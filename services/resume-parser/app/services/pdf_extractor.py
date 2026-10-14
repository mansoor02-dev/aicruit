"""
PDF extraction service with native text extraction and conditional OCR.

Uses PyMuPDF (fitz) for native text extraction. Detects scanned/empty pages
using a configurable character-count threshold and falls back to Tesseract
OCR only when necessary.

Resource cleanup:
- PDF documents are always closed via context manager / finally blocks.
- PIL images are explicitly closed after OCR.
- No large buffers retained after extraction.
"""

from __future__ import annotations

import hashlib
import io
import logging
import struct
from dataclasses import dataclass, field
from typing import Optional

import fitz  # PyMuPDF

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


# ── Result types ──────────────────────────────────────────────────────────

@dataclass
class PageResult:
    """Extraction result for a single page."""
    page_number: int
    text: str
    method: str  # "native" | "ocr" | "empty"
    char_count: int = 0


@dataclass
class ExtractionResult:
    """Complete extraction result for a PDF document."""
    text: str
    total_pages: int
    native_pages: int = 0
    ocr_pages: int = 0
    empty_pages: int = 0
    content_hash: str = ""
    pages: list[PageResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ── Validation ────────────────────────────────────────────────────────────

class PDFValidationError(Exception):
    """Raised when a PDF fails validation checks."""
    pass


class OCRUnavailableError(Exception):
    """Raised when OCR is needed but Tesseract is not installed."""
    pass


def _validate_pdf_magic(data: bytes) -> None:
    """Check that the file starts with the PDF magic bytes (%PDF-)."""
    if len(data) < 5 or data[:5] != b"%PDF-":
        raise PDFValidationError(
            "File is not a valid PDF (missing %PDF- header)"
        )


def _validate_file_size(data: bytes, max_bytes: int) -> None:
    """Validate file size against configured maximum."""
    if len(data) > max_bytes:
        size_mb = len(data) / (1024 * 1024)
        max_mb = max_bytes / (1024 * 1024)
        raise PDFValidationError(
            f"File size ({size_mb:.1f} MB) exceeds maximum ({max_mb:.0f} MB)"
        )


# ── OCR helpers ───────────────────────────────────────────────────────────

def _is_tesseract_available() -> bool:
    """Check whether Tesseract OCR is installed and accessible."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _ocr_page(page: fitz.Page, dpi: int = 200) -> str:
    """OCR a single page using Tesseract via PyMuPDF pixmap."""
    from PIL import Image
    import pytesseract

    pix = page.get_pixmap(dpi=dpi)
    try:
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        try:
            text = pytesseract.image_to_string(img)
            return text.strip()
        finally:
            img.close()
    finally:
        # Pixmap doesn't have close() but setting to None helps GC
        pix = None


# ── DOCX extraction ──────────────────────────────────────────────────────

def extract_docx(data: bytes) -> ExtractionResult:
    """Extract text from a DOCX file."""
    from docx import Document as DocxDocument

    doc = DocxDocument(io.BytesIO(data))
    text = "\n".join(p.text for p in doc.paragraphs)
    content_hash = hashlib.sha256(data).hexdigest()

    return ExtractionResult(
        text=text,
        total_pages=1,  # DOCX doesn't have page concept
        native_pages=1,
        content_hash=content_hash,
        pages=[PageResult(page_number=1, text=text, method="native", char_count=len(text))],
    )


# ── Main extraction ──────────────────────────────────────────────────────

def extract_pdf(
    data: bytes,
    settings: Optional[Settings] = None,
) -> ExtractionResult:
    """
    Extract text from a PDF with validation and conditional OCR.

    Pipeline:
    1. Validate PDF magic bytes and file size.
    2. Open with PyMuPDF and validate page count.
    3. Extract text natively from each page.
    4. For pages below the character threshold, attempt OCR if enabled.
    5. Return combined text with extraction metadata.

    Args:
        data: Raw PDF file bytes.
        settings: Service configuration (defaults to global settings).

    Returns:
        ExtractionResult with combined text and per-page metadata.

    Raises:
        PDFValidationError: If the file fails validation.
        OCRUnavailableError: If OCR is needed but Tesseract is unavailable.
    """
    if settings is None:
        settings = get_settings()

    # Step 1: Validate file format and size
    _validate_pdf_magic(data)
    _validate_file_size(data, settings.max_file_size_bytes)

    # Compute content hash for caching
    content_hash = hashlib.sha256(data).hexdigest()

    # Step 2: Open and validate page count
    doc = None
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        raise PDFValidationError(f"Failed to open PDF: {e}") from e

    try:
        if doc.page_count == 0:
            raise PDFValidationError("PDF contains no pages")

        if doc.page_count > settings.max_page_count:
            raise PDFValidationError(
                f"PDF has {doc.page_count} pages (maximum: {settings.max_page_count})"
            )

        # Step 3 & 4: Extract text per page
        pages: list[PageResult] = []
        native_count = 0
        ocr_count = 0
        empty_count = 0
        warnings: list[str] = []
        ocr_needed_but_unavailable: list[int] = []

        tesseract_available: Optional[bool] = None  # Lazy check

        for page_num in range(doc.page_count):
            page = doc[page_num]
            native_text = page.get_text().strip()

            if len(native_text) >= settings.min_chars_per_page:
                # Native extraction succeeded
                pages.append(PageResult(
                    page_number=page_num + 1,
                    text=native_text,
                    method="native",
                    char_count=len(native_text),
                ))
                native_count += 1
            elif settings.ocr_enabled:
                # Page appears scanned — try OCR
                if tesseract_available is None:
                    tesseract_available = _is_tesseract_available()

                if tesseract_available:
                    try:
                        ocr_text = _ocr_page(page, dpi=settings.ocr_dpi)
                        if ocr_text.strip():
                            pages.append(PageResult(
                                page_number=page_num + 1,
                                text=ocr_text,
                                method="ocr",
                                char_count=len(ocr_text),
                            ))
                            ocr_count += 1
                            logger.info(
                                "pdf_extractor.ocr_page",
                                extra={"page": page_num + 1, "chars": len(ocr_text)},
                            )
                        else:
                            pages.append(PageResult(
                                page_number=page_num + 1,
                                text="",
                                method="empty",
                            ))
                            empty_count += 1
                    except Exception as ocr_err:
                        logger.warning(
                            "pdf_extractor.ocr_failed",
                            extra={"page": page_num + 1, "error": str(ocr_err)},
                        )
                        pages.append(PageResult(
                            page_number=page_num + 1,
                            text=native_text,  # Keep whatever native text we got
                            method="native",
                            char_count=len(native_text),
                        ))
                        warnings.append(f"OCR failed on page {page_num + 1}")
                else:
                    ocr_needed_but_unavailable.append(page_num + 1)
                    pages.append(PageResult(
                        page_number=page_num + 1,
                        text=native_text,
                        method="empty",
                        char_count=len(native_text),
                    ))
                    empty_count += 1
            else:
                # OCR disabled, keep whatever we got
                pages.append(PageResult(
                    page_number=page_num + 1,
                    text=native_text,
                    method="empty",
                    char_count=len(native_text),
                ))
                empty_count += 1

        # If ALL pages needed OCR but it wasn't available, raise
        if ocr_needed_but_unavailable and native_count == 0 and ocr_count == 0:
            raise OCRUnavailableError(
                f"PDF appears to be scanned ({len(ocr_needed_but_unavailable)} pages with "
                f"insufficient text), but Tesseract OCR is not available. "
                f"Install tesseract-ocr to process scanned documents."
            )

        if ocr_needed_but_unavailable:
            warnings.append(
                f"Pages {ocr_needed_but_unavailable} appear scanned but OCR is unavailable"
            )

        # Combine page text
        combined_text = "\n\n".join(
            p.text for p in pages if p.text.strip()
        )

        return ExtractionResult(
            text=combined_text,
            total_pages=doc.page_count,
            native_pages=native_count,
            ocr_pages=ocr_count,
            empty_pages=empty_count,
            content_hash=content_hash,
            pages=pages,
            warnings=warnings,
        )

    finally:
        doc.close()


def extract_text(data: bytes, ext: str, settings: Optional[Settings] = None) -> ExtractionResult:
    """
    Extract text from a file based on its extension.

    This is the main entry point for the extraction service.

    Args:
        data: Raw file bytes.
        ext: File extension (e.g., ".pdf", ".docx").
        settings: Service configuration.

    Returns:
        ExtractionResult with extracted text and metadata.

    Raises:
        PDFValidationError: If validation fails.
        ValueError: If file type is unsupported.
    """
    ext = ext.lower()
    if ext == ".pdf":
        return extract_pdf(data, settings)
    elif ext == ".docx":
        return extract_docx(data)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

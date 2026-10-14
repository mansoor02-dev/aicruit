import fitz
import pytest

from app.core.config import Settings
from app.services import pdf_extractor
from app.services.pdf_extractor import (
    OCRUnavailableError,
    PDFValidationError,
    extract_pdf,
)


def _make_pdf(*page_texts: str) -> bytes:
    document = fitz.open()
    for text in page_texts:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_pdf_magic_validation_rejects_invalid_header():
    with pytest.raises(PDFValidationError, match="%PDF-"):
        extract_pdf(b"not a pdf")


def test_pdf_magic_validation_accepts_valid_header():
    with pytest.raises(PDFValidationError, match="Failed to open PDF"):
        extract_pdf(b"%PDF-invalid document", _settings(ocr_enabled=False))


def test_file_size_limit_is_enforced_before_opening_pdf():
    data = b"%PDF-" + b"x" * (1024 * 1024)

    with pytest.raises(PDFValidationError, match="exceeds maximum"):
        extract_pdf(data, _settings(max_file_size_mb=1))


def test_empty_scanned_page_is_reported_when_ocr_is_unavailable(monkeypatch):
    monkeypatch.setattr(pdf_extractor, "_is_tesseract_available", lambda: False)
    settings = _settings(ocr_enabled=True, min_chars_per_page=10)

    result = extract_pdf(_make_pdf("This page contains enough native text.", ""), settings)

    assert result.total_pages == 2
    assert result.native_pages == 1
    assert result.empty_pages == 1
    assert any("OCR is unavailable" in warning for warning in result.warnings)
    assert result.pages[1].method == "empty"


def test_ocr_unavailable_for_only_scanned_page_is_an_explicit_error(monkeypatch):
    monkeypatch.setattr(pdf_extractor, "_is_tesseract_available", lambda: False)

    with pytest.raises(OCRUnavailableError, match="appears to be scanned"):
        extract_pdf(_make_pdf(""), _settings(ocr_enabled=True))


def test_pdf_document_is_closed_when_page_extraction_fails(monkeypatch):
    class BrokenPage:
        def get_text(self):
            raise RuntimeError("page extraction failed")

    class FakeDocument:
        page_count = 1

        def __getitem__(self, index):
            return BrokenPage()

        def close(self):
            self.closed = True

    document = FakeDocument()
    monkeypatch.setattr(pdf_extractor.fitz, "open", lambda **kwargs: document)

    with pytest.raises(RuntimeError, match="page extraction failed"):
        extract_pdf(b"%PDF-test", _settings(ocr_enabled=False))

    assert document.closed is True

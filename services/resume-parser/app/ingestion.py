import fitz
from docx import Document
from pathlib import Path
from io import BytesIO
import pytesseract
from PIL import Image


def ingest(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    data = open(file_path, "rb").read()
    return ingest_bytes(data, ext)


def ingest_bytes(data: bytes, ext: str) -> str:
    if ext == ".pdf":
        return _extract_pdf(data)
    elif ext == ".docx":
        return _extract_docx(data)
    elif ext in {".png", ".jpg", ".jpeg", ".tiff"}:
        return _extract_image(data)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _extract_pdf(data: bytes) -> str:
    doc = fitz.open(stream=data, filetype="pdf")
    text = "".join(page.get_text() for page in doc)
    if text.strip():
        return text
    return None #_ocr_pdf(data)


def _ocr_pdf(data: bytes) -> str:
    doc = fitz.open(stream=data, filetype="pdf")
    text = ""
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text += pytesseract.image_to_string(img)
    return text


def _extract_docx(data: bytes) -> str:
    doc = Document(BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)


def _extract_image(data: bytes) -> str:
    img = Image.open(BytesIO(data))
    return pytesseract.image_to_string(img)
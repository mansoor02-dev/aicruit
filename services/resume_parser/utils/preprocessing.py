import os
from langdetect import detect
from cleaner import clean_text
from pipelines.extract_text import extract_text_docx, extract_text_pdf, extract_text_pdf_ocr

def preprocess_resume(file_path):
    filename = os.path.basename(file_path)

    log = {
        "filename": filename,
        "is_scanned": False,
        "used_ocr": False,
        "is_corrupted": False,
        "language_raw": None,
        "language_clean": None,
        "text_length_raw": 0,
        "text_length_clean": 0,
    }

    # ----------------------- Extract Text -----------------------
    if filename.lower().endswith(".pdf"):
        text = extract_text_pdf(file_path)

        if not text or len(text.strip()) < 40:
            log["is_scanned"] = True
            text = extract_text_pdf_ocr(file_path)
            log["used_ocr"] = True

    elif filename.lower().endswith(".docx"):
        text = extract_text_docx(file_path)

    else:
        log["is_corrupted"] = True
        return log, ""

    if text is None or len(text.strip()) < 10:
        log["is_corrupted"] = True
        return log, ""

    log["text_length_raw"] = len(text)

    # ----------------------- Language Detection -----------------------
    try:
        log["language_raw"] = detect(text[:2000])
    except:
        log["language_raw"] = "unknown"

    # ----------------------- Cleaning -----------------------
    cleaned_text = clean_text(text)
    log["text_length_clean"] = len(cleaned_text)

    try:
        log["language_clean"] = detect(cleaned_text[:2000])
    except:
        log["language_clean"] = "unknown"

    return log, cleaned_text
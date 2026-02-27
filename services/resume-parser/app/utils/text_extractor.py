import os
from typing import Optional
import fitz
from pdf2image import convert_from_path
import pytesseract
import docx

def extract_text_from_pdf(pdf_path: str) -> Optional[str]:
    """Extract text from PDF using PyMuPDF"""
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            full_text += text + "\n"
        
        doc.close()
        return full_text
    
    except Exception as e:
        print(f"❌ Error reading PDF: {e}")
        return None


def extract_text_pdf_ocr(pdf_path: str) -> Optional[str]:
    """Extract text from PDF using OCR (for image-based PDFs)"""
    try:
        images = convert_from_path(pdf_path)
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        print(f"❌ Error reading PDF with OCR: {e}")
        return None


def extract_text_docx(docx_path: str) -> Optional[str]:
    """Extract text from DOCX file"""
    try:
        doc = docx.Document(docx_path)
        return "\n".join([p.text for p in doc.paragraphs]).strip()
    except Exception as e:
        print(f"❌ Error reading DOCX: {e}")
        return None

def extract_from_file(file_path: str) -> Optional[str]:
    """
    Extract text from PDF or DOCX file
    
    Args:
        file_path: Path to the file
    
    Returns:
        str: Extracted text or None if failed
    """
    filename = os.path.basename(file_path)
    try: 
        # For PDF
        if filename.lower().endswith(".pdf"):
            text = extract_text_from_pdf(file_path)
            
            # Fallback to OCR if text extraction failed or too short
            if not text or len(text.strip()) < 30:
                text = extract_text_pdf_ocr(file_path)
        
        # For DOCX    
        elif filename.lower().endswith(".docx"):
            text = extract_text_docx(file_path)
        else:
            raise ValueError(f"Unsupported file type: {filename}")
        
        return text
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return None

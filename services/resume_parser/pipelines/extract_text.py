import os
import fitz
from pdf2image import convert_from_path
import pytesseract
import docx

def extract_text_from_pdf(pdf_path: str) -> str:
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


# For OCR (Images)
def extract_text_pdf_ocr(pdf_path: str) -> str:
    try:
        images = convert_from_path(pdf_path)
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        print(f"❌ Error reading PDF: {e}")
        return None

# For Documents
def extract_text_docx(pdf_path: str) -> str:
    try:
        doc = docx.Document(pdf_path)
        return "\n".join([p.text for p in doc.paragraphs]).strip()
    except Exception as e:
        print(f"❌ Error reading PDF: {e}")
        return None
    
def extract_from_pdf(pdf_path: str) -> str:
    filename = os.path.basename(pdf_path)
    try: 
        # For PDF
        if filename.lower().endswith(".pdf"):
            text = extract_text_from_pdf(pdf_path)
            
            # For OCR
            if not text or len(text.strip()) < 30:
                text = extract_text_pdf_ocr(pdf_path)
        
        # For Document    
        elif filename.lower().endswith(".docx"):
            text = extract_text_docx(pdf_path)

        return text
    except Exception as e:
        print(f"❌ Error reading PDF: {e}")
        return None
        
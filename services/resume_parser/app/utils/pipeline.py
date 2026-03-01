import os
from typing import Optional

from .file_downloader import download_file_from_url
from .text_extractor import extract_from_file
from .text_preprocessor import clean_text
from .llm_extractor import extract_resume_with_llm
from ..models.resume_schema import StructuredResume


def process_resume_from_url(
    pdf_url: str,
    api_key: Optional[str] = None
) -> StructuredResume:
    """
    Complete pipeline: URL → Download → Extract Text → Clean → LLM Extract → Validate
    
    Args:
        pdf_url: URL of the resume PDF/DOCX
        api_key: Google API key for LLM
    
    Returns:
        StructuredResume: Validated structured resume
    """
    
    temp_file_path = None
    
    try:
        print(f"\n{'='*60}")
        print(f"📄 Processing resume from URL: {pdf_url}")
        print(f"{'='*60}")
        
        # Step 1: Download file
        print("\n1️⃣ Downloading file from URL...")
        temp_file_path = download_file_from_url(pdf_url)
        print(f"   ✅ Downloaded to: {temp_file_path}")
        
        # Step 2: Extract text
        print("\n2️⃣ Extracting text from file...")
        raw_text = extract_from_file(temp_file_path)
        if not raw_text:
            raise ValueError("Failed to extract text from file")
        
        print(f"   ✅ Extracted {len(raw_text)} characters")
        
        # Step 3: Clean text
        print("\n3️⃣ Cleaning and normalizing text...")
        cleaned_text = clean_text(raw_text)
        print(f"   ✅ Cleaned: {len(cleaned_text)} chars (removed {len(raw_text) - len(cleaned_text)} chars)")
        
        # Step 4: Extract with LLM
        print("\n4️⃣ Extracting structured data with LLM...")
        extracted_data = extract_resume_with_llm(cleaned_text, api_key=api_key)
        
        # Step 5: Validate with Pydantic
        print("\n5️⃣ Validating with Pydantic schema...")
        try:
            # Add source file metadata
            extracted_data['source_file'] = os.path.basename(pdf_url)
            
            # Validate
            structured_resume = StructuredResume(**extracted_data)
            print("   ✅ Validation passed!")
            
        except Exception as e:
            print(f"   ❌ Validation failed: {e}")
            raise
        
        print(f"\n{'='*60}")
        print("✅ PROCESSING COMPLETE!")
        print(f"{'='*60}\n")
        
        return structured_resume
    
    finally:
        # Clean up temp file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                print(f"Warning: Failed to delete temp file: {e}")


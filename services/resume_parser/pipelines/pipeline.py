import pydantic
import json
from extract_text import extract_from_pdf
from preprocess_text import clean_text
from llm_extracter import extract_resume_with_llm
from models.resume_schema import StructuredResume

def process_resume(
    pdf_path: str,
    output_dir: str = "extracted_resumes",
    api_key: Optional[str] = None
) -> StructuredResume:
    """
    Complete pipeline: PDF → Cleaned Text → Structured JSON
    
    Args:
        pdf_path: Path to resume PDF
        output_dir: Directory to save output
        api_key: Google API key
    
    Returns:
        StructuredResume: Validated structured resume
    """
    
    print(f"\n{'='*60}")
    print(f"📄 Processing: {pdf_path}")
    print(f"{'='*60}")
    
    # Step 1: Extract text
    print("\n1️⃣ Extracting text from PDF...")
    raw_text = extract_from_pdf(pdf_path)
    if not raw_text:
        raise ValueError("Failed to extract text from PDF")
    
    print(f"   ✅ Extracted {len(raw_text)} characters")
    
    # Step 2: Clean text
    print("\n2️⃣ Cleaning and normalizing text...")
    cleaned_text = clean_text(raw_text)
    print(f"   ✅ Cleaned: {len(cleaned_text)} chars (removed {len(raw_text) - len(cleaned_text)} chars)")
    
    # Step 3: Extract with LLM
    print("\n3️⃣ Extracting structured data with LLM...")
    extracted_data = extract_resume_with_llm(cleaned_text, api_key=api_key)
    
    # Step 4: Validate with Pydantic
    print("\n4️⃣ Validating with Pydantic schema...")
    try:
        # Add source file metadata
        extracted_data['source_file'] = os.path.basename(pdf_path)
        
        # Validate
        structured_resume = StructuredResume(**extracted_data)
        print("   ✅ Validation passed!")
        
    except Exception as e:
        print(f"   ❌ Validation failed: {e}")
        raise
    
    # Step 5: Save output
    print("\n5️⃣ Saving output...")
    os.makedirs(output_dir, exist_ok=True)
    
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}_structured.json")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(structured_resume.model_dump(), f, indent=2, ensure_ascii=False)
    
    print(f"   ✅ Saved to: {output_path}")
    
    print(f"\n{'='*60}")
    print("✅ PROCESSING COMPLETE!")
    print(f"{'='*60}\n")
    
    return structured_resume
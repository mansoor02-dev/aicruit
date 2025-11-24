import json
import os
from typing import Optional
import google.generativeai as genai
from .llm_instruction import get_schema_description
from dotenv import load_dotenv

load_dotenv('.env')  # Loads .env file automatically

def extract_resume_with_llm(
    cleaned_text: str,
    model_name: str = "gemini-2.5-flash",
    api_key: Optional[str] = None
) -> dict:
    """
    Extract structured resume data using LLM
    
    Args:
        cleaned_text: Preprocessed resume text
        model_name: Gemini model to use
        api_key: Google API key (or set GOOGLE_API_KEY env var)
    
    Returns:
        dict: Extracted resume data
    """
    
    # Configure API
    if api_key:
        genai.configure(api_key=api_key)
    elif os.getenv('GOOGLE_API_KEY'):
        genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
    else:
        raise ValueError("No API key provided. Set GOOGLE_API_KEY or pass api_key parameter")
    
    # Create model
    model = genai.GenerativeModel(model_name)
    
    # Build prompt
    schema_desc = get_schema_description()
    prompt = f"""{schema_desc}

RESUME TEXT:
{cleaned_text}

Extract the information and return ONLY the JSON object (no markdown, no explanation):"""
    
    # Call LLM
    print("🤖 Calling LLM for extraction...")
    response = model.generate_content(prompt)
    response_text = response.text
    
    # Clean response (remove markdown if present)
    if '```json' in response_text:
        response_text = response_text.split('```json')[1].split('```')[0]
    elif '```' in response_text:
        response_text = response_text.split('```')[1].split('```')[0]
    
    # Parse JSON
    try:
        extracted_data = json.loads(response_text.strip())
        print("✅ Successfully extracted JSON")
        return extracted_data
    
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing failed: {e}")
        print(f"Response was:\n{response_text[:500]}...")
        raise


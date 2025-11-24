import json
import os
from fastapi import APIRouter, HTTPException
from typing import Optional
from ..models.api_models import ParseResumeRequest, ParseResumeResponse
from ..utils.pipeline import process_resume_from_url
from ..utils.db import get_db_connection
from dotenv import load_dotenv

load_dotenv('.env')
router = APIRouter()


@router.post("/parse-resume", response_model=ParseResumeResponse)
async def parse_resume(request: ParseResumeRequest):
    """
    Parse resume from URL and save to database
    
    Args:
        request: ParseResumeRequest containing id (optional) and pdf_url
    
    Returns:
        ParseResumeResponse with id and message
    """
    try:
        # Get API key from environment
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY environment variable not set"
            )
        
        # Process resume using pipeline
        print(f"Processing resume from URL: {request.pdf_url}")
        structured_resume = process_resume_from_url(
            pdf_url=request.pdf_url,
            api_key=api_key
        )
        
        # Convert to JSON for database storage
        parsed_json = json.dumps(structured_resume.model_dump(), default=str)
        
        # Save to database
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Insert into resumes table
            insert_sql = """
                INSERT INTO resumes (original_file_url, parsed_json, parse_status)
                VALUES (%s, %s, %s)
                RETURNING id
            """
            
            cur.execute(
                insert_sql,
                (
                    request.pdf_url,
                    parsed_json,
                    'success'
                )
            )
            
            result = cur.fetchone()
            conn.commit()
            
            if not result or not result[0]:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to save resume to database"
                )
            
            resume_id = str(result[0])
            
            return ParseResumeResponse(
                id=resume_id,
                message="Resume parsed and saved successfully"
            )
        
        except Exception as db_error:
            conn.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Database error: {str(db_error)}"
            )
        
        finally:
            cur.close()
            conn.close()
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error parsing resume: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse resume: {str(e)}"
        )


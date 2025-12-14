import json
import os
from fastapi import APIRouter, HTTPException
from typing import Optional
from ..models.api_models import ParseResumeRequest, ParseResumeResponse
from ..utils.pipeline import process_resume_from_url
from ..utils.db import get_db_session, Resume
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

        # Prepare parsed files directory (configurable)
        parsed_dir = os.getenv("PARSED_DIR",
                       os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'parsed')))
        os.makedirs(parsed_dir, exist_ok=True)
        
        # Save to database using SQLAlchemy ORM
        session = get_db_session()
        try:
            resume_row = Resume(
                original_file_url=request.pdf_url,
                parsed_json=parsed_json,
                parse_status='success'
            )
            session.add(resume_row)
            session.commit()
            session.refresh(resume_row)

            resume_id = str(resume_row.id)

            # Save parsed JSON to file so it's visible on host
            try:
                parsed_filename = f"resume_{resume_id}.json"
                parsed_path = os.path.join(parsed_dir, parsed_filename)
                with open(parsed_path, "w", encoding="utf-8") as pf:
                    pf.write(parsed_json)
            except Exception as file_err:
                print(f"Warning: failed to write parsed file for resume {resume_id}: {file_err}")

            return ParseResumeResponse(
                id=resume_id,
                message="Resume parsed and saved successfully"
            )
        except Exception as db_error:
            session.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")
        finally:
            session.close()
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error parsing resume: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse resume: {str(e)}"
        )


import json
import os
from fastapi import APIRouter, HTTPException
from typing import Optional
from ..models.api_models import ParseResumeRequest, ParseResumeResponse
from ..utils.db import get_db_session, Resume
from dotenv import load_dotenv

load_dotenv('.env')
router = APIRouter()


@router.post("/parse-resume", response_model=ParseResumeResponse)
async def parse_resume(request: ParseResumeRequest):
    """     
    Parse resume from database by resume_id
    Extract skills and save to storage
    
    Args:
        request: ParseResumeRequest containing resume_id
    
    Returns:
        ParseResumeResponse with id, skills and message
    """
    try:
        # Fetch resume from database
        session = next(get_db_session())
        try:
            resume_row = session.query(Resume).filter(Resume.id == request.resume_id).first()
            if not resume_row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Resume with ID {request.resume_id} not found"
                )
            
            # If already parsed, return it
            if resume_row.parsed_skills:
                print(f"Resume {request.resume_id} already parsed")
                skills_data = resume_row.parsed_skills
                if isinstance(skills_data, dict):
                    skills = skills_data.get('skills', [])
                elif isinstance(skills_data, list):
                    skills = skills_data
                else:
                    skills = []
            else:
                # Need to parse
                from ..utils.pipeline import process_resume_from_url
                print(f"Processing resume from database: {request.resume_id}")
                
                file_url = resume_row.file_url
                # Convert localhost URL to docker internal service if applicable
                if "localhost:8005" in file_url or "127.0.0.1:8005" in file_url:
                    file_url = file_url.replace("localhost:8005", "aicruit_file_service:8005").replace("127.0.0.1:8005", "aicruit_file_service:8005")
                elif file_url.startswith("/"):
                    file_url = f"http://aicruit_file_service:8005{file_url}"
                
                # Extract using Pipeline
                structured_resume = process_resume_from_url(file_url)
                skills = structured_resume.skills
                
                # Update resume record with full parsed text and skills
                try:
                    resume_row.parsed_skills = {"skills": skills}
                    resume_row.parsed_text = structured_resume.model_dump_json()
                    session.commit()
                    session.refresh(resume_row)
                    print(f"✅ Updated resume record with parsed data")
                except Exception as update_err:
                    session.rollback()
                    raise HTTPException(status_code=500, detail=f"Failed to update resume: {str(update_err)}")
            
            return ParseResumeResponse(
                id=request.resume_id,
                message="Resume parsed successfully",
                skills=skills
            )
        except HTTPException:
            raise
        except Exception as db_error:
            import traceback
            traceback.print_exc()
            try:
                session.rollback()
            except Exception:
                pass
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


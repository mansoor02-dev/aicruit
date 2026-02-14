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
        session = get_db_session()
        try:
            resume_row = session.query(Resume).filter(Resume.id == request.resume_id).first()
            if not resume_row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Resume with ID {request.resume_id} not found"
                )
            
            # Parse stored JSON
            print(f"Processing resume from database: {request.resume_id}")
            resume_data = json.loads(resume_row.parsed_json)
            
            # Extract skills from resume data
            skills = resume_data.get('skills', [])
            
            # Prepare parsed skills data for storage
            parsed_skills = {
                "skills": skills
            }
            
            # Prepare parsed files directory (configurable)
            parsed_dir = os.getenv("PARSED_DIR",
                           os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'parsed')))
            os.makedirs(parsed_dir, exist_ok=True)
            
            # Save parsed skills JSON to file
            try:
                parsed_filename = f"resume_{request.resume_id}_skills.json"
                parsed_path = os.path.join(parsed_dir, parsed_filename)
                with open(parsed_path, "w", encoding="utf-8") as pf:
                    json.dump(parsed_skills, pf, indent=2)
                print(f"✅ Saved parsed skills to: {parsed_filename}")
            except Exception as file_err:
                print(f"Warning: failed to write parsed skills file for resume {request.resume_id}: {file_err}")
            
            # Update resume record with parsed skills
            try:
                resume_row.parsed_skills = json.dumps(parsed_skills)
                session.commit()
                session.refresh(resume_row)
                print(f"✅ Updated resume record with parsed skills")
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


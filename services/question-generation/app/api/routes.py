"""HTTP routes for the Question Generation service."""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.prompts.templates import build_scenario_guidance
from app.schemas.llm import DraftEmail
from app.schemas.requests import DraftEmailRequest, QuestionRequest

logger = logging.getLogger(__name__)
router = APIRouter()


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.post("/next-question")
async def get_next_question(req: QuestionRequest, request: Request):
    """
    Generate the next interview question.

    Returns:
        {
            "question": str,
            "metadata": {
                "category": str,
                "difficulty": str,
                "is_followup": bool,
                "evaluation": {...},   # present when a follow-up is generated
                ...
            }
        }
    """
    try:
        graph = request.app.state.graph
        previous_qa_list = (
            [qa.model_dump() for qa in req.previous_qa]
            if req.previous_qa
            else None
        )

        logger.info(
            f"Generating question: history_length={len(previous_qa_list or [])}, "
            f"difficulty={req.difficulty}, category={req.category}, "
            f"pool_size={len(req.question_pool or [])}"
        )

        result = await graph.ainvoke(
            {
                "resume_json": req.resume_json or {},
                "previous_qa_list": previous_qa_list,
                "difficulty": req.difficulty,
                "category": req.category,
                "pool": (
                    [pool_question.model_dump() for pool_question in req.question_pool]
                    if req.question_pool
                    else []
                ),
                "used_pool_questions": req.used_pool_questions or [],
            }
        )
        question, metadata = result["question"], result["metadata"]

        logger.info(
            f"Generated: category={metadata.get('category')}, "
            f"is_followup={metadata.get('is_followup')}"
        )

        return {"question": question, "metadata": metadata}

    except Exception as e:
        logger.error(f"Error generating question: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/draft-email")
async def draft_email(req: DraftEmailRequest, request: Request):
    """
    Generate a candidate email subject + body.
    Returns: {"subject": str, "body": str}
    """
    try:
        scenario = (req.scenario or "custom").strip().lower()
        guidance = build_scenario_guidance(
            scenario,
            req.job_title,
            req.scheduled_at,
            req.stage_name,
            req.custom_instructions,
        )

        company = req.company_name or "AIcruit"
        first_name = (req.candidate_name or "").split(" ")[0] if req.candidate_name else "there"

        context_lines = [
            f"Candidate full name: {req.candidate_name}",
            f"Candidate first name: {first_name}",
            f"Job title: {req.job_title}",
            f"Company name: {company}",
        ]
        if req.scheduled_at:
            context_lines.append(f"Scheduled at (ISO): {req.scheduled_at}")
        if req.stage_name:
            context_lines.append(f"Stage name: {req.stage_name}")
        if req.overall_score is not None:
            context_lines.append(f"Overall interview score (0-10): {req.overall_score}")
        if req.category_scores:
            cs_lines = ", ".join(
                f"{c.category}: {c.score:.1f}/10" for c in req.category_scores
            )
            context_lines.append(f"Category scores: {cs_lines}")
        if req.custom_instructions:
            context_lines.append(f"Recruiter instructions: {req.custom_instructions}")

        # For rejection with scores, instruct the model to append a performance summary
        extra_rules = ""
        if scenario == "rejection" and req.category_scores:
            extra_rules = (
                "\n\nIMPORTANT: At the end of the body (before the sign-off), include a short "
                "section that begins with: 'We've included a brief summary of your interview "
                "performance to help with your continued growth:' followed by one line per "
                "category formatted exactly as '- {category}: {score}/10'."
            )

        email_chain = request.app.state.chains.email
        result = await email_chain.ainvoke(
            {
                "scenario": scenario,
                "guidance": guidance,
                "context": "\n".join(context_lines),
                "extra_rules": extra_rules,
            }
        )
        if isinstance(result, DraftEmail):
            parsed = result.model_dump()
        else:
            parsed = DraftEmail.model_validate(result).model_dump()
        if not parsed.get("subject") or not parsed.get("body"):
            raise ValueError("LLM returned empty subject or body")
        return parsed

    except Exception as e:
        logger.error(f"draft-email failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Email drafting failed: {e}")


@router.get("/health")
async def health():
    return {"status": "ok", "service": "interview-question-generation"}

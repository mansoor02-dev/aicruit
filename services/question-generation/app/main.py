"""
FastAPI endpoint for the interview question generation service.
HTTP concerns only — all orchestration is delegated to InterviewOrchestrator.
"""
import csv
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


import sys
sys.path.insert(0, "/app")
sys.path.append(str(Path(__file__).parent.parent))

from shared.llm_client import LLMClient
from pipelines.llm_loader import get_embedder, get_default_chat
from pipelines.answer_evaluator import AnswerEvaluator
from pipelines.orchestrator import InterviewOrchestrator
from pipelines.question_generator import QuestionGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Module-level singletons (populated during lifespan startup)
orchestrator: Optional[InterviewOrchestrator] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator

    logger.info("Initialising interview service…")

    # LLM and embedder are now lazy-loaded from shared/ on first use
    logger.info("Shared LLM and embedding providers configured")

    dataset_path = Path("data/software_questions.csv")
    with open(dataset_path, newline="", encoding="latin1") as f:
        dataset = list(csv.DictReader(f))
    logger.info(f"Dataset loaded: {len(dataset)} questions")

    evaluator = AnswerEvaluator(embedder=get_embedder())
    question_generator = QuestionGenerator(dataset_questions=dataset)

    orchestrator = InterviewOrchestrator(
        evaluator=evaluator,
        question_generator=question_generator,
    )
    logger.info("Interview service ready")

    yield

    logger.info("Shutting down interview service…")


app = FastAPI(title="Interview Question Generation API", lifespan=lifespan)


# ------------------------------------------------------------------
# Request / Response schemas
# ------------------------------------------------------------------

class QA(BaseModel):
    Q: str
    A: str


class PoolQuestion(BaseModel):
    question: str
    topic: Optional[str] = None


class QuestionRequest(BaseModel):
    resume_json: Optional[Dict[str | None, Any]] = None
    previous_qa: Optional[List[QA]] = []
    difficulty: str = "medium"
    category: Optional[str] = None
    question_pool: Optional[List[PoolQuestion]] = None
    used_pool_questions: Optional[List[str]] = None


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@app.post("/next-question")
async def get_next_question(req: QuestionRequest):
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
        previous_qa_list = (
            [{"Q": qa.Q, "A": qa.A} for qa in req.previous_qa]
            if req.previous_qa
            else None
        )

        logger.info(
            f"Generating question: history_length={len(previous_qa_list or [])}, "
            f"difficulty={req.difficulty}, category={req.category}, "
            f"pool_size={len(req.question_pool or [])}"
        )

        # If a recruiter-uploaded pool exists, prefer picking from it.
        if req.question_pool:
            used = set(req.used_pool_questions or [])
            target_topic = (req.category or "").strip().lower()

            def _topic_match(q: PoolQuestion) -> bool:
                if not target_topic:
                    return True
                t = (q.topic or "").strip().lower()
                return t == target_topic

            unused = [q for q in req.question_pool if q.question not in used]
            preferred = [q for q in unused if _topic_match(q)]

            chosen = None
            if preferred:
                chosen = preferred[0]
            elif unused:
                chosen = unused[0]

            if chosen is not None:
                metadata = {
                    "source": "recruiter_pool",
                    "scenario": "new_question",
                    "question_id": None,
                    "category": chosen.topic or req.category or "Unknown",
                    "difficulty": req.difficulty,
                    "reference_answer": "",
                    "is_followup": False,
                    "evaluation": {},
                }
                # Still evaluate prior answer if there is history, to populate scores
                if previous_qa_list:
                    last_qa = previous_qa_list[-1]
                    try:
                        evaluation, flow = orchestrator.evaluator.evaluate_combined(
                            question=last_qa["Q"],
                            user_answer=last_qa["A"],
                            reference_answer=last_qa.get("reference_answer"),
                            is_followup=last_qa.get("is_followup", False),
                        )
                        metadata["evaluation"] = {
                            "decision":   flow.get("decision"),
                            "score":      flow.get("score_value"),
                            "confidence": evaluation.get("confidence"),
                            "remarks":    flow.get("remarks"),
                            "feedback":   evaluation.get("feedback"),
                        }
                    except Exception as eval_exc:
                        logger.warning(f"Pool path evaluator failed: {eval_exc}")
                return {"question": chosen.question, "metadata": metadata}

        question, metadata = orchestrator.generate_next_question(
            resume_json=req.resume_json or {},
            previous_qa_list=previous_qa_list,
            difficulty=req.difficulty,
            category=req.category,
        )

        logger.info(
            f"Generated: category={metadata.get('category')}, "
            f"is_followup={metadata.get('is_followup')}"
        )

        return {"question": question, "metadata": metadata}

    except Exception as e:
        logger.error(f"Error generating question: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class CategoryScore(BaseModel):
    category: str
    score: float


class DraftEmailRequest(BaseModel):
    scenario: str
    candidate_name: str
    job_title: str
    company_name: Optional[str] = None
    scheduled_at: Optional[str] = None
    stage_name: Optional[str] = None
    category_scores: Optional[List[CategoryScore]] = None
    overall_score: Optional[float] = None
    custom_instructions: Optional[str] = None


def _strip_code_fences(text: str) -> str:
    """Strip ```json ... ``` or ``` ... ``` wrappers from LLM output."""
    import re
    s = (text or "").strip()
    # Remove leading ```json or ```
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


def _parse_email_json(text: str) -> Dict[str, str]:
    """Parse strict JSON {subject, body} defensively."""
    import json as _json
    import re
    cleaned = _strip_code_fences(text)
    try:
        data = _json.loads(cleaned)
        if isinstance(data, dict) and "subject" in data and "body" in data:
            return {"subject": str(data["subject"]).strip(), "body": str(data["body"]).strip()}
    except Exception:
        pass
    # Fallback: try regex extraction
    subj_match = re.search(r'"subject"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
    body_match = re.search(r'"body"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned, re.DOTALL)
    if subj_match and body_match:
        return {
            "subject": subj_match.group(1).encode().decode("unicode_escape", errors="replace"),
            "body": body_match.group(1).encode().decode("unicode_escape", errors="replace"),
        }
    # Last resort: split first line as subject
    lines = cleaned.splitlines()
    subject = lines[0].strip().lstrip("#").strip() if lines else "Update from the hiring team"
    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else cleaned
    return {"subject": subject, "body": body}


SYSTEM_PROMPT_EMAIL = (
    "You are an HR communications assistant for AIcruit. "
    "Write professional, warm, concise candidate emails. "
    "Plain text only — no markdown, no asterisks, no bullet symbols other than dashes. "
    "Address the candidate by first name. Keep paragraphs short. "
    "Do not invent facts beyond what's provided. "
    "End with 'Best regards,' on its own line followed by '{Company} Hiring Team' "
    "(or 'The AIcruit Hiring Team' if no company is provided)."
)


_SCENARIO_GUIDANCE = {
    "shortlisted": (
        "Tone: congratulatory and encouraging. Inform the candidate they have been "
        "shortlisted for the {job_title} role. Briefly mention next steps (a recruiter "
        "will be in touch) and thank them for their interest."
    ),
    "interview_scheduled": (
        "Tone: warm and informative. Congratulate the candidate on advancing to the "
        "interview stage for the {job_title} role. Mention the scheduled date and time "
        "({scheduled_at}). Provide a one-line note that the interview link will follow "
        "(use the literal placeholder {{interview_link}} where the link will appear). "
        "Keep instructions brief: have your environment ready, test your mic and camera."
    ),
    "stage_advance": (
        "Tone: positive and encouraging. Tell the candidate they have advanced to the "
        "{stage_name} stage for the {job_title} role. Mention what to expect at this stage "
        "and that the team will reach out with details soon."
    ),
    "rejection": (
        "Tone: respectful, kind, and clearly final. Thank the candidate for their time "
        "and effort. State plainly that they have not been selected for the {job_title} "
        "role at this time, without vague hedging. Wish them well."
    ),
    "offer": (
        "Tone: enthusiastic and professional. Extend the offer for the {job_title} role. "
        "Mention that a formal offer letter with full details will follow. Encourage them "
        "to reach out with any questions."
    ),
    "custom": (
        "Follow the custom instructions exactly. {custom_instructions}"
    ),
}


@app.post("/draft-email")
async def draft_email(req: DraftEmailRequest):
    """
    Generate a candidate email subject + body using Gemini.
    Returns: {"subject": str, "body": str}
    """
    try:
        scenario = (req.scenario or "custom").strip().lower()
        guidance_template = _SCENARIO_GUIDANCE.get(scenario, _SCENARIO_GUIDANCE["custom"])

        # Format guidance with available fields
        guidance = guidance_template.format(
            job_title=req.job_title or "the role",
            scheduled_at=req.scheduled_at or "the scheduled time",
            stage_name=req.stage_name or "the next stage",
            custom_instructions=req.custom_instructions or "",
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

        user_prompt = (
            f"Scenario: {scenario}\n"
            f"Guidance: {guidance}\n\n"
            f"Context:\n" + "\n".join(context_lines) + "\n\n"
            f"Write the email now.{extra_rules}\n\n"
            "Return STRICT JSON with exactly these keys and no others, "
            "no markdown fences, no commentary:\n"
            '{"subject": "<one-line subject>", "body": "<plain text body with \\n line breaks>"}'
        )

        chat = get_default_chat()
        result = chat.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_EMAIL},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=900,
        )
        text = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = _parse_email_json(text)
        if not parsed.get("subject") or not parsed.get("body"):
            raise ValueError("LLM returned empty subject or body")
        return parsed

    except Exception as e:
        logger.error(f"draft-email failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Email drafting failed: {e}")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "interview-question-generation"}


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="localhost", port=8010)
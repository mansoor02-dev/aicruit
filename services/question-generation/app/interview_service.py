# app/interview_service.py
from typing import Dict, Any
from uuid import uuid4
from pipelines.conversation_manager import ConversationManager
from pipelines.flow_controller import FlowController
from pipelines.question_generator import QuestionGenerator
from pipelines.answer_evaluator import AnswerEvaluator
from pipelines.llm_loader import LLMLoader
from sentence_transformers import SentenceTransformer
from app.db import InterviewDB
import csv
from pathlib import Path

# ==== Singletons ====
llm = LLMLoader().get_llm()
embedder = SentenceTransformer("all-MiniLM-L6-v2")
evaluator = AnswerEvaluator(embedder, llm)
flow_controller = FlowController(max_followups_per_topic=2)

dataset_path = Path("data/software_questions.csv")
with open(dataset_path) as f:
    dataset = list(csv.DictReader(f))

# In-memory sessions
sessions: Dict[str, Dict] = {}

async def create_session(interview_id: str, resume_id: str, job_description: str):
    session_id = str(uuid4())[:8]

    # Fetch resume
    resume_json = await InterviewDB.get_resume_by_id(resume_id)
    if not resume_json:
        raise ValueError("Resume not found")
    resume_text = str(resume_json)

    # Create AI session linked to your real interview
    await InterviewDB.create_ai_session(
        interview_id=interview_id,
        session_id=session_id,
        resume_id=resume_id,
        job_description=job_description
    )

    generator = QuestionGenerator(
        llm=llm,
        dataset_questions=dataset,
        candidate_resume=resume_text,
        job_description=job_description
    )
    conversation = ConversationManager(total_questions=5)

    q, meta = generator.generate_new_topic_question(topics_covered=[], difficulty="medium")

    sessions[session_id] = {
        "conversation": conversation,
        "generator": generator,
        "current_question": q,
        "current_metadata": meta,
        "is_followup": False
    }

    return {
        "session_id": session_id,
        "question": q,
        "is_followup": False,
        "progress": {"questions_asked": 0, "total": 5}
    }

async def get_next_question(session_id: str, answer: str) -> Dict[str, Any]:
    if session_id not in sessions:
        raise ValueError("Invalid session")

    sess = sessions[session_id]
    conv: ConversationManager = sess["conversation"]
    gen: QuestionGenerator = sess["generator"]

    # ── Evaluate previous answer ──
    evaluation = evaluator.evaluate(
        question=sess["current_question"],
        user_answer=answer,
        reference_answer=sess["current_metadata"].get("reference_answer"),
        is_followup=sess["is_followup"]
    )

    # ── Record turn in memory + DB ──
    conv.add_turn(
        question=sess["current_question"],
        answer=answer,
        evaluation=evaluation,
        is_followup=sess["is_followup"],
        topic=sess["current_metadata"].get("category"),
        metadata=sess["current_metadata"]
    )

    turn_number = len(conv.history)
    await InterviewDB.add_turn(
        session_id=session_id,
        turn_number=turn_number,
        question=sess["current_question"],
        user_answer=answer,
        is_followup=sess["is_followup"],
        topic=sess["current_metadata"].get("category"),
        depth_score=evaluation["depth_score"],
        pass_val=evaluation["pass"],
        confidence=evaluation["confidence"],
        feedback=evaluation["feedback"]
    )

    # ── Decide next action ──
    decision = flow_controller.decide_next_action(
        evaluation=evaluation,
        topic_depth=conv.get_current_topic_depth(),
        questions_asked=conv.get_questions_asked(),
        total_questions=5,
        topics_covered=conv.get_topics_covered_list()
    )

    # ── End of interview? ──
    if decision.action == "end":
        await InterviewDB.end_ai_session(session_id)
        del sessions[session_id]
        return {
            "status": "complete",
            "message": "Interview completed!",
            "summary": conv.get_performance_summary(),
            "full_log": conv.to_dict()
        }

    # ── Generate next question ──
    if decision.action == "new_topic":
        q, meta = gen.generate_new_topic_question(
            topics_covered=conv.get_topics_covered_list(),
            difficulty="medium"
        )
        is_followup = False
    else:  # followup
        last_turn = conv.get_last_turn()
        angle = decision.suggested_angle or "elaboration"
        q, meta = gen.generate_followup_question(
            previous_question=last_turn.question,
            previous_answer=answer,
            followup_angle=angle,
            evaluation=evaluation
        )
        meta["is_followup"] = True
        is_followup = True

    # ── Update session ──
    sess["current_question"] = q
    sess["current_metadata"] = meta
    sess["is_followup"] = is_followup

    return {
        "session_id": session_id,
        "question": q,
        "is_followup": is_followup,
        "evaluation": evaluation,
        "progress": {
            "questions_asked": conv.get_questions_asked(),
            "total": 5
        }
    }
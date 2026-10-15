import asyncio
import json
import random
from datetime import datetime
from pathlib import Path

import pandas as pd

import sys
sys.path.append(str(Path(__file__).parent.parent))

from app.config import Settings
from app.graph.nodes import QuestionGraphNodes
from app.llm.chains import build_chains
from app.llm.embeddings import EmbeddingProvider
from app.llm.models import make_chat_models
from app.pipelines.conversation_manager import ConversationManager
from app.pipelines.flow_controller import FlowController
from app.services.dataset import DatasetRepository
from app.services.text import is_valid_followup


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class Config:
    BASE_DIR  = Path(__file__).resolve().parents[1]
    CSV_PATH  = BASE_DIR / "data" / "software_questions.csv"
    LOGS_DIR  = BASE_DIR / "logs"

    TOTAL_QUESTIONS = 3
    MAX_FOLLOWUPS   = 1
    DIFFICULTY      = "medium"

    @classmethod
    def ensure_dirs(cls) -> None:
        cls.LOGS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_questions(csv_path: Path) -> list:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    print(f"Loading questions from {csv_path.name}…")
    try:
        df = pd.read_csv(csv_path, encoding="latin1")
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding="utf-8", errors="ignore")

    questions = [
        {
            "id":         int(row.get("Question Number", idx + 1)),
            "question":   str(row.get("Question", "")).strip(),
            "answer":     str(row.get("Answer", "")).strip(),
            "category":   str(row.get("Category", "General")).strip(),
            "difficulty": str(row.get("Difficulty", "medium")).strip().lower(),
        }
        for idx, row in df.iterrows()
    ]
    print(f"   Loaded {len(questions)} questions")
    return questions


# ---------------------------------------------------------------------------
# Interview loop
# ---------------------------------------------------------------------------

async def run_interview() -> None:
    Config.ensure_dirs()

    print("=" * 70)
    print(" " * 20 + "REALISTIC INTERVIEW SYSTEM")
    print("=" * 70)

    # --- Initialisation ---
    questions = load_questions(Config.CSV_PATH)

    print("\nInitialising interview components…")
    settings    = Settings.from_env()
    models      = make_chat_models(settings)
    embeddings  = EmbeddingProvider(settings)
    chains      = build_chains(models, settings, embeddings)
    dataset     = DatasetRepository(
        [
            {
                "Id":         q["id"],
                "Question":   q["question"],
                "Answer":     q["answer"],
                "Category":   q["category"],
                "Difficulty": q["difficulty"],
            }
            for q in questions
        ]
    )
    nodes = QuestionGraphNodes(
        chains=chains,
        dataset=dataset,
        settings=settings,
        rng=random.Random(),
    )
    conversation    = ConversationManager(total_questions=Config.TOTAL_QUESTIONS)
    flow_controller = FlowController(max_followups_per_topic=Config.MAX_FOLLOWUPS)
    print("✓ All components ready\n")

    print("=" * 70)
    print(" " * 25 + "INTERVIEW STARTED")
    print("=" * 70)
    print("\nType 'quit' or 'exit' to end the interview early\n")

    turn_number = 0

    while not conversation.is_complete():
        turn_number += 1
        last_turn = conversation.get_last_turn()

        # --- Decide: follow-up or new topic? ---
        decision = flow_controller.decide_next_action(
            evaluation=last_turn.evaluation if last_turn else {},
            topic_depth=conversation.get_current_topic_depth(),
            questions_asked=conversation.get_questions_asked(),
            total_questions=Config.TOTAL_QUESTIONS,
            topics_covered=conversation.get_topics_covered_list(),
        )

        if decision.action == "end":
            print(f"\n✓ {decision.reason}")
            break

        # --- Generate question ---
        is_followup = decision.action == "followup"

        if is_followup:
            followup_state = {
                "previous_qa_list": [
                    {"Q": last_turn.question, "A": last_turn.answer}
                ],
                "flow": {
                    "decision": (last_turn.evaluation or {}).get(
                        "flow_decision", "same_topic"
                    ),
                    "score_value": (last_turn.evaluation or {}).get(
                        "depth_score", 0.5
                    ),
                    "remarks": "",
                    "feedback": (last_turn.evaluation or {}).get("feedback", ""),
                },
                "resume_json": {},
                "difficulty": Config.DIFFICULTY,
                "category": last_turn.topic,
            }
            generated = await nodes.generate_followup(followup_state)
            question_text, metadata = generated["question"], generated["metadata"]
            if not is_valid_followup(question_text, last_turn.answer):
                fallback = nodes.followup_template_fallback(
                    {**followup_state, "candidate": question_text}
                )
                question_text, metadata = fallback["question"], fallback["metadata"]
            topic = last_turn.topic
        else:
            new_topic_state = {
                "previous_qa_list": [
                    {"Q": t.question, "A": t.answer, "category": t.topic}
                    for t in conversation.history
                ],
                "difficulty": Config.DIFFICULTY,
                "resume_json": {},
                "category": None,
            }
            generated = await nodes.generate_new_topic(new_topic_state)
            question_text, metadata = generated["question"], generated["metadata"]
            topic = metadata.get("category", "General")

        # --- Display question ---
        marker = "FOLLOW-UP" if is_followup else "NEW TOPIC"
        print(f"\n{'─' * 70}")
        print(f"{marker} | Turn #{turn_number} | Topic: {topic}")
        print(f"{'─' * 70}")
        print(f"\n❓ {question_text}\n")

        # --- Get answer ---
        user_answer = input("Your answer > ").strip()
        if user_answer.lower() in ("quit", "exit", "q"):
            print("\nEnding interview early…")
            break
        if not user_answer:
            print("Empty answer — please try again.\n")
            turn_number -= 1
            continue

        # --- Single combined evaluation call (score + flow decision) ---
        print("\nEvaluating your answer…")
        evaluation, flow = await chains.evaluation.ainvoke(
            {
                "question": question_text,
                "user_answer": user_answer,
                "reference_answer": metadata.get("reference_answer"),
                "is_followup": is_followup,
            }
        )

        # Inject flow decision into evaluation so FlowController can use it
        # on the next iteration (same shape as before)
        evaluation["flow_decision"] = flow.get("decision", "new_topic")

        # --- Show feedback ---
        status = "✓ PASS" if evaluation["pass"] else "✗ NEEDS WORK"
        print(f"\n{'═' * 70}")
        print(f"{status}")
        print(f"Depth Score: {evaluation['depth_score']:.2f}/1.00")
        print(f"Confidence:  {evaluation['confidence']:.2f}")
        print(f"Feedback:    {evaluation['feedback']}")
        print(f"{'═' * 70}")

        # --- Record ---
        conversation.add_turn(
            question=question_text,
            answer=user_answer,
            evaluation=evaluation,
            is_followup=is_followup,
            topic=topic,
            metadata=metadata,
        )

        perf = conversation.get_performance_summary()
        print(
            f"\nProgress: {perf['questions_asked']}/{Config.TOTAL_QUESTIONS} questions | "
            f"Score: {perf['score']:.1f}/{perf['max_score']:.1f} ({perf['percentage']}%)"
        )

    # --- Wrap-up ---
    print("\n" + "=" * 70)
    print(" " * 25 + "INTERVIEW COMPLETE")
    print("=" * 70)
    conversation.print_summary()

    log_file = Config.LOGS_DIR / f"interview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    session_data = conversation.to_dict()
    session_data["metadata"] = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "total_questions": Config.TOTAL_QUESTIONS,
            "max_followups":   Config.MAX_FOLLOWUPS,
            "difficulty":      Config.DIFFICULTY,
        },
    }
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2, ensure_ascii=False)

    print(f"Session saved to: {log_file.name}\n")
    print("=" * 70)
    print(" " * 20 + "Thank you for interviewing!")
    print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(run_interview())
    except KeyboardInterrupt:
        print("\n\nInterview interrupted by user (Ctrl+C)")
    except Exception as e:
        import traceback
        print(f"\nError: {e}")
        traceback.print_exc()
import json
import pickle
from datetime import datetime
from pathlib import Path

import faiss
import numpy as np
import pandas as pd


import sys
sys.path.append(str(Path(__file__).parent.parent))

from pipelines.answer_evaluator import AnswerEvaluator
from pipelines.llm_loader import get_embedder
from pipelines.conversation_manager import ConversationManager
from pipelines.flow_controller import FlowController
from pipelines.question_generator import QuestionGenerator


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class Config:
    BASE_DIR     = Path(__file__).resolve().parents[1]
    CSV_PATH     = BASE_DIR / "data" / "software_questions.csv"
    CACHE_DIR    = BASE_DIR / "cache"
    INDEX_PATH   = CACHE_DIR / "questions.index"
    PASSAGES_PKL = CACHE_DIR / "passages.pkl"
    LOGS_DIR     = BASE_DIR / "logs"

    EMBED_MODEL     = "all-MiniLM-L6-v2"
    TOTAL_QUESTIONS = 3
    MAX_FOLLOWUPS   = 1
    DIFFICULTY      = "medium"

    @classmethod
    def ensure_dirs(cls) -> None:
        cls.CACHE_DIR.mkdir(exist_ok=True)
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


def build_or_load_index(questions: list, embedder: get_embedder(Config.EMBED_MODEL)) -> tuple:
    if Config.INDEX_PATH.exists() and Config.PASSAGES_PKL.exists():
        try:
            index = faiss.read_index(str(Config.INDEX_PATH))
            with open(Config.PASSAGES_PKL, "rb") as f:
                passages = pickle.load(f)
            if index.ntotal == len(passages) == len(questions):
                print(f"✓ Loaded cached index ({index.ntotal} vectors)")
                return index, passages
        except Exception as e:
            print(f"Cache invalid ({e}), rebuilding…")

    print("Building FAISS index…")
    passages = [
        {
            "id": q["id"], "question": q["question"], "answer": q["answer"],
            "category": q["category"], "difficulty": q["difficulty"],
        }
        for q in questions
    ]
    texts      = [f"{p['question']} {p['answer']}" for p in passages]
    embeddings = embedder.encode(
        texts, batch_size=64, show_progress_bar=True,
        convert_to_numpy=True, normalize_embeddings=True,
    ).astype(np.float32)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    faiss.write_index(index, str(Config.INDEX_PATH))
    with open(Config.PASSAGES_PKL, "wb") as f:
        pickle.dump(passages, f)

    print(f"✓ Built index with {index.ntotal} vectors")
    return index, passages


# ---------------------------------------------------------------------------
# Interview loop
# ---------------------------------------------------------------------------

def run_interview() -> None:
    Config.ensure_dirs()

    print("=" * 70)
    print(" " * 20 + "REALISTIC INTERVIEW SYSTEM")
    print("=" * 70)

    # --- Initialisation ---
    questions = load_questions(Config.CSV_PATH)

    print(f"\nLoading embedding model: {Config.EMBED_MODEL}")
    embedder = get_embedder(Config.EMBED_MODEL)

    build_or_load_index(questions, embedder)   # warm the cache

    print("\nInitialising interview components…")
    conversation    = ConversationManager(total_questions=Config.TOTAL_QUESTIONS)
    flow_controller = FlowController(max_followups_per_topic=Config.MAX_FOLLOWUPS)
    question_gen    = QuestionGenerator(model_type="openrouter", dataset_questions=questions)
    evaluator       = AnswerEvaluator(embedder=embedder, model_type="openrouter")
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
            question_text, metadata = question_gen.generate_followup_question(
                previous_question=last_turn.question,
                previous_answer=last_turn.answer,
                evaluation_result=last_turn.evaluation,
            )
            topic = last_turn.topic
        else:
            question_text, metadata = question_gen.generate_new_topic_question(
                topics_covered=conversation.get_topics_covered_list(),
                difficulty=Config.DIFFICULTY,
            )
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
        evaluation, flow = evaluator.evaluate_combined(
            question=question_text,
            user_answer=user_answer,
            reference_answer=metadata.get("reference_answer"),
            is_followup=is_followup,
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
        run_interview()
    except KeyboardInterrupt:
        print("\n\nInterview interrupted by user (Ctrl+C)")
    except Exception as e:
        import traceback
        print(f"\nError: {e}")
        traceback.print_exc()
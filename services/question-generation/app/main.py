import json
import pickle
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

import sys
sys.path.append(str(Path(__file__).parent.parent))


from pipelines.llm_loader import LLMLoader
from pipelines.conversation_manager import ConversationManager
from pipelines.flow_controller import FlowController
from pipelines.question_generator import QuestionGenerator
from pipelines.answer_evaluator import AnswerEvaluator


# ========== CONFIGURATION ==========
class Config:
    """Centralized configuration"""
    
    BASE_DIR = Path(__file__).resolve().parents[1]
    # points to: services/question-generation/

    # Paths
    CSV_PATH = BASE_DIR / "data" / "software_questions.csv"
    CACHE_DIR = BASE_DIR / "cache"
    INDEX_PATH = CACHE_DIR / "questions.index"
    PASSAGES_PKL = CACHE_DIR / "passages.pkl"
    LOGS_DIR = BASE_DIR / "logs"

    # Models
    LLM_PATH = BASE_DIR / "models" / "llm" / "Phi-3-mini-4k-instruct-q4.gguf"
    # Models
    EMBED_MODEL = "all-MiniLM-L6-v2"
    
    # LLM Settings
    N_CTX = 2048
    N_THREADS = 4
    N_BATCH = 512
    
    # Interview Settings
    TOTAL_QUESTIONS = 3  # Main questions (not counting follow-ups)
    MAX_FOLLOWUPS_PER_TOPIC = 1
    DIFFICULTY = "medium"  # Can be made dynamic later
    
    @classmethod
    def ensure_dirs(cls):
        """Create necessary directories"""
        cls.CACHE_DIR.mkdir(exist_ok=True)
        cls.LOGS_DIR.mkdir(exist_ok=True)


# ========== DATA LOADING ==========
def load_questions_from_csv(csv_path: Path) -> list:
    """
    Load questions from CSV with robust parsing
    
    Expected columns: Question Number, Question, Answer, Category, Difficulty
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    
    print(f"Loading questions from {csv_path.name}...")
    
    try:
        df = pd.read_csv(csv_path, encoding="latin1")
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding="utf-8", errors="ignore")
    
    questions = []
    for idx, row in df.iterrows():
        questions.append({
            "id": int(row.get("Question Number", idx + 1)),
            "question": str(row.get("Question", "")).strip(),
            "answer": str(row.get("Answer", "")).strip(),
            "category": str(row.get("Category", "General")).strip(),
            "difficulty": str(row.get("Difficulty", "medium")).strip().lower()
        })
    
    print(f"   Loaded {len(questions)} questions")
    return questions


def build_or_load_index(questions: list, embedder: SentenceTransformer) -> tuple:
    # Check cache
    if Config.INDEX_PATH.exists() and Config.PASSAGES_PKL.exists():
        try:
            index = faiss.read_index(str(Config.INDEX_PATH))
            with open(Config.PASSAGES_PKL, "rb") as f:
                passages = pickle.load(f)
            
            if index.ntotal == len(passages) == len(questions):
                print(f"✓ Loaded cached index ({index.ntotal} vectors)")
                return index, passages
        except Exception as e:
            print(f"Cache load failed: {e}, rebuilding...")
    
    print(f"Building FAISS index...")
    
    # Prepare passages
    passages = []
    for q in questions:
        text = f"{q['question']} {q['answer']}"
        passages.append({
            "id": q["id"],
            "text": text,
            "question": q["question"],
            "answer": q["answer"],
            "category": q["category"],
            "difficulty": q["difficulty"]
        })
    
    # Create embeddings
    texts = [p["text"] for p in passages]
    embeddings = embedder.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True
    )
    embeddings = embeddings.astype(np.float32)
    
    # Build index
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    
    # Cache
    faiss.write_index(index, str(Config.INDEX_PATH))
    with open(Config.PASSAGES_PKL, "wb") as f:
        pickle.dump(passages, f)
    
    print(f"✓ Built index with {index.ntotal} vectors")
    return index, passages


# ========== MAIN INTERVIEW LOOP ==========
def run_interview():  
    Config.ensure_dirs()
    
    print("=" * 70)
    print(" " * 20 + "REALISTIC INTERVIEW SYSTEM")
    print("=" * 70)
    print()
    
    # ========== INITIALIZATION ==========
    print("Initializing components...\n")
    
    # Load data
    questions = load_questions_from_csv(Config.CSV_PATH)
    
    # Load embedding model
    print(f"Loading embedding model: {Config.EMBED_MODEL}")
    embedder = SentenceTransformer(Config.EMBED_MODEL, device='cpu')
    embedder.max_seq_length = 128
    
    # Build/load index
    index, passages = build_or_load_index(questions, embedder)
    # Load LLM
    print(f"\n🤖 Loading LLM: {Config.LLM_PATH.name}")
    if not Config.LLM_PATH.exists():
        print(f"Model not found: {Config.LLM_PATH}")
        return
    print(f"✓ LLM loaded")
    
    # Initialize components
    print("\n🎯 Initializing interview components...")
    conversation = ConversationManager(total_questions=Config.TOTAL_QUESTIONS)
    flow_controller = FlowController(max_followups_per_topic=Config.MAX_FOLLOWUPS_PER_TOPIC)
    question_gen = QuestionGenerator(model_type="openrouter", dataset_questions=questions)
    evaluator = AnswerEvaluator(embedder=embedder, model_type="openrouter")
    
    print("✓ All components ready\n")
    
    # ========== INTERVIEW START ==========
    print("=" * 70)
    print(" " * 25 + "🚀 INTERVIEW STARTED")
    print("=" * 70)
    print("\n💡 Type 'quit' or 'exit' to end interview early\n")
    
    turn_number = 0
    
    while not conversation.is_complete():
        turn_number += 1
        
        # ========== STEP 1: DECIDE ACTION (Follow-up or New Topic) ==========
        last_turn = conversation.get_last_turn()
        
        if last_turn:
            # We have history - decide what to do next
            decision = flow_controller.decide_next_action(
                evaluation=last_turn.evaluation,
                topic_depth=conversation.get_current_topic_depth(),
                questions_asked=conversation.get_questions_asked(),
                total_questions=Config.TOTAL_QUESTIONS,
                topics_covered=conversation.get_topics_covered_list()
            )
            
            if decision.action == "end":
                print(f"\n✓ {decision.reason}")
                break
        else:
            # First question - must be new topic
            decision = flow_controller.decide_next_action(
                evaluation={},
                topic_depth=0,
                questions_asked=0,
                total_questions=Config.TOTAL_QUESTIONS,
                topics_covered=[]
            )
        
        # ========== STEP 2: GENERATE QUESTION ==========
        is_followup = (decision.action == "followup")
        
        if is_followup:
            # Generate follow-up based on previous Q&A
            question_text, metadata = question_gen.generate_followup_question(
                previous_question=last_turn.question,
                previous_answer=last_turn.answer,
                evaluation_result=last_turn.evaluation
            )
            topic = last_turn.topic
        else:
            # Generate new topic question
            question_text, metadata = question_gen.generate_new_topic_question(
                topics_covered=conversation.get_topics_covered_list(),
                difficulty=Config.DIFFICULTY
            )
            topic = metadata.get("category", "General")
        
        # ========== STEP 3: DISPLAY QUESTION ==========
        print(f"\n{'─' * 70}")
        marker = "🔄 FOLLOW-UP" if is_followup else "🆕 NEW TOPIC"
        print(f"{marker} | Turn #{turn_number} | Topic: {topic}")
        print(f"{'─' * 70}")
        print(f"\n❓ {question_text}\n")
        
        # ========== STEP 4: GET USER ANSWER ==========
        user_answer = input("💬 Your answer > ").strip()
        
        # Handle exit
        if user_answer.lower() in ("quit", "exit", "q"):
            print("\n👋 Ending interview early...")
            break
        
        # Handle empty
        if not user_answer:
            print("⚠️ Empty answer. Please provide an answer.\n")
            turn_number -= 1
            continue
        
        # ========== STEP 5: EVALUATE ANSWER ==========
        print("\n⏳ Evaluating your answer...")
        
        evaluation = evaluator.evaluate(
            question=question_text,
            user_answer=user_answer,
            reference_answer=metadata.get("reference_answer"),
            is_followup=is_followup
        )
        
        # ========== STEP 6: SHOW FEEDBACK ==========
        print(f"\n{'═' * 70}")
        print(" " * 28 + "📊 EVALUATION")
        print(f"{'═' * 70}")
        
        status = "✓ PASS" if evaluation["pass"] else "✗ NEEDS WORK"
        print(f"\n{status}")
        print(f"Depth Score: {evaluation['depth_score']:.2f}/1.00")
        print(f"Confidence: {evaluation['confidence']:.2f}")
        print(f"Feedback: {evaluation['feedback']}")
        print(f"\n{'═' * 70}")
        
        # ========== STEP 7: RECORD TURN ==========
        conversation.add_turn(
            question=question_text,
            answer=user_answer,
            evaluation=evaluation,
            is_followup=is_followup,
            topic=topic,
            metadata=metadata
        )
        
        # Show progress
        perf = conversation.get_performance_summary()
        print(f"\n📈 Progress: {perf['questions_asked']}/{Config.TOTAL_QUESTIONS} questions | "
              f"Score: {perf['score']:.1f}/{perf['max_score']:.1f} ({perf['percentage']}%)")
    
    # ========== INTERVIEW COMPLETE ==========
    print("\n" + "=" * 70)
    print(" " * 25 + "✅ INTERVIEW COMPLETE")
    print("=" * 70)
    
    # Show final summary
    conversation.print_summary()
    
    # ========== SAVE LOG ==========
    log_file = Config.LOGS_DIR / f"interview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    session_data = conversation.to_dict()
    session_data["metadata"] = {
        "timestamp": datetime.now().isoformat(),
        "model": Config.LLM_PATH.name,
        "config": {
            "total_questions": Config.TOTAL_QUESTIONS,
            "max_followups": Config.MAX_FOLLOWUPS_PER_TOPIC,
            "difficulty": Config.DIFFICULTY
        }
    }
    
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Session saved to: {log_file.name}\n")
    
    print("=" * 70)
    print(" " * 20 + "Thank you for interviewing! 🎉")
    print("=" * 70 + "\n")


# ========== ENTRY POINT ==========
if __name__ == "__main__":
    try:
        run_interview()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interview interrupted by user (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ Error occurred: {e}")
        import traceback
        traceback.print_exc()
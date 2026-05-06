import json
import random
import re
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, "/app")

from shared.llm_client import LLMClient
from pipelines.llm_loader import LLMLoader, get_default_chat

_FOLLOWUP_ANGLE_MAP = {
    "deep_dive": "implementation_details",
    "same_topic": "elaboration",
}

_ANGLE_GOAL = {
    "elaboration":           "Get more detail and depth from their answer.",
    "clarification":         "Clarify vague or ambiguous points.",
    "examples":              "Request concrete examples or use cases.",
    "implementation_details":"Probe how they would actually implement or apply this.",
    "tradeoffs":             "Explore alternatives, trade-offs, or limitations.",
    "edge_cases":            "Test handling of edge cases or failure scenarios.",
}

_FALLBACK_TEMPLATES: Dict[str, List[str]] = {
    "elaboration": [
        "Can you walk me through a specific example from your experience where you applied {topic}?",
        "What trade-offs did you weigh the last time you used {topic} in a real project?",
        "What's the most common mistake you've seen others make with {topic}, and how would you avoid it?",
    ],
    "clarification": [
        "Can you walk me through a specific example from your experience where you applied {topic}?",
        "What trade-offs did you weigh the last time you used {topic} in a real project?",
        "What's the most common mistake you've seen others make with {topic}, and how would you avoid it?",
    ],
    "examples": [
        "Can you walk me through a specific example from your experience where you applied {topic}?",
        "What trade-offs did you weigh the last time you used {topic} in a real project?",
        "What's the most common mistake you've seen others make with {topic}, and how would you avoid it?",
    ],
    "implementation_details": [
        "Can you walk me through a specific example from your experience where you applied {topic}?",
        "What trade-offs did you weigh the last time you used {topic} in a real project?",
        "What's the most common mistake you've seen others make with {topic}, and how would you avoid it?",
    ],
    "tradeoffs": [
        "Can you walk me through a specific example from your experience where you applied {topic}?",
        "What trade-offs did you weigh the last time you used {topic} in a real project?",
        "What's the most common mistake you've seen others make with {topic}, and how would you avoid it?",
    ],
    "edge_cases": [
        "Can you walk me through a specific example from your experience where you applied {topic}?",
        "What trade-offs did you weigh the last time you used {topic} in a real project?",
        "What's the most common mistake you've seen others make with {topic}, and how would you avoid it?",
    ],
}

_CONVERSATIONAL_PREFIXES = ["", "I'd like to know: "]

_DIFFICULTY_GUIDANCE = {
    "easy":   "easy difficulty â€” single-concept, simple vocabulary, max 15 words, no compound parts",
    "medium": "medium difficulty â€” requires brief explanation, max 20 words, 1-2 parts at most",
    "hard":   "hard difficulty â€” probes deep understanding or trade-offs, max 25 words",
}

_DIFFICULTY_WORD_LIMIT = {
    "easy":   10,
    "medium": 15,
    "hard":   20,
}


class QuestionGenerator:
    """Generates interview questions â€” new topics and contextual follow-ups."""

    def __init__(
        self,
        dataset_questions: List[Dict],
        model_type: str = "gemini",
        difficulty: str = "medium",
    ):
        self.dataset = dataset_questions
        # Prefer Gemini via get_default_chat(); fall back to LLMLoader (which
        # also resolves to OpenRouter only when GEMINI_API_KEY is missing).
        try:
            self.llm = get_default_chat().create_chat_completion
        except Exception:
            self.llm = LLMLoader(model_type=model_type).get_llm()
        self.difficulty = difficulty
        self.used_question_ids: set = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_new_topic_question(
        self,
        topics_covered: Optional[List[str]] = None,
        difficulty: Optional[str] = None,
        resume_json: Optional[Dict] = None,
        category: Optional[str] = None,
    ) -> Tuple[str, Dict]:
        """
        Pick a question from the dataset (filtered by difficulty and optional
        category, avoiding already-covered topics), optionally personalising
        it via LLM when a resume is provided.
        """
        topics_covered = topics_covered or []
        difficulty = (difficulty or self.difficulty).lower()

        selected = self._pick_question(topics_covered, difficulty, category=category)

        base_q = selected.get("Question") or selected.get("question", "")
        if resume_json:
            question_text = self._generate_contextual_question(
                base_question=base_q,
                category=category or selected.get("Category", "Software Engineering"),
                resume_json=resume_json,
                difficulty=difficulty,
            )
            source = "dataset_inspired"
        else:
            question_text = self._maybe_rephrase(base_q)
            source = "dataset"

        metadata = {
            "source": source,
            "scenario": "new_question",
            "question_id": selected.get("Id"),
            "category": category or selected.get("Category", "Unknown"),
            "difficulty": selected.get("Difficulty", "medium"),
            "reference_answer": selected.get("Answer", ""),
            "is_followup": False,
        }
        return question_text, metadata

    def generate_followup_question(
        self,
        previous_question: str,
        previous_answer: str,
        evaluation_result: Optional[Dict] = None,
        resume_json: Optional[Dict] = None,
        difficulty: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> Tuple[str, Dict]:
        """
        Generate a contextual follow-up question using the LLM, with a
        topic-aware template fallback.
        """
        difficulty = (difficulty or self.difficulty).lower()
        decision = (evaluation_result or {}).get("decision", "same_topic").lower()
        angle = _FOLLOWUP_ANGLE_MAP.get(decision, "elaboration")

        system_prompt = self._followup_system_prompt(angle, resume_json, difficulty=difficulty, topic=topic)
        user_prompt = self._followup_user_prompt(
            previous_question, previous_answer, evaluation_result,
            difficulty=difficulty, topic=topic, resume_json=resume_json,
        )

        question_text = self._call_llm_for_question(system_prompt, user_prompt)

        # Validate; fall back to template if invalid
        if not self._is_valid_followup(question_text, previous_answer):
            template = random.choice(
                _FALLBACK_TEMPLATES.get(angle, _FALLBACK_TEMPLATES["elaboration"])
            )
            question_text = template.format(topic=topic or "this area")

        metadata = {
            "source": "llm_generated",
            "scenario": "question_with_same_category",
            "is_followup": True,
            "followup_angle": angle,
            "based_on_question": previous_question,
            "reference_answer": None,
        }
        return question_text, metadata

    def generate_introduction_question(
        self,
        resume_json: Optional[Dict] = None,
    ) -> Tuple[str, Dict]:
        """
        Generate a warm, personalised opening question for the very start of
        the interview (no history, no category).
        """
        name = ""
        if resume_json and isinstance(resume_json, dict):
            name = (
                resume_json.get("name")
                or resume_json.get("Name")
                or resume_json.get("personal_info", {}).get("name", "")
            )

        if name:
            question_text = f"Hi {name}, welcome! Could you please introduce yourself and walk me through your technical background?"
        else:
            question_text = "Welcome! Could you please introduce yourself and walk me through your technical background?"

        metadata = {
            "source": "introduction",
            "scenario": "1st_question",
            "question_id": None,
            "category": "Introduction",
            "difficulty": "easy",
            "reference_answer": "",
            "is_followup": False,
        }
        return question_text, metadata

    def generate_category_opener_question(
        self,
        category: str
    ) -> Tuple[str, Dict]:
        """
        Generate the FIRST question for a category â€” always a general, easy
        dataset question with no resume personalisation.  This warms the
        candidate up on the topic before contextual / resume-linked questions
        are introduced in the follow-on turns.
        """
        # Always use easy difficulty for the opener regardless of session difficulty
        selected = self._pick_question([], "easy", category=category)

        question_text = self._maybe_rephrase(
            selected.get("Question") or selected.get("question", "")
        )

        metadata = {
            "source": "dataset",
            "scenario": "new_question",
            "question_id": selected.get("Id"),
            "category": selected.get("Category", category),
            "difficulty": "easy",
            "reference_answer": selected.get("Answer", ""),
            "is_followup": False,
            "is_category_opener": True,
        }
        return question_text, metadata

    # ------------------------------------------------------------------
    # Dataset helpers
    # ------------------------------------------------------------------

    def _pick_question(
        self,
        topics_covered: List[str],
        difficulty: str,
        category: Optional[str] = None,
    ) -> Dict:
        """Select a question from the dataset, progressively relaxing constraints."""
        # Apply category filter as the base pool when provided
        if category:
            base_dataset = [
                q for q in self.dataset
                if q.get("Category", "").lower() == category.lower()
            ] or self.dataset  # fall back to full dataset if category not found
        else:
            base_dataset = self.dataset

        # Preferred: correct difficulty, not yet used
        pool = [
            q for q in base_dataset
            if q.get("Difficulty", "").lower() == difficulty
            and q.get("Id") not in self.used_question_ids
        ]

        # Relax used-question constraint if pool too small
        if len(pool) < 3:
            pool = [q for q in base_dataset if q.get("Difficulty", "").lower() == difficulty]

        # Relax difficulty if still empty
        if not pool:
            pool = [q for q in base_dataset if q.get("Id") not in self.used_question_ids]

        # Last resort: base dataset (category-filtered or full)
        if not pool:
            pool = base_dataset

        # Prefer topics not in the last 3 covered
        recent_topics = set(topics_covered[-3:])
        fresh = [q for q in pool if q.get("Category") not in recent_topics]
        selected = random.choice(fresh if fresh else pool)

        q_id = selected.get("Id")
        if q_id is not None:
            self.used_question_ids.add(q_id)

        return selected

    def _maybe_rephrase(self, question: str) -> str:
        """Add a conversational prefix ~40% of the time."""
        if random.random() < 0.4:
            prefix = random.choice(_CONVERSATIONAL_PREFIXES)
            return f"{prefix}{question}" if prefix else question
        return question

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------

    def _call_llm_for_question(self, system_prompt: str, user_prompt: str) -> str:
        """Call LLM and return cleaned question text, or empty string on failure."""
        try:
            response = self.llm(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_tokens=150,
            )
            raw = response["choices"][0]["message"]["content"].strip()
            return self._clean_question(raw)
        except Exception as e:
            print(f" LLM question generation failed: {e}")
            return ""

    def _generate_contextual_question(
        self, base_question: str, category: str, resume_json: Dict, difficulty: str = "medium"
    ) -> str:
        """Personalise a dataset question to the candidate's resume using the LLM."""
        resume_snippet = self._build_resume_snippet(resume_json)

        if not resume_snippet:
            return self._maybe_rephrase(base_question)

        word_limit = _DIFFICULTY_WORD_LIMIT.get(difficulty, 20)

        system_prompt = (
            "You are a senior technical interviewer at a top company. You ask "
            "precise, scenario-driven questions that test real understanding, "
            "not memorization. Output ONE question only — no preamble, no "
            "numbering, no 'Question:' prefix, no quotation marks, no markdown. "
            "Keep it under 40 words. Use the candidate's resume to make the "
            "question concrete (reference their skills/projects when natural). "
            "Aim for the requested difficulty."
        )
        user_prompt = (
            f"Base topic: {category}\n"
            f"Seed question (from question bank): {base_question}\n"
            f"Requested difficulty: {difficulty}\n\n"
            f"Candidate resume snapshot:\n{resume_snippet}\n\n"
            "Rewrite the seed question into a more relevant, sharper interview "
            "question on the same topic, contextualized to this candidate. "
            "Return ONLY the question text."
        )

        question_text = self._call_llm_for_question(system_prompt, user_prompt)

        if not question_text or len(question_text.split()) > word_limit + 25:
            return self._maybe_rephrase(base_question)

        return question_text

    @staticmethod
    def _build_resume_snippet(resume_json: Dict) -> str:
        """Extract skills, projects, and experience into a concise string for prompts."""
        parts: List[str] = []

        # Name
        name = resume_json.get("name") or resume_json.get("Name", "") or resume_json.get("personal_info", {}).get("name", "")
        if name:
            parts.append(f"Name: {name}")

        # Skills (try both cases)
        skills = resume_json.get("Skills") or resume_json.get("skills") or []
        if skills:
            parts.append(f"Skills: {', '.join(skills)}")

        # Projects
        projects = resume_json.get("projects") or resume_json.get("Projects") or []
        for proj in projects[:3]:
            title = proj.get("title", "")
            desc = proj.get("description", "")
            if isinstance(desc, list):
                desc = "; ".join(desc)
            if title:
                parts.append(f"Project â€“ {title}: {desc[:200]}")

        # Experience
        experience = resume_json.get("experience") or resume_json.get("Experience") or []
        for exp in experience[:3]:
            role = exp.get("role") or exp.get("title", "")
            company = exp.get("company", "")
            desc = exp.get("description", "")
            if isinstance(desc, list):
                desc = "; ".join(desc)
            if role:
                parts.append(f"Experience â€“ {role} at {company}: {desc[:200]}")

        return "\n".join(parts)

    def _followup_system_prompt(
        self,
        angle: str,
        resume_json: Optional[Dict],
        difficulty: str = "medium",
        topic: Optional[str] = None,
    ) -> str:
        return (
            "You are a senior technical interviewer conducting a deep-dive "
            "follow-up. Based on the candidate's last answer, ask ONE focused "
            "follow-up that probes a gap, asks for a concrete example, or pushes "
            "one level deeper into the topic. Do NOT change topic. Do NOT repeat "
            "what they said. Do NOT ask multiple questions. Output ONE question "
            "only — no preamble, no numbering, no 'Question:' prefix, no "
            "quotation marks, under 35 words. Make it specific enough that a "
            "vague answer is impossible."
        )

    def _followup_user_prompt(
        self,
        previous_question: str,
        previous_answer: str,
        evaluation_result: Optional[Dict],
        difficulty: str = "medium",
        topic: Optional[str] = None,
        resume_json: Optional[Dict] = None,
    ) -> str:
        parts = []
        if topic:
            parts.append(f"Topic: {topic}")
        parts.append(f"Original question: {previous_question}")
        parts.append(f"Candidate's last answer: {previous_answer}")

        if resume_json:
            snippet = self._build_resume_snippet(resume_json)
            if snippet:
                parts.append(f"Candidate resume snapshot:\n{snippet}")

        if evaluation_result:
            feedback = evaluation_result.get("feedback") or ""
            remarks = evaluation_result.get("remarks") or ""
            extras = []
            if feedback:
                extras.append(f"- Evaluator feedback: {feedback}")
            if remarks:
                extras.append(f"- Evaluator remarks: {remarks}")
            extras.append(
                f"- Decision: {evaluation_result.get('decision', 'unknown')} "
                f"(score {evaluation_result.get('score_value', 0.5):.2f})"
            )
            if extras:
                parts.append("Evaluation:\n" + "\n".join(extras))

        parts.append(
            f"Difficulty: {difficulty}.\n"
            "Generate the follow-up. Return ONLY the question text."
        )
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Text cleaning / validation
    # ------------------------------------------------------------------

    def _clean_question(self, text: str) -> str:
        text = text.strip()
        # Strip common preambles
        text = re.sub(r"^(Question|Follow-up|Q)\s*[:\-]\s*", "", text, flags=re.IGNORECASE).strip()
        # Strip surrounding quotes / backticks
        text = text.strip("`")
        if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
            text = text[1:-1].strip()
        # Strip stray leading markdown bullets / numbering
        text = re.sub(r"^(?:[-*]|\d+[\.)])\s+", "", text).strip()
        # Keep only the first sentence
        first = re.split(r"[.!?]", text)[0].strip()
        # Collapse duplicate trailing punctuation
        first = first.rstrip("?.! ")
        return first + "?" if first else first

    def _is_valid_followup(self, question: str, previous_answer: str) -> bool:
        if not question or len(question) < 10 or not question.endswith("?"):
            return False
        if len(question.split()) > 30:
            return False
        q_words = set(re.findall(r"\b\w{4,}\b", question.lower()))
        a_words = set(re.findall(r"\b\w{4,}\b", previous_answer.lower()))
        common = q_words & a_words
        return 1 <= len(common) <= 10
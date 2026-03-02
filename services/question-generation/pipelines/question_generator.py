import json
import random
import re
from typing import Dict, List, Optional, Tuple

from pipelines.llm_loader import LLMLoader

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
    "elaboration":            ["Can you elaborate on that?", "Can you explain that in more detail?", "Could you expand on your answer?"],
    "clarification":          ["What exactly do you mean by that?", "Can you clarify that point?", "Could you be more specific?"],
    "examples":               ["Can you give me a concrete example?", "What's a practical use case for this?", "Can you show how that would work in practice?"],
    "implementation_details": ["How would you actually implement that?", "Walk me through your approach step by step.", "What would the code look like?"],
    "tradeoffs":              ["What are the trade-offs of that approach?", "How does this compare to alternatives?", "What are the downsides?"],
    "edge_cases":             ["What could go wrong with that approach?", "How would you handle edge cases?", "What if the input is invalid?"],
}

_CONVERSATIONAL_PREFIXES = ["", "I'd like to know: "]

_DIFFICULTY_GUIDANCE = {
    "easy":   "easy difficulty — single-concept, simple vocabulary, max 15 words, no compound parts",
    "medium": "medium difficulty — requires brief explanation, max 20 words, 1-2 parts at most",
    "hard":   "hard difficulty — probes deep understanding or trade-offs, max 25 words",
}

_DIFFICULTY_WORD_LIMIT = {
    "easy":   10,
    "medium": 15,
    "hard":   20,
}


class QuestionGenerator:
    """Generates interview questions — new topics and contextual follow-ups."""

    def __init__(
        self,
        dataset_questions: List[Dict],
        model_type: str = "openrouter",
        difficulty: str = "medium",
    ):
        self.dataset = dataset_questions
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
    ) -> Tuple[str, Dict]:
        """
        Generate a contextual follow-up question using the LLM, with a
        template-based fallback.
        """
        difficulty = (difficulty or self.difficulty).lower()
        decision = (evaluation_result or {}).get("decision", "same_topic").lower()
        angle = _FOLLOWUP_ANGLE_MAP.get(decision, "elaboration")

        system_prompt = self._followup_system_prompt(angle, resume_json, difficulty=difficulty)
        user_prompt = self._followup_user_prompt(previous_question, previous_answer, evaluation_result, difficulty=difficulty)

        question_text = self._call_llm_for_question(system_prompt, user_prompt)

        # Validate; fall back to template if invalid
        if not self._is_valid_followup(question_text, previous_answer):
            question_text = random.choice(_FALLBACK_TEMPLATES.get(angle, _FALLBACK_TEMPLATES["elaboration"]))

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
        Generate the FIRST question for a category — always a general, easy
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

        difficulty_guide = _DIFFICULTY_GUIDANCE.get(difficulty, _DIFFICULTY_GUIDANCE["medium"])
        word_limit = _DIFFICULTY_WORD_LIMIT.get(difficulty, 20)

        system_prompt = (
            "You are a senior technical interviewer.\n"
            f"Difficulty level: {difficulty_guide}\n"
            "Your job is to ask questions that are SPECIFICALLY tied to the candidate's\n"
            "own projects, skills, or work experience — not generic textbook questions.\n\n"
            f"Candidate Background:\n{resume_snippet}"
        )
        user_prompt = (
            f"Base topic / question: {base_question}\n"
            f"Category: {category}\n"
            f"Difficulty: {difficulty}\n\n"
            "Generate ONE interview question that:\n"
            "- Directly references a specific project, skill, or experience from the candidate's resume\n"
            "- Asks HOW or WHERE they applied the concept, e.g. 'In your [project], how did you handle…'\n"
            f"- Is natural and conversational, strictly under {word_limit} words\n"
            "- Matches the difficulty level above exactly — do NOT make it harder\n"
            "- No preamble — just the question, ending with ?\n\n"
            "Question:"
        )

        question_text = self._call_llm_for_question(system_prompt, user_prompt)

        if not question_text or len(question_text.split()) > word_limit + 5:
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
                parts.append(f"Project – {title}: {desc[:200]}")

        # Experience
        experience = resume_json.get("experience") or resume_json.get("Experience") or []
        for exp in experience[:3]:
            role = exp.get("role") or exp.get("title", "")
            company = exp.get("company", "")
            desc = exp.get("description", "")
            if isinstance(desc, list):
                desc = "; ".join(desc)
            if role:
                parts.append(f"Experience – {role} at {company}: {desc[:200]}")

        return "\n".join(parts)

    def _followup_system_prompt(
        self, angle: str, resume_json: Optional[Dict], difficulty: str = "medium"
    ) -> str:
        resume_context = ""
        if resume_json:
            snippet = self._build_resume_snippet(resume_json)
            if snippet:
                resume_context = f"\nCandidate Background:\n{snippet}\n"

        goal = _ANGLE_GOAL.get(angle, "")
        difficulty_guide = _DIFFICULTY_GUIDANCE.get(difficulty, _DIFFICULTY_GUIDANCE["medium"])
        return (
            f"You are a senior technical interviewer.{resume_context}\n"
            f"Difficulty level for your question: {difficulty_guide}\n"
            "Your follow-up questions must be:\n"
            "- Directly relevant to the candidate's previous answer\n"
            "- Conversational and appropriately scoped to the difficulty level\n"
            "- Do NOT exceed the word limit implied by the difficulty level\n"
            f"{f'Goal: {goal}' if goal else ''}"
        )

    def _followup_user_prompt(
        self,
        previous_question: str,
        previous_answer: str,
        evaluation_result: Optional[Dict],
        difficulty: str = "medium",
    ) -> str:
        word_limit = _DIFFICULTY_WORD_LIMIT.get(difficulty, 20)
        parts = [
            f"Previous question: {previous_question}",
            f"Candidate's answer: {previous_answer}",
        ]
        if evaluation_result:
            parts.append(
                f"Evaluation:\n"
                f"- Decision: {evaluation_result.get('decision', 'unknown')}\n"
                f"- Score: {evaluation_result.get('score_value', 0.5):.2f}\n"
                f"- Remarks: {evaluation_result.get('remarks', '')}"
            )
        parts.append(
            "Generate ONE natural follow-up question that probes deeper.\n"
            "Rules:\n"
            "1. Directly related to the previous answer\n"
            f"2. Max {word_limit} words — strictly enforce this\n"
            "3. Conversational interview style\n"
            "4. No preamble — just the question\n"
            "5. End with ?\n\n"
            "Question:"
        )
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Text cleaning / validation
    # ------------------------------------------------------------------

    def _clean_question(self, text: str) -> str:
        text = re.sub(r"^(Question:|Follow-up:|Q:)\s*", "", text, flags=re.IGNORECASE).strip()
        # Keep only the first sentence
        first = re.split(r"[.!?]", text)[0].strip()
        return first + "?" if first and not first.endswith("?") else first

    def _is_valid_followup(self, question: str, previous_answer: str) -> bool:
        if not question or len(question) < 10 or not question.endswith("?"):
            return False
        if len(question.split()) > 30:
            return False
        q_words = set(re.findall(r"\b\w{4,}\b", question.lower()))
        a_words = set(re.findall(r"\b\w{4,}\b", previous_answer.lower()))
        common = q_words & a_words
        return 1 <= len(common) <= 10
"""Thin graph nodes: each returns a partial state update.

Nodes never mutate the input state and hold no per-request state. All LLM
work goes through the injected LCEL ``Chains``; dataset access goes through
the immutable ``DatasetRepository``.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Optional

from app.config import Settings
from app.llm.chains import Chains
from app.llm.models import LLMProviderError
from app.services import evaluation as eval_helpers
from app.services.dataset import DatasetRepository
from app.services.text import (
    build_resume_snippet,
    fallback_template_question,
    followup_angle,
    is_valid_followup,
    maybe_rephrase,
    word_limit,
)

from .edges import rejection_reason, select_pool_question
from .state import QuestionGraphState

logger = logging.getLogger(__name__)


class QuestionGraphNodes:
    """Node implementations closed over shared, stateless dependencies."""

    def __init__(
        self,
        chains: Chains,
        dataset: DatasetRepository,
        settings: Settings,
        rng: random.Random,
    ):
        self.chains = chains
        self.dataset = dataset
        self.settings = settings
        self.rng = rng

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def evaluate_answer(self, state: QuestionGraphState) -> dict[str, Any]:
        """Evaluate the latest answer; never raises (neutral on surprise)."""
        last_qa = self._last_qa(state)
        try:
            evaluation, flow = await self.chains.evaluation.ainvoke(
                {
                    "question": last_qa.get("Q", ""),
                    "user_answer": last_qa.get("A", ""),
                    "reference_answer": last_qa.get("reference_answer"),
                    "is_followup": last_qa.get("is_followup", False),
                }
            )
        except Exception:
            logger.warning("Evaluation chain failed; using neutral result", exc_info=True)
            evaluation, flow = eval_helpers.neutral_result()
        return {"evaluation": evaluation, "flow": flow}

    # ------------------------------------------------------------------
    # Recruiter pool (deterministic, no LLM)
    # ------------------------------------------------------------------

    def pick_pool_question(self, state: QuestionGraphState) -> dict[str, Any]:
        """Return the selected recruiter-pool question and its metadata."""
        chosen = select_pool_question(
            state.get("pool"),
            state.get("used_pool_questions"),
            state.get("category"),
        )
        if chosen is None:
            raise ValueError("Pool node requires an unused pool question")
        metadata: dict[str, Any] = {
            "source": "recruiter_pool",
            "scenario": "new_question",
            "question_id": None,
            "category": chosen.get("topic")
            or state.get("category")
            or "Unknown",
            "difficulty": state.get("difficulty", "medium"),
            "reference_answer": "",
            "is_followup": False,
            "evaluation": {},
        }
        if state.get("evaluation") or state.get("flow"):
            metadata["evaluation"] = self._evaluation_metadata(state)
        return {"question": chosen.get("question"), "metadata": metadata}

    # ------------------------------------------------------------------
    # No-history paths (no LLM)
    # ------------------------------------------------------------------

    def generate_introduction(self, state: QuestionGraphState) -> dict[str, Any]:
        """Warm, personalised opening question (no history, no category)."""
        resume = state.get("resume_json") or {}
        name = (
            resume.get("name")
            or resume.get("Name")
            or (resume.get("personal_info") or {}).get("name", "")
        )
        if name:
            question_text = (
                f"Hi {name}, welcome! Could you please introduce yourself "
                "and walk me through your technical background?"
            )
        else:
            question_text = (
                "Welcome! Could you please introduce yourself and walk me "
                "through your technical background?"
            )
        metadata: dict[str, Any] = {
            "source": "introduction",
            "scenario": "1st_question",
            "question_id": None,
            "category": "Introduction",
            "difficulty": "easy",
            "reference_answer": "",
            "is_followup": False,
        }
        return {"question": question_text, "metadata": metadata}

    def generate_category_opener(self, state: QuestionGraphState) -> dict[str, Any]:
        """First question for a category: always an easy dataset question."""
        category = state.get("category")
        if not category:
            raise ValueError("Category-opener node requires a category")
        selected = self.dataset.pick_question(
            [],
            "easy",
            category=category,
            exclude_ids=set(),
            rng=self.rng,
        )
        question_text = maybe_rephrase(
            selected.get("Question") or selected.get("question", ""), self.rng
        )
        metadata: dict[str, Any] = {
            "source": "dataset",
            "scenario": "new_question",
            "question_id": selected.get("Id"),
            "category": selected.get("Category", category),
            "difficulty": "easy",
            "reference_answer": selected.get("Answer", ""),
            "is_followup": False,
            "is_category_opener": True,
        }
        return {"question": question_text, "metadata": metadata}

    # ------------------------------------------------------------------
    # Follow-up path (LLM with retry loop + template fallback)
    # ------------------------------------------------------------------

    async def generate_followup(self, state: QuestionGraphState) -> dict[str, Any]:
        """Generate one follow-up candidate via the followup chain."""
        last_qa = self._last_qa(state)
        previous_answer = last_qa.get("A", "")
        attempts = state.get("attempts", 0) + 1

        previous_candidate = state.get("candidate") or ""
        reason = ""
        if previous_candidate and not is_valid_followup(
            previous_candidate, previous_answer
        ):
            reason = rejection_reason(previous_candidate, previous_answer)

        followup_error = False
        try:
            candidate = await self.chains.followup.ainvoke(
                {
                    "previous_question": last_qa.get("Q", ""),
                    "candidate_answer": previous_answer,
                    "evaluation_result": state.get("flow") or {},
                    "resume_snippet": build_resume_snippet(
                        state.get("resume_json")
                    ),
                    "difficulty": state.get("difficulty", "medium"),
                    "topic": state.get("category"),
                    "rejection_reason": reason,
                }
            )
        except Exception:
            logger.warning("Follow-up chain failed", exc_info=True)
            candidate = ""
            followup_error = True

        decision = (state.get("flow") or {}).get("decision", "same_topic")
        metadata: dict[str, Any] = {
            "source": "llm_generated",
            "scenario": "question_with_same_category",
            "is_followup": True,
            "followup_angle": followup_angle(decision),
            "based_on_question": last_qa.get("Q", ""),
            "reference_answer": None,
        }
        metadata["evaluation"] = self._evaluation_metadata(state)
        return {
            "candidate": candidate,
            "question": candidate,
            "metadata": metadata,
            "attempts": attempts,
            "followup_error": followup_error,
        }

    def followup_template_fallback(
        self, state: QuestionGraphState
    ) -> dict[str, Any]:
        """Topic-aware template question after exhausted follow-up retries."""
        last_qa = self._last_qa(state)
        topic = state.get("category")
        question_text = fallback_template_question(topic, self.rng)
        decision = (state.get("flow") or {}).get("decision", "same_topic")
        metadata: dict[str, Any] = {
            "source": "llm_generated",
            "scenario": "question_with_same_category",
            "is_followup": True,
            "followup_angle": followup_angle(decision),
            "based_on_question": last_qa.get("Q", ""),
            "reference_answer": None,
        }
        metadata["evaluation"] = self._evaluation_metadata(state)
        return {"question": question_text, "metadata": metadata}

    # ------------------------------------------------------------------
    # New-topic path (dataset pick + optional LLM personalisation)
    # ------------------------------------------------------------------

    async def generate_new_topic(self, state: QuestionGraphState) -> dict[str, Any]:
        """Dataset seed question, personalised via LLM when resume exists."""
        difficulty = (state.get("difficulty") or "medium").lower()
        category = state.get("category")
        history = state.get("previous_qa_list") or []
        try:
            selected = self.dataset.pick_question(
                self._extract_topics(history),
                difficulty,
                category=category,
                exclude_ids=self.dataset.derive_exclude_ids(history),
                rng=self.rng,
            )
        except ValueError:
            return await self._generate_fresh_question(state, difficulty, category)

        base_q = selected.get("Question") or selected.get("question", "")
        snippet = build_resume_snippet(state.get("resume_json"))
        if snippet:
            try:
                generated = await self.chains.personalize.ainvoke(
                    {
                        "base_question": base_q,
                        "category": category
                        or selected.get("Category", "Software Engineering"),
                        "difficulty": difficulty,
                        "resume_snippet": snippet,
                    }
                )
            except Exception:
                logger.warning(
                    "Personalize chain failed; using seed question", exc_info=True
                )
                generated = ""
            if (
                not generated
                or len(generated.split()) > word_limit(difficulty) + 25
            ):
                question_text = maybe_rephrase(base_q, self.rng)
            else:
                question_text = generated
            source = "dataset_inspired"
        else:
            question_text = maybe_rephrase(base_q, self.rng)
            source = "dataset"

        metadata: dict[str, Any] = {
            "source": source,
            "scenario": "new_question",
            "question_id": selected.get("Id"),
            "category": category or selected.get("Category", "Unknown"),
            "difficulty": selected.get("Difficulty", "medium"),
            "reference_answer": selected.get("Answer", ""),
            "is_followup": False,
        }
        metadata["scenario"] = "question_with_same_category"
        metadata["evaluation"] = self._evaluation_metadata(state)
        return {"question": question_text, "metadata": metadata}

    async def _generate_fresh_question(
        self,
        state: QuestionGraphState,
        difficulty: str,
        category: Optional[str],
    ) -> dict[str, Any]:
        """Last-resort generation when the dataset has no usable rows."""
        try:
            question_text = await self.chains.question.ainvoke(
                {
                    "category": category or "Software Engineering",
                    "difficulty": difficulty,
                    "resume_snippet": build_resume_snippet(
                        state.get("resume_json")
                    ),
                }
            )
        except Exception as exc:
            raise LLMProviderError(
                "Question generation failed and the dataset is empty"
            ) from exc
        metadata: dict[str, Any] = {
            "source": "llm_generated",
            "scenario": "question_with_same_category",
            "question_id": None,
            "category": category or "Software Engineering",
            "difficulty": difficulty,
            "reference_answer": "",
            "is_followup": False,
        }
        metadata["evaluation"] = self._evaluation_metadata(state)
        return {"question": question_text, "metadata": metadata}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _last_qa(state: QuestionGraphState) -> dict[str, Any]:
        history = state.get("previous_qa_list")
        if not history:
            raise ValueError("Answer-processing node requires interview history")
        return history[-1]

    @staticmethod
    def _evaluation_metadata(state: QuestionGraphState) -> dict[str, Any]:
        evaluation = state.get("evaluation", {})
        flow = state.get("flow", {})
        return {
            "decision": flow.get("decision"),
            "score": flow.get("score_value"),
            "confidence": evaluation.get("confidence"),
            "remarks": flow.get("remarks"),
            "feedback": evaluation.get("feedback"),
        }

    @staticmethod
    def _extract_topics(previous_qa_list: list[dict[str, Any]]) -> list[str]:
        seen: set[str] = set()
        topics: list[str] = []
        for qa in previous_qa_list:
            topic = qa.get("category") or qa.get("topic")
            if topic and topic not in seen:
                seen.add(topic)
                topics.append(topic)
        return topics

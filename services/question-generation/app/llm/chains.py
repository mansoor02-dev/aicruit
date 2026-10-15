"""LCEL chains: ``prompt | model | parser`` with provider fallbacks.

Every LLM node uses the same shape: a ``ChatPromptTemplate`` piped into a
Gemini structured-output runnable, with an OpenRouter
(``prompt | ChatOpenAI | PydanticOutputParser``) fallback attached via
``.with_fallbacks`` on the finished chains. LangSmith tracing is enabled
purely by env vars; chains only carry static ``run_name`` / ``tags`` (never
resume content or candidate answers).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import (
    Runnable,
    RunnableBranch,
    RunnableLambda,
)

from app.config import Settings
from app.llm.embeddings import EmbeddingProvider
from app.llm.models import ChatModels, ProfileModels
from app.prompts import templates as prompt_templates
from app.schemas.llm import AnswerEvaluation, DraftEmail, GeneratedQuestion
from app.services import evaluation as eval_helpers
from app.services.text import clean_question

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Chains:
    """All LCEL runnables for the service (stubs can replace any of them)."""

    question: Runnable
    personalize: Runnable
    followup: Runnable
    evaluation: Runnable
    email: Runnable


def _extract_question_text(result: Any) -> str:
    if isinstance(result, GeneratedQuestion):
        return result.question
    if isinstance(result, dict):
        return str(result.get("question", ""))
    return str(result or "")


def _clean_result(result: Any) -> str:
    return clean_question(_extract_question_text(result))


def _tag(chain: Runnable, run_name: str) -> Runnable:
    return chain.with_config(
        {"run_name": run_name, "tags": ["aicruit", "question-generation"]}
    )


def _split_profile(
    profile: ProfileModels, models: ChatModels
) -> tuple[Any | None, Any | None]:
    """Return ``(gemini_model, openrouter_model)`` for one profile.

    In an OpenRouter-only deployment the profile's ``primary`` slot already
    holds the OpenRouter model.
    """
    if models.has_gemini and models.has_openrouter:
        return profile.primary, profile.fallback
    if models.has_gemini:
        return profile.primary, None
    return None, profile.primary


def _parser_chain(
    prompt: ChatPromptTemplate, model: Any, schema: Any, tail: Runnable
) -> Runnable:
    parser: PydanticOutputParser = PydanticOutputParser(pydantic_object=schema)
    instructed = prompt.partial(
        format_instructions=parser.get_format_instructions()
    )
    return instructed | model | parser | tail


def _finish(
    primary: Runnable | None, fallback: Runnable | None, run_name: str
) -> Runnable:
    if primary is None:
        if fallback is None:
            raise ValueError(f"No model configured for chain '{run_name}'")
        chain = fallback
    elif fallback is None:
        chain = primary
    else:
        chain = primary.with_fallbacks([fallback])
    return _tag(chain, run_name)


def _build_question_chain(
    *,
    system: str,
    human: str,
    prep: Any | None,
    gemini: Any | None,
    openrouter: Any | None,
    run_name: str,
) -> Runnable:
    """Build a ``GeneratedQuestion -> cleaned str`` chain."""
    primary_prompt, fallback_prompt = prompt_templates.make_prompt(system, human)
    clean = RunnableLambda(_clean_result)
    primary: Runnable | None = None
    fallback: Runnable | None = None
    if gemini is not None:
        core = primary_prompt | gemini.with_structured_output(GeneratedQuestion)
        core = core | clean
        primary = prep | core if prep is not None else core
    if openrouter is not None:
        core = _parser_chain(
            fallback_prompt, openrouter, GeneratedQuestion, clean
        )
        fallback = prep | core if prep is not None else core
    return _finish(primary, fallback, run_name)


def _map_eval_output(values: dict) -> tuple[dict, dict]:
    return eval_helpers.map_llm_evaluation(
        values["result"], values.get("answer_length", 0)
    )


def _build_evaluation_chain(
    *,
    gemini: Any | None,
    openrouter: Any | None,
    embeddings: EmbeddingProvider,
    run_name: str = "evaluate_answer",
) -> Runnable:
    """Build the evaluation ``RunnableBranch``.

    Three deterministic short-circuits (empty, don't-know, <5 words) make zero
    LLM calls; otherwise a structured LLM chain runs, with the heuristic
    fallback receiving the same input dict when every provider fails.
    """
    primary_prompt, fallback_prompt = prompt_templates.make_prompt(
        prompt_templates.EVALUATION_SYSTEM, prompt_templates.EVALUATION_HUMAN
    )
    prep = RunnableLambda(prompt_templates.build_evaluation_inputs)

    async def heuristic_eval(inputs: dict) -> tuple[dict, dict]:
        answer = inputs.get("user_answer") or ""
        reference = inputs.get("reference_answer")
        answer_length = len(answer.split())
        if reference:
            keyword = eval_helpers.keyword_overlap(answer, reference)
            length_score = min(1.0, answer_length / 20)
            semantic: float | None = None
            if embeddings.get() is not None:
                try:
                    semantic = await embeddings.similarity(answer, reference)
                except Exception:
                    semantic = 0.5
            if semantic is None:
                # No embedder: drop the semantic term, renormalise the rest.
                depth = round(min(1.0, (0.3 * keyword + 0.2 * length_score) / 0.5), 3)
            else:
                depth = round(
                    max(
                        0.0,
                        min(1.0, 0.5 * semantic + 0.3 * keyword + 0.2 * length_score),
                    ),
                    3,
                )
        else:
            depth = round(min(1.0, answer_length / 30), 3)
        passed = depth >= eval_helpers.PASS_THRESHOLD
        return eval_helpers.heuristic_result(depth, answer_length, passed)

    map_output = RunnableLambda(_map_eval_output)

    primary: Runnable | None = None
    fallback: Runnable | None = None
    if gemini is not None:
        core = primary_prompt | gemini.with_structured_output(AnswerEvaluation)
        primary = (
            prep
            | {
                "result": core,
                "answer_length": lambda prepped: prepped["answer_length"],
            }
            | map_output
        )
    if openrouter is not None:
        parser: PydanticOutputParser = PydanticOutputParser(
            pydantic_object=AnswerEvaluation
        )
        instructed = fallback_prompt.partial(
            format_instructions=parser.get_format_instructions()
        )
        core = instructed | openrouter | parser
        fallback = (
            prep
            | {
                "result": core,
                "answer_length": lambda prepped: prepped["answer_length"],
            }
            | map_output
        )

    if primary is None and fallback is None:
        raise ValueError("No model configured for chain 'evaluate_answer'")
    if primary is None:
        llm_eval = fallback
    elif fallback is None:
        llm_eval = primary
    else:
        llm_eval = primary.with_fallbacks([fallback])
    llm_eval = llm_eval.with_fallbacks([RunnableLambda(heuristic_eval)])

    branch = RunnableBranch(
        (
            eval_helpers.is_empty_answer,
            RunnableLambda(lambda inputs: eval_helpers.empty_answer_result()),
        ),
        (
            eval_helpers.is_dont_know_answer,
            RunnableLambda(lambda inputs: eval_helpers.dont_know_result()),
        ),
        (
            eval_helpers.is_brief_answer,
            RunnableLambda(
                lambda inputs: eval_helpers.brief_answer_result(
                    len((inputs.get("user_answer") or "").split())
                )
            ),
        ),
        llm_eval,
    )
    return _tag(branch, run_name)


def _build_email_chain(
    *, gemini: Any | None, openrouter: Any | None
) -> Runnable:
    primary_prompt, fallback_prompt = prompt_templates.make_prompt(
        prompt_templates.EMAIL_SYSTEM, prompt_templates.EMAIL_HUMAN
    )
    primary: Runnable | None = None
    fallback: Runnable | None = None
    if gemini is not None:
        primary = primary_prompt | gemini.with_structured_output(DraftEmail)
    if openrouter is not None:
        fallback = _parser_chain(
            fallback_prompt, openrouter, DraftEmail, RunnableLambda(lambda x: x)
        )
    return _finish(primary, fallback, "draft_email")


def build_chains(
    models: ChatModels,
    settings: Settings,
    embeddings: EmbeddingProvider,
) -> Chains:
    """Assemble every LCEL chain from models, settings and embeddings."""
    _ = settings  # Per-profile generation settings already live on the models.
    # The question, personalize and followup chains share the "question"
    # generation profile (same temperature / max-token budget).
    gemini_q, openrouter_q = _split_profile(models.question, models)
    gemini_e, openrouter_e = _split_profile(models.evaluation, models)
    gemini_m, openrouter_m = _split_profile(models.email, models)

    followup_prep: Runnable = RunnableLambda(
        prompt_templates.build_followup_inputs
    )
    return Chains(
        question=_build_question_chain(
            system=prompt_templates.QUESTION_SYSTEM,
            human=prompt_templates.QUESTION_HUMAN,
            prep=None,
            gemini=gemini_q,
            openrouter=openrouter_q,
            run_name="generate_question",
        ),
        personalize=_build_question_chain(
            system=prompt_templates.PERSONALIZE_SYSTEM,
            human=prompt_templates.PERSONALIZE_HUMAN,
            prep=None,
            gemini=gemini_q,
            openrouter=openrouter_q,
            run_name="personalize_question",
        ),
        followup=_build_question_chain(
            system=prompt_templates.FOLLOWUP_SYSTEM,
            human=prompt_templates.FOLLOWUP_HUMAN,
            prep=followup_prep,
            gemini=gemini_q,
            openrouter=openrouter_q,
            run_name="generate_followup",
        ),
        evaluation=_build_evaluation_chain(
            gemini=gemini_e,
            openrouter=openrouter_e,
            embeddings=embeddings,
        ),
        email=_build_email_chain(gemini=gemini_m, openrouter=openrouter_m),
    )

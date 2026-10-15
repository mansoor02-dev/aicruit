"""Evaluation chain: short-circuits, stub mapping and heuristic fallback."""

import asyncio

from conftest import FakeChatModel, stub_chain
from app.config import Settings
from app.llm.chains import build_chains
from app.llm.embeddings import EmbeddingProvider
from app.llm.models import ChatModels, ProfileModels
from app.schemas.llm import AnswerEvaluation
from app.services import evaluation as eval_helpers


def _chains(primary_result=None, primary_exc=None, fallback_result=None,
            fallback_exc=None, embeddings=None):
    primary_calls: list = []
    fallback_calls: list = []
    gemini = FakeChatModel(
        result=primary_result, exc=primary_exc, calls=primary_calls
    )
    openrouter = FakeChatModel(
        result=fallback_result, exc=fallback_exc, calls=fallback_calls
    )
    models = ChatModels(
        question=ProfileModels(
            primary=FakeChatModel(result="Q?"), fallback=None
        ),
        evaluation=ProfileModels(primary=gemini, fallback=openrouter),
        email=ProfileModels(primary=FakeChatModel(result=None), fallback=None),
        has_gemini=True,
        has_openrouter=True,
    )
    chains = build_chains(
        models,
        Settings(gemini_api_key="test", openrouter_api_key="test"),
        embeddings or EmbeddingProvider(Settings()),
    )
    return chains.evaluation, primary_calls, fallback_calls


def _llm_answer():
    return (
        "Indexes improve query performance by locating matching rows "
        "without scanning every record in the table."
    )


def test_short_circuits_make_zero_llm_calls():
    evaluation, primary_calls, fallback_calls = _chains(
        primary_result=AnswerEvaluation(
            score=0.8,
            confidence=0.9,
            feedback="Clear explanation.",
            decision="new_topic",
            remarks="Sufficient.",
            score_reason="Covers key points.",
        )
    )

    asyncio.run(evaluation.ainvoke({"question": "Q?", "user_answer": "ok"}))
    asyncio.run(
        evaluation.ainvoke(
            {"question": "Q?", "user_answer": "I don't know this topic"}
        )
    )
    asyncio.run(
        evaluation.ainvoke({"question": "Q?", "user_answer": "far too short"})
    )

    assert primary_calls == []
    assert fallback_calls == []


def test_dont_know_variants_skip_llm():
    evaluation, primary_calls, _ = _chains(
        primary_result=AnswerEvaluation(score=0.9, decision="new_topic")
    )

    for answer in (
        "I have no idea about this.",
        "Never heard of it, sorry.",
        "I'm not familiar with that framework at all.",
    ):
        ev, flow = asyncio.run(
            evaluation.ainvoke({"question": "Q?", "user_answer": answer})
        )
        assert flow["decision"] == "new_topic"
        assert ev["depth_score"] == 0.0

    assert primary_calls == []


def test_combined_evaluation_uses_structured_chain():
    evaluation, primary_calls, fallback_calls = _chains(
        primary_result=AnswerEvaluation(
            score=0.8,
            confidence=0.9,
            feedback="Clear explanation.",
            decision="new_topic",
            remarks="The answer is sufficient.",
            score_reason="Covers key points.",
        )
    )

    evaluation_result, flow = asyncio.run(
        evaluation.ainvoke(
            {
                "question": "How do indexes improve queries?",
                "user_answer": _llm_answer(),
            }
        )
    )

    assert evaluation_result["pass"] is True
    assert evaluation_result["depth_score"] == 0.8
    assert evaluation_result["feedback"] == "Clear explanation."
    assert flow["decision"] == "new_topic"
    assert flow["score_value"] == 0.8
    assert len(primary_calls) == 1
    assert fallback_calls == []


def test_openrouter_fallback_parses_structured_output():
    evaluation, primary_calls, fallback_calls = _chains(
        primary_exc=RuntimeError("Gemini unavailable"),
        fallback_result=(
            '{"score": 0.3, "confidence": 0.7, "feedback": "Vague.", '
            '"decision": "same_topic", "remarks": "Needs detail.", '
            '"score_reason": "Missing concepts."}'
        ),
    )

    evaluation_result, flow = asyncio.run(
        evaluation.ainvoke(
            {"question": "How does caching work?", "user_answer": _llm_answer()}
        )
    )

    assert evaluation_result["pass"] is False
    assert flow["decision"] == "same_topic"
    assert flow["score_value"] == 0.3
    assert len(primary_calls) == 1
    assert len(fallback_calls) == 1


def test_heuristic_fallback_when_all_providers_fail():
    evaluation, _, _ = _chains(
        primary_exc=RuntimeError("Gemini unavailable"),
        fallback_exc=RuntimeError("OpenRouter unavailable"),
    )
    long_answer = " ".join(["caching improves performance greatly"] * 10)

    evaluation_result, flow = asyncio.run(
        evaluation.ainvoke(
            {
                "question": "How does caching work?",
                "user_answer": long_answer,
                "reference_answer": None,
                "is_followup": False,
            }
        )
    )

    assert evaluation_result["depth_score"] == 1.0
    assert evaluation_result["pass"] is True
    assert flow["decision"] == "new_topic"


def test_heuristic_renormalises_without_embeddings():
    evaluation, _, _ = _chains(
        primary_exc=RuntimeError("Gemini unavailable"),
        fallback_exc=RuntimeError("OpenRouter unavailable"),
        embeddings=EmbeddingProvider(Settings()),  # no GEMINI_API_KEY
    )
    answer = "Caching stores copies of data for fast access today quickly."
    reference = "Caching stores copies of frequently accessed data in memory."

    evaluation_result, flow = asyncio.run(
        evaluation.ainvoke(
            {
                "question": "How does caching work?",
                "user_answer": answer,
                "reference_answer": reference,
                "is_followup": False,
            }
        )
    )

    keyword = eval_helpers.keyword_overlap(answer, reference)
    length = min(1.0, len(answer.split()) / 20)
    expected = round(min(1.0, (0.3 * keyword + 0.2 * length) / 0.5), 3)
    assert evaluation_result["depth_score"] == expected
    assert flow["score_value"] == expected


def test_stub_chain_result_maps_to_pass_and_flow():
    from conftest import FOLLOWUP_EVALUATION, make_stub_chains

    chains = make_stub_chains(evaluation=FOLLOWUP_EVALUATION)
    evaluation_result, flow = asyncio.run(
        chains.evaluation.ainvoke(
            {"question": "Q?", "user_answer": _llm_answer()}
        )
    )

    assert evaluation_result["pass"] is False
    assert evaluation_result["depth_score"] == 0.4
    assert flow["decision"] == "same_topic"
    assert flow["score_value"] == 0.4

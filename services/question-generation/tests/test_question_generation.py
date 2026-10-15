"""Question generation: followup/new-topic nodes, text utils and pool rules."""

import asyncio
import random

from app.config import Settings
from app.graph.builder import Dependencies, build_question_graph
from app.graph.edges import select_pool_question
from app.services.dataset import DatasetRepository
from app.services.text import clean_question, is_valid_followup
from conftest import ROWS, make_stub_chains


def _graph(**chain_overrides):
    chains = make_stub_chains(**chain_overrides)
    return build_question_graph(
        Dependencies(
            chains=chains,
            dataset=DatasetRepository(ROWS),
            settings=Settings(gemini_api_key="test"),
            rng=random.Random(0),
        )
    )


def test_followup_generation_preserves_question_metadata():
    graph = _graph(
        followup="How did you apply cache invalidation in production?"
    )

    result = asyncio.run(
        graph.ainvoke(
            {
                "previous_qa_list": [
                    {
                        "Q": "How does a cache work?",
                        "A": "I used cache invalidation to prevent stale data.",
                    }
                ],
                "category": "Caching",
            }
        )
    )

    assert result["question"] == "How did you apply cache invalidation in production?"
    assert result["metadata"]["scenario"] == "question_with_same_category"
    assert result["metadata"]["is_followup"] is True
    assert result["metadata"]["followup_angle"] == "elaboration"
    assert result["metadata"]["based_on_question"] == "How does a cache work?"


def test_followup_angle_deep_dive():
    deep_dive = (
        {
            "pass": True,
            "depth_score": 0.85,
            "confidence": 0.9,
            "feedback": "Strong answer.",
            "answer_length": 20,
            "needs_followup": False,
        },
        {
            "decision": "deep_dive",
            "remarks": "Worth probing deeper.",
            "score_value": 0.85,
            "score_reason": "Excellent detail.",
        },
    )
    graph = _graph(evaluation=deep_dive)

    result = asyncio.run(
        graph.ainvoke(
            {
                "previous_qa_list": [
                    {
                        "Q": "How does caching work?",
                        "A": "I use caching to improve performance.",
                    }
                ],
                "category": "Caching",
            }
        )
    )

    assert result["metadata"]["is_followup"] is True
    assert result["metadata"]["followup_angle"] == "implementation_details"
    assert result["metadata"]["evaluation"]["decision"] == "deep_dive"


def test_followup_angle_mapping():
    from app.services.text import followup_angle

    assert followup_angle("deep_dive") == "implementation_details"
    assert followup_angle("same_topic") == "elaboration"
    assert followup_angle("new_topic") == "elaboration"


def test_new_topic_personalises_with_resume():
    from conftest import PASS_EVALUATION

    graph = _graph(
        evaluation=PASS_EVALUATION,
        personalize="How did you apply caching at scale?",
    )

    result = asyncio.run(
        graph.ainvoke(
            {
                "resume_json": {"skills": ["Redis"]},
                "previous_qa_list": [
                    {
                        "Q": "What is Python?",
                        "A": "Python is a language I use daily for scripting.",
                    }
                ],
                "category": "Caching",
            }
        )
    )

    assert result["question"] == "How did you apply caching at scale?"
    assert result["metadata"]["source"] == "dataset_inspired"
    assert result["metadata"]["is_followup"] is False


def test_new_topic_without_resume_uses_seed():
    from conftest import PASS_EVALUATION

    graph = _graph(evaluation=PASS_EVALUATION)

    result = asyncio.run(
        graph.ainvoke(
            {
                "previous_qa_list": [
                    {
                        "Q": "What is Python?",
                        "A": "Python is a language I use daily for scripting.",
                    }
                ],
                "category": "Caching",
                "difficulty": "easy",
            }
        )
    )

    assert result["metadata"]["source"] == "dataset"
    assert result["metadata"]["category"] == "Caching"
    assert result["question"] == "What is caching?"


def test_personalize_word_limit_falls_back_to_seed():
    from conftest import PASS_EVALUATION

    graph = _graph(
        evaluation=PASS_EVALUATION, personalize=" ".join(["word"] * 60)
    )

    result = asyncio.run(
        graph.ainvoke(
            {
                "resume_json": {"skills": ["Redis"]},
                "previous_qa_list": [
                    {
                        "Q": "What is Python?",
                        "A": "Python is a language I use daily for scripting.",
                    }
                ],
                "category": "Caching",
            }
        )
    )

    assert result["metadata"]["source"] == "dataset_inspired"
    assert len(result["question"].split()) <= 20


def test_clean_question_keeps_through_first_question_mark():
    assert (
        clean_question("How does Node.js handle I/O?")
        == "How does Node.js handle I/O?"
    )
    assert clean_question("  Question: How does caching work?  ") == (
        "How does caching work?"
    )
    assert (
        clean_question('Can you give an e.g. of caching? "Sure," he said.')
        == "Can you give an e.g. of caching?"
    )


def test_clean_question_appends_question_mark_when_missing():
    assert clean_question("Tell me about C++") == "Tell me about C++?"
    assert clean_question("Compare X vs. Y") == "Compare X vs. Y?"
    assert clean_question("Explain e.g. caching strategies") == (
        "Explain e.g. caching strategies?"
    )
    assert clean_question("") == ""


def test_is_valid_followup():
    assert is_valid_followup(
        "How did you use caching in production?",
        "I used caching to improve performance.",
    )
    assert not is_valid_followup("bad", "I used caching in production.")
    assert not is_valid_followup(
        "How did you use caching in production?", "unrelated words here now"
    )


def test_exclude_ids_derived_from_history():
    rows = [
        {
            "Id": str(i),
            "Question": f"Easy caching question number {i}?",
            "Answer": "An answer.",
            "Category": "Caching",
            "Difficulty": "easy",
        }
        for i in range(10, 14)
    ]
    dataset = DatasetRepository(rows)
    exclude = dataset.derive_exclude_ids(
        [
            {
                "Q": "I'd like to know: Easy caching question number 10?",
                "A": "An answer here.",
            },
            {"Q": "Something else entirely?", "A": "Another answer here."},
        ]
    )

    assert exclude == {"10"}
    for seed in range(10):
        picked = dataset.pick_question(
            [],
            "easy",
            category="Caching",
            exclude_ids=exclude,
            rng=random.Random(seed),
        )
        assert picked["Id"] != "10"


def test_pool_prefers_topic_match_then_first_unused():
    pool = [
        {"question": "Q1 pool", "topic": "Other"},
        {"question": "Q2 pool", "topic": "API"},
    ]

    assert select_pool_question(pool, [], "API")["question"] == "Q2 pool"
    assert select_pool_question(pool, [], None)["question"] == "Q1 pool"
    # Topic mismatch is accepted on purpose.
    assert select_pool_question(pool, [], "Missing")["question"] == "Q1 pool"
    # Exhausted pool falls through to the normal graph.
    assert (
        select_pool_question(pool, ["Q1 pool", "Q2 pool"], "API") is None
    )
    assert select_pool_question([], [], "API") is None


def test_optional_qa_fields_are_backward_compatible():
    from app.schemas.requests import QuestionRequest

    plain = QuestionRequest.model_validate(
        {"previous_qa": [{"Q": "Q?", "A": "An answer here today."}]}
    )
    assert plain.previous_qa[0].category is None
    assert plain.previous_qa[0].is_followup is False
    assert plain.previous_qa[0].reference_answer is None

    enriched = QuestionRequest.model_validate(
        {
            "previous_qa": [
                {
                    "Q": "Q?",
                    "A": "An answer here today.",
                    "category": "Caching",
                    "is_followup": True,
                    "reference_answer": "A reference.",
                    "question_id": "7",
                }
            ]
        }
    )
    assert enriched.previous_qa[0].category == "Caching"

    graph = _graph()
    result = asyncio.run(
        graph.ainvoke(
            {
                "previous_qa_list": [
                    qa.model_dump() for qa in enriched.previous_qa
                ],
                "category": "Caching",
            }
        )
    )
    assert result["metadata"]["is_followup"] is True

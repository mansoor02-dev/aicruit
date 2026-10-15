import asyncio

from app.pipelines.orchestrator import InterviewOrchestrator
from conftest import FOLLOWUP_EVALUATION, make_stub_chains, make_test_graph

CACHING_HISTORY = [
    {
        "Q": "How does caching work?",
        "A": "I use caching to improve performance.",
    }
]


def test_graph_routes_initial_request_to_introduction():
    graph = make_test_graph()

    question, metadata = asyncio.run(
        InterviewOrchestrator(graph).generate_next_question(
            resume_json={"name": "Sam"}
        )
    )

    assert question.startswith("Hi Sam")
    assert metadata["scenario"] == "1st_question"


def test_graph_routes_evaluated_answer_to_followup():
    graph = make_test_graph()

    result = asyncio.run(
        graph.ainvoke(
            {
                "previous_qa_list": CACHING_HISTORY,
                "category": "Caching",
            }
        )
    )

    assert result["question"] == "How did you use caching in production?"
    assert result["metadata"]["is_followup"] is True
    assert result["metadata"]["evaluation"]["decision"] == "same_topic"
    assert result["metadata"]["evaluation"]["score"] == 0.4


def test_graph_routes_no_history_category_to_opener():
    graph = make_test_graph()

    result = asyncio.run(graph.ainvoke({"category": "Python"}))

    assert result["metadata"]["is_category_opener"] is True
    assert result["metadata"]["difficulty"] == "easy"
    assert result["metadata"]["category"] == "Python"


def test_graph_output_schema_has_only_response_keys():
    graph = make_test_graph()

    result = asyncio.run(
        graph.ainvoke({"previous_qa_list": CACHING_HISTORY})
    )

    assert set(result) == {"question", "metadata"}


def test_graph_routes_strong_answer_to_new_topic():
    from conftest import PASS_EVALUATION

    graph = make_test_graph(
        chains=make_stub_chains(
            evaluation=PASS_EVALUATION,
            personalize="Personalized caching question?",
        )
    )

    result = asyncio.run(
        graph.ainvoke(
            {
                "resume_json": {"skills": ["Redis"]},
                "previous_qa_list": [
                    {
                        "Q": "How does caching work?",
                        "A": (
                            "Caching stores copies of frequently accessed data "
                            "in memory to reduce latency on repeated reads."
                        ),
                    }
                ],
                "category": "Caching",
            }
        )
    )

    assert result["metadata"]["is_followup"] is False
    assert result["metadata"]["evaluation"]["decision"] == "new_topic"


def test_followup_retry_loop_uses_template_after_two_invalid():
    import random

    from langchain_core.runnables import RunnableLambda

    from app.config import Settings
    from app.graph.builder import Dependencies, build_question_graph
    from app.llm.chains import Chains
    from app.services.dataset import DatasetRepository
    from conftest import ROWS, make_stub_chains

    chains = make_stub_chains()
    bad_followup = Chains(
        question=chains.question,
        personalize=chains.personalize,
        followup=RunnableLambda(lambda _inputs: "bad"),
        evaluation=chains.evaluation,
        email=chains.email,
    )
    graph = build_question_graph(
        Dependencies(
            chains=bad_followup,
            dataset=DatasetRepository(ROWS),
            settings=Settings(gemini_api_key="test"),
            rng=random.Random(0),
        )
    )

    result = asyncio.run(
        graph.ainvoke(
            {
                "previous_qa_list": [
                    {
                        "Q": "How does caching work?",
                        "A": "I used caching with Redis clusters daily.",
                    }
                ],
                "category": "Caching",
            }
        )
    )

    assert "Caching" in result["question"]
    assert result["metadata"]["is_followup"] is True


def test_followup_retry_loop_accepts_second_attempt():
    from langchain_core.runnables import RunnableLambda

    from app.llm.chains import Chains
    from conftest import make_stub_chains

    chains = make_stub_chains()
    calls = {"n": 0}

    async def _flaky(_inputs):
        calls["n"] += 1
        if calls["n"] == 1:
            return "bad"
        return "How did caching improve latency?"

    retry_chains = Chains(
        question=chains.question,
        personalize=chains.personalize,
        followup=RunnableLambda(_flaky),
        evaluation=chains.evaluation,
        email=chains.email,
    )
    graph = make_test_graph(chains=retry_chains)

    result = asyncio.run(
        graph.ainvoke(
            {
                "previous_qa_list": [
                    {
                        "Q": "How does caching work?",
                        "A": "I used caching with Redis clusters daily.",
                    }
                ],
                "category": "Caching",
            }
        )
    )

    assert result["question"] == "How did caching improve latency?"
    assert calls["n"] == 2


def test_max_followups_routes_to_new_topic():
    graph = make_test_graph(
        chains=make_stub_chains(evaluation=FOLLOWUP_EVALUATION)
    )

    result = asyncio.run(
        graph.ainvoke(
            {
                "previous_qa_list": [
                    {"Q": "Q1?", "A": "Answer one two three four five."},
                    {
                        "Q": "Q2?",
                        "A": "Answer six seven eight nine ten.",
                        "is_followup": True,
                    },
                    {
                        "Q": "Q3?",
                        "A": "Answer eleven twelve thirteen fourteen fifteen.",
                        "is_followup": True,
                    },
                ],
                "category": "Caching",
            }
        )
    )

    assert result["metadata"]["is_followup"] is False
    # The evaluation still says same_topic; the budget forced a new topic.
    assert result["metadata"]["evaluation"]["decision"] == "same_topic"

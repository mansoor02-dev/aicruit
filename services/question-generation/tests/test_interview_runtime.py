from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda

from app import main as application
from app.llm.chains import Chains
from app.schemas.llm import DraftEmail
from conftest import stub_chain


def _interview_chains():
    state = {"evaluations": 0}

    async def _followup(_inputs):
        return "What Python design trade-offs did you make?"

    async def _personalize(_inputs):
        return "How would you evaluate scaling bottlenecks in a system?"

    async def _evaluate(_inputs):
        state["evaluations"] += 1
        if state["evaluations"] == 1:
            return (
                {
                    "pass": False,
                    "depth_score": 0.45,
                    "confidence": 0.9,
                    "feedback": (
                        "The answer includes relevant implementation detail."
                    ),
                    "answer_length": 12,
                    "needs_followup": True,
                },
                {
                    "decision": "same_topic",
                    "remarks": "Continue the simulated interview.",
                    "score_value": 0.45,
                    "score_reason": "Deterministic runtime-test response.",
                },
            )
        return (
            {
                "pass": True,
                "depth_score": 0.82,
                "confidence": 0.9,
                "feedback": (
                    "The answer includes relevant implementation detail."
                ),
                "answer_length": 16,
                "needs_followup": False,
            },
            {
                "decision": "new_topic",
                "remarks": "Continue the simulated interview.",
                "score_value": 0.82,
                "score_reason": "Deterministic runtime-test response.",
            },
        )

    chains = Chains(
        question=stub_chain("Fresh question?"),
        personalize=RunnableLambda(_personalize),
        followup=RunnableLambda(_followup),
        evaluation=RunnableLambda(_evaluate),
        email=stub_chain(DraftEmail(subject="s", body="b")),
    )
    return chains, state


def test_multiturn_interview_via_http_api(monkeypatch):
    chains, state = _interview_chains()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(application, "build_chains", lambda *args: chains)

    resume = {
        "personal_info": {"name": "Synthetic Candidate"},
        "skills": ["Python", "PostgreSQL"],
        "experience": [],
        "projects": [],
    }
    answer = (
        "I used Python to build a data-processing service and measured its "
        "performance before and after deployment."
    )

    with TestClient(application.app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        first = client.post("/next-question", json={"resume_json": resume})
        assert first.status_code == 200
        first_data = first.json()
        assert first_data["question"].startswith("Hi Synthetic Candidate")
        assert first_data["metadata"]["scenario"] == "1st_question"

        history = [
            {
                "Q": first_data["question"],
                "A": (
                    "I am a software engineer with experience building "
                    "Python services and data applications."
                ),
            }
        ]
        second = client.post(
            "/next-question",
            json={
                "resume_json": resume,
                "previous_qa": history,
                "category": "Python",
            },
        )
        assert second.status_code == 200
        second_data = second.json()
        assert second_data["metadata"]["is_followup"] is True
        assert second_data["metadata"]["evaluation"]["decision"] == "same_topic"
        assert "Python" in second_data["question"]

        history.append({"Q": second_data["question"], "A": answer})
        third = client.post(
            "/next-question",
            json={
                "resume_json": resume,
                "previous_qa": history,
                "category": "Python",
            },
        )
        assert third.status_code == 200
        third_data = third.json()
        assert third_data["metadata"]["is_followup"] is False
        assert third_data["metadata"]["evaluation"]["decision"] == "new_topic"
        assert third_data["question"].endswith("?")

    assert state["evaluations"] == 2

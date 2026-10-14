from fastapi.testclient import TestClient

from app import main as application
from app.schemas.llm import AnswerEvaluation, GeneratedQuestion


class InterviewLLMStub:
    def __init__(self):
        self.evaluation_count = 0

    async def complete_json(self, prompt, response_model, **_kwargs):
        if response_model is GeneratedQuestion:
            if "follow-up" in prompt.lower():
                return GeneratedQuestion(
                    question="What Python design trade-offs did you make?"
                )
            return GeneratedQuestion(
                question="How would you evaluate scaling bottlenecks in a system?"
            )

        assert response_model is AnswerEvaluation
        self.evaluation_count += 1
        decision = "same_topic" if self.evaluation_count == 1 else "new_topic"
        return AnswerEvaluation(
            score=0.45 if decision == "same_topic" else 0.82,
            confidence=0.9,
            feedback="The answer includes relevant implementation detail.",
            decision=decision,
            remarks="Continue the simulated interview.",
            score_reason="Deterministic runtime-test response.",
        )


def test_multiturn_interview_via_http_api(monkeypatch):
    llm_stub = InterviewLLMStub()
    monkeypatch.setattr(application, "LLMClient", lambda: llm_stub)
    monkeypatch.setattr(application, "get_embedder", lambda: object())

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

    assert llm_stub.evaluation_count == 2

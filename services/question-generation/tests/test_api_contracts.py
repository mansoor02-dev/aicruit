import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import routes as api
from app import main as application
from app.pipelines.orchestrator import InterviewOrchestrator
from app.services.question_generator import QuestionGenerator


class StubLLMClient:
    async def complete_json(
        self,
        response_model,
        **_kwargs,
    ):
        if response_model.__name__ == "DraftEmail":
            return response_model(subject="Interview update", body="Thank you.")
        return response_model(question="How do you use caching?")


class StubEvaluator:
    async def evaluate_combined(self, **_kwargs):
        return {}, {}


def test_next_question_endpoint_keeps_response_shape():
    generator = QuestionGenerator(dataset_questions=[], llm_client=StubLLMClient())
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                orchestrator=InterviewOrchestrator(StubEvaluator(), generator)
            )
        )
    )

    response = asyncio.run(api.get_next_question(api.QuestionRequest(), request))

    assert set(response) == {"question", "metadata"}
    assert response["question"].startswith("Welcome!")
    assert response["metadata"]["scenario"] == "1st_question"


def test_recruiter_pool_without_history_skips_llm_and_graph():
    class CountingLLMClient(StubLLMClient):
        def __init__(self):
            self.calls = 0

        async def complete_json(self, response_model, **kwargs):
            self.calls += 1
            return await super().complete_json(response_model, **kwargs)

    class CountingEvaluator(StubEvaluator):
        def __init__(self):
            self.calls = 0

        async def evaluate_combined(self, **kwargs):
            self.calls += 1
            return await super().evaluate_combined(**kwargs)

    llm_client = CountingLLMClient()
    evaluator = CountingEvaluator()
    generator = QuestionGenerator(dataset_questions=[], llm_client=llm_client)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                orchestrator=InterviewOrchestrator(evaluator, generator)
            )
        )
    )

    response = asyncio.run(
        api.get_next_question(
            api.QuestionRequest(
                question_pool=[
                    {"question": "How do you measure API latency?", "topic": "API"}
                ],
                category="API",
            ),
            request,
        )
    )

    assert response["question"] == "How do you measure API latency?"
    assert response["metadata"]["source"] == "recruiter_pool"
    assert llm_client.calls == 0
    assert evaluator.calls == 0


def test_application_lifespan_initializes_app_state(monkeypatch):
    llm_client = StubLLMClient()
    orchestrator = object()
    monkeypatch.setattr(application, "LLMClient", lambda: llm_client)
    monkeypatch.setattr(application, "get_embedder", object)
    monkeypatch.setattr(application, "AnswerEvaluator", lambda **_kwargs: object())
    monkeypatch.setattr(application, "QuestionGenerator", lambda **_kwargs: object())
    monkeypatch.setattr(
        application,
        "InterviewOrchestrator",
        lambda **_kwargs: orchestrator,
    )

    with TestClient(application.app) as client:
        assert client.get("/health").json() == {
            "status": "ok",
            "service": "interview-question-generation",
        }
        assert application.app.state.llm_client is llm_client
        assert application.app.state.orchestrator is orchestrator


def test_draft_email_endpoint_keeps_response_shape(monkeypatch):
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(llm_client=StubLLMClient()))
    )
    response = asyncio.run(
        api.draft_email(
            api.DraftEmailRequest(
                scenario="shortlisted",
                candidate_name="Sam Candidate",
                job_title="Engineer",
            ),
            request,
        )
    )

    assert response == {"subject": "Interview update", "body": "Thank you."}

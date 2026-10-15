import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda

from app import main as application
from app.api import routes as api
from app.llm.chains import Chains
from app.schemas.llm import DraftEmail
from conftest import make_stub_chains, make_test_graph, stub_chain


def _request_with_graph(graph, chains):
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(graph=graph, chains=chains)
        )
    )


def test_next_question_endpoint_keeps_response_shape():
    chains = make_stub_chains()
    request = _request_with_graph(make_test_graph(chains=chains), chains)

    response = asyncio.run(api.get_next_question(api.QuestionRequest(), request))

    assert set(response) == {"question", "metadata"}
    assert response["question"].startswith("Welcome!")
    assert response["metadata"]["scenario"] == "1st_question"


def test_recruiter_pool_without_history_skips_llm_and_graph():
    calls = {"evaluation": 0, "followup": 0, "personalize": 0, "question": 0}

    def _counting(name, value):
        async def _inner(_inputs):
            calls[name] += 1
            return value

        return RunnableLambda(_inner)

    chains = Chains(
        question=_counting("question", "stub?"),
        personalize=_counting("personalize", "stub?"),
        followup=_counting("followup", "stub?"),
        evaluation=_counting(
            "evaluation",
            (
                {
                    "pass": True,
                    "depth_score": 0.5,
                    "confidence": 0.5,
                    "feedback": "",
                    "answer_length": 0,
                    "needs_followup": False,
                },
                {
                    "decision": "new_topic",
                    "remarks": "",
                    "score_value": 0.5,
                    "score_reason": "",
                },
            ),
        ),
        email=_counting(
            "email", DraftEmail(subject="s", body="b")
        ),
    )
    request = _request_with_graph(make_test_graph(chains=chains), chains)

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
    assert calls == {
        "evaluation": 0,
        "followup": 0,
        "personalize": 0,
        "question": 0,
    }


def test_recruiter_pool_with_history_attaches_evaluation():
    chains = make_stub_chains()
    request = _request_with_graph(make_test_graph(chains=chains), chains)

    response = asyncio.run(
        api.get_next_question(
            api.QuestionRequest(
                question_pool=[
                    {"question": "How do you measure API latency?", "topic": "API"}
                ],
                category="API",
                previous_qa=[
                    {
                        "Q": "How does caching work?",
                        "A": "I use caching to improve performance.",
                    }
                ],
            ),
            request,
        )
    )

    assert response["metadata"]["source"] == "recruiter_pool"
    assert response["metadata"]["evaluation"]["decision"] == "same_topic"


def test_application_lifespan_initializes_app_state(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(
        application, "build_chains", lambda *args: make_stub_chains()
    )

    with TestClient(application.app) as client:
        assert client.get("/health").json() == {
            "status": "ok",
            "service": "interview-question-generation",
        }
        assert application.app.state.graph is not None
        assert application.app.state.orchestrator is not None
        assert application.app.state.chains is not None
        assert application.app.state.dataset is not None


def test_draft_email_endpoint_keeps_response_shape():
    chains = make_stub_chains()
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(chains=chains))
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


def test_draft_email_keeps_literal_interview_link_placeholder():
    seen = {}

    async def _capture(inputs):
        seen.update(inputs)
        return DraftEmail(subject="Interview scheduled", body="See {interview_link}.")

    chains = make_stub_chains(email=stub_chain(None))
    capturing = Chains(
        question=chains.question,
        personalize=chains.personalize,
        followup=chains.followup,
        evaluation=chains.evaluation,
        email=RunnableLambda(_capture),
    )
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(chains=capturing))
    )
    response = asyncio.run(
        api.draft_email(
            api.DraftEmailRequest(
                scenario="interview_scheduled",
                candidate_name="Sam Candidate",
                job_title="Engineer",
                scheduled_at="2026-10-20T10:00:00Z",
            ),
            request,
        )
    )

    assert "{interview_link}" in seen["guidance"]
    assert response["body"] == "See {interview_link}."


def test_email_system_prompt_renders_literal_company():
    from app.prompts.templates import EMAIL_SYSTEM, make_prompt

    primary, _ = make_prompt(EMAIL_SYSTEM, "Scenario: {scenario}")
    system_text = primary.format_messages(scenario="x")[0].content

    assert "{Company} Hiring Team" in system_text


def test_draft_email_all_scenarios_return_subject_and_body():
    from app.prompts.templates import build_scenario_guidance

    scenarios = [
        "shortlisted",
        "interview_scheduled",
        "stage_advance",
        "rejection",
        "offer",
        "custom",
    ]
    for scenario in scenarios:
        # Guidance builds without template errors for every scenario.
        guidance = build_scenario_guidance(
            scenario,
            "Engineer",
            "2026-10-20T10:00:00Z",
            "Technical",
            "Be concise." if scenario == "custom" else None,
        )
        assert guidance

        chains = make_stub_chains(
            email=stub_chain(
                DraftEmail(subject=f"{scenario} subject", body="Body text.")
            )
        )
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(chains=chains))
        )
        payload = {
            "scenario": scenario,
            "candidate_name": "Sam Candidate",
            "job_title": "Engineer",
            "scheduled_at": "2026-10-20T10:00:00Z",
        }
        if scenario == "rejection":
            payload["category_scores"] = [
                {"category": "Python", "score": 4.0}
            ]
        response = asyncio.run(
            api.draft_email(api.DraftEmailRequest(**payload), request)
        )
        assert set(response) == {"subject", "body"}
        assert response["subject"] and response["body"]

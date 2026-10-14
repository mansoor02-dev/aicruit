from fastapi.testclient import TestClient

from app.llm.dependencies import get_llm_client
from app.main import app
from app.schemas.reports import CandidateReport, RecruiterSummary, ScoreResult


class APIStubLLM:
    async def complete_structured(self, _prompt, response_model, _values, **_kwargs):
        if response_model is ScoreResult:
            return ScoreResult(score=5, remark="Clear explanation.")
        if response_model is RecruiterSummary:
            return RecruiterSummary(overall_remark="A strong technical discussion.")
        if response_model is CandidateReport:
            return CandidateReport(
                strengths=["Clear explanations."],
                improvements=["Include more implementation details."],
            )
        raise AssertionError(f"Unexpected schema {response_model}")


def test_generate_report_keeps_response_contract(monkeypatch):
    app.dependency_overrides[get_llm_client] = lambda: APIStubLLM()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/generate-report",
                json={
                    "data": [
                        {
                            "q": "How would you design a cache?",
                            "a": "I would measure access patterns and define invalidation.",
                            "category": "Systems",
                        }
                    ]
                },
            )
    finally:
        app.dependency_overrides.pop(get_llm_client, None)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"recruiter_report", "candidate_report"}
    assert body["recruiter_report"]["overall_score"] == 10.0
    assert body["recruiter_report"]["category_scores"] == [
        {"category": "Systems", "score": 10.0}
    ]
    assert body["candidate_report"]["strengths"] == ["Clear explanations."]


def test_generate_report_rejects_empty_data():
    with TestClient(app) as client:
        response = client.post("/generate-report", json={"data": []})

    assert response.status_code == 422


def test_health_contract_is_unchanged():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

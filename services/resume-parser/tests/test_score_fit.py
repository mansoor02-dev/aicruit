import pytest
from fastapi.testclient import TestClient
from app import api

client = TestClient(api.app)


def _payload():
    return {"resume": {"skills": ["python"]}, "job": {"required_skills": ["python"]}}


def test_clamps_over_100_to_100(monkeypatch):
    monkeypatch.setattr(api, "run_score_inference", lambda sp, up: {
        "overall": 150, "skills_match": 200, "experience_match": 50,
        "education_match": 70, "project_match": 60, "rationale": "ok"
    })
    r = client.post("/score-fit", json=_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["overall"] == 100
    assert body["skills_match"] == 100


def test_clamps_below_0_to_0(monkeypatch):
    monkeypatch.setattr(api, "run_score_inference", lambda sp, up: {
        "overall": -5, "skills_match": -10, "experience_match": 50,
        "education_match": 70, "project_match": 60, "rationale": "ok"
    })
    r = client.post("/score-fit", json=_payload())
    assert r.status_code == 200
    assert r.json()["overall"] == 0
    assert r.json()["skills_match"] == 0


def test_502_on_missing_overall(monkeypatch):
    monkeypatch.setattr(api, "run_score_inference", lambda sp, up: {"skills_match": 50})
    r = client.post("/score-fit", json=_payload())
    assert r.status_code == 502


def test_502_on_non_integer_overall(monkeypatch):
    monkeypatch.setattr(api, "run_score_inference", lambda sp, up: {
        "overall": "not a number", "skills_match": 50, "experience_match": 50,
        "education_match": 50, "project_match": 50, "rationale": "x"
    })
    r = client.post("/score-fit", json=_payload())
    assert r.status_code == 502


def test_returns_validated_dict_on_success(monkeypatch):
    monkeypatch.setattr(api, "run_score_inference", lambda sp, up: {
        "overall": 72, "skills_match": 80, "experience_match": 70,
        "education_match": 75, "project_match": 60, "rationale": "Good fit overall."
    })
    r = client.post("/score-fit", json=_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["overall"] == 72
    assert body["rationale"] == "Good fit overall."

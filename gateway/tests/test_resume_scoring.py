import pytest
import httpx
from unittest.mock import AsyncMock, patch
from app.services.resume_scoring import score_resume_for_job


def _resp(status_code: int, json_body):
    req = httpx.Request("POST", "http://test/score-fit")
    return httpx.Response(status_code, json=json_body, request=req)


@pytest.mark.asyncio
async def test_score_returns_int_on_success():
    fake_response = _resp(200, {
        "overall": 72, "skills_match": 80, "experience_match": 70,
        "education_match": 75, "project_match": 60, "rationale": "good"
    })
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        result = await score_resume_for_job({"skills": []}, {"title": "x"})
    assert result == 72


@pytest.mark.asyncio
async def test_score_returns_none_on_502():
    fake_response = _resp(502, {"detail": "scoring_unavailable"})
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        result = await score_resume_for_job({}, {})
    assert result is None


@pytest.mark.asyncio
async def test_score_clamps_to_100():
    fake_response = _resp(200, {
        "overall": 150, "skills_match": 200, "experience_match": 50,
        "education_match": 70, "project_match": 60, "rationale": "x"
    })
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        result = await score_resume_for_job({}, {})
    assert result == 100


@pytest.mark.asyncio
async def test_score_returns_none_on_missing_overall():
    fake_response = _resp(200, {"foo": 1})
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        result = await score_resume_for_job({}, {})
    assert result is None


@pytest.mark.asyncio
async def test_score_returns_none_on_network_error():
    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=httpx.ConnectError("boom"))):
        result = await score_resume_for_job({}, {})
    assert result is None

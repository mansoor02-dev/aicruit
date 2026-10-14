import pytest
from fastapi.testclient import TestClient

from app import api
from app.core.config import Settings
from app.services.resume_pipeline import PipelineResult


client = TestClient(api.app)


def test_parse_endpoint_returns_pipeline_schema(monkeypatch):
    async def mock_parse_resume(contents, ext, settings):
        assert contents.startswith(b"%PDF-")
        assert ext == ".pdf"
        return PipelineResult(
            data={
                "personal_info": {"name": "Alex Candidate"},
                "skills": ["Python"],
                "experience": [],
                "education": [],
                "projects": [],
                "certifications": [],
                "publications": [],
                "interests": [],
                "languages": [],
            },
            elapsed_seconds=0.12,
        )

    monkeypatch.setattr(api, "parse_resume", mock_parse_resume)

    response = client.post(
        "/parse",
        files={"file": ("resume.pdf", b"%PDF-test", "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "resume.pdf"
    assert body["resume"]["personal_info"]["name"] == "Alex Candidate"
    assert body["resume"]["skills"] == ["Python"]


@pytest.mark.parametrize("filename", ["resume.txt", "resume.exe"])
def test_parse_endpoint_rejects_unsupported_extensions(filename):
    response = client.post(
        "/parse",
        files={"file": (filename, b"not a resume", "application/octet-stream")},
    )

    assert response.status_code == 400


def test_health_endpoint_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("api_key", "expected_status"),
    [("", 503), ("test-key", 200)],
)
def test_readiness_endpoint_reflects_gemini_key_configuration(
    monkeypatch, api_key, expected_status
):
    monkeypatch.setattr(
        api,
        "get_settings",
        lambda: Settings(_env_file=None, gemini_api_key=api_key),
    )

    response = client.get("/readiness")

    assert response.status_code == expected_status


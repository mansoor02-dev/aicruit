from types import SimpleNamespace

from app.core.config import Settings
from app.schemas.resume import ResumeExtraction
from app.services import resume_extractor


def test_structured_output_is_primary(monkeypatch):
    expected = ResumeExtraction(skills=["Python"])

    class StructuredModel:
        def invoke(self, messages):
            return expected

    class ChatModel:
        def with_structured_output(self, schema):
            assert schema is ResumeExtraction
            return StructuredModel()

        def invoke(self, messages):
            raise AssertionError("raw fallback should not be called")

    monkeypatch.setattr(resume_extractor, "_build_chain", lambda settings: ChatModel())

    result = resume_extractor._invoke_llm_sync(
        "Python engineer", Settings(_env_file=None, gemini_api_key="test-key")
    )

    assert result is expected


def test_structured_output_failure_falls_back_to_raw_json(monkeypatch):
    class StructuredModel:
        def invoke(self, messages):
            raise ValueError("unsupported structured response")

    class ChatModel:
        def with_structured_output(self, schema):
            return StructuredModel()

        def invoke(self, messages):
            return SimpleNamespace(
                content='{"personal_info": {"name": "Alex"}, "skills": ["Python"]}'
            )

    monkeypatch.setattr(resume_extractor, "_build_chain", lambda settings: ChatModel())

    result = resume_extractor._invoke_llm_sync(
        "Python engineer", Settings(_env_file=None, gemini_api_key="test-key")
    )

    assert isinstance(result, str)
    assert resume_extractor._parse_llm_output(result).skills == ["Python"]

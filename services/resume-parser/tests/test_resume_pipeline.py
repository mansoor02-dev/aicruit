import fitz
import pytest

from app.core.config import Settings
from app.schemas.resume import ResumeExtraction
from app.services import resume_pipeline
from app.services.pdf_extractor import (
    ExtractionResult,
    PDFValidationError,
)
from app.services.resume_extractor import PermanentLLMError
from app.services.resume_pipeline import (
    ExtractionFailedError,
    FileValidationError,
    LLMFailedError,
    parse_resume,
)


def _make_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Alex Candidate Python engineer")
    data = document.tobytes()
    document.close()
    return data


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        gemini_api_key="test-key",
        min_chars_per_page=1,
        ocr_enabled=False,
        cache_enabled=True,
        cache_max_size=8,
    )


@pytest.mark.asyncio
async def test_repeated_identical_file_uses_cached_result(monkeypatch):
    monkeypatch.setattr(resume_pipeline, "_cache", None)
    llm_calls = 0

    async def mock_extract_resume(text, settings):
        nonlocal llm_calls
        llm_calls += 1
        return ResumeExtraction(
            personal_info={"name": "Alex Candidate"},
            skills=["Python"],
        )

    monkeypatch.setattr(resume_pipeline, "extract_resume", mock_extract_resume)
    settings = _settings()
    data = _make_pdf()

    first = await parse_resume(data, ".pdf", settings)
    second = await parse_resume(data, ".pdf", settings)

    assert first.data["personal_info"]["name"] == "Alex Candidate"
    assert second.cached is True
    assert llm_calls == 1


@pytest.mark.asyncio
async def test_pdf_validation_error_maps_to_file_validation_error(monkeypatch):
    monkeypatch.setattr(
        resume_pipeline,
        "extract_text",
        lambda *args: (_ for _ in ()).throw(PDFValidationError("bad PDF")),
    )

    with pytest.raises(FileValidationError, match="bad PDF") as error:
        await parse_resume(b"bad", ".pdf", _settings())

    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_unextractable_text_maps_to_extraction_failed_error(monkeypatch):
    monkeypatch.setattr(
        resume_pipeline,
        "extract_text",
        lambda *args: ExtractionResult(text="", total_pages=1),
    )

    with pytest.raises(ExtractionFailedError):
        await parse_resume(b"%PDF-test", ".pdf", _settings())


@pytest.mark.asyncio
async def test_provider_error_maps_to_llm_failed_error(monkeypatch):
    async def fail_extraction(text, settings):
        raise PermanentLLMError("provider unavailable")

    monkeypatch.setattr(resume_pipeline, "extract_resume", fail_extraction)

    with pytest.raises(LLMFailedError, match="provider error") as error:
        await parse_resume(_make_pdf(), ".pdf", _settings())

    assert error.value.status_code == 502

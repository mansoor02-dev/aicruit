from app.core.config import Settings
from app.services.text_normalizer import (
    _detect_repeated_headers_footers,
    normalize_text,
)


def test_normalization_removes_controls_page_markers_and_long_digit_noise():
    raw = "Name\x00: Alex\nPage 1 of 3\nReference 12345678901234567890"

    result = normalize_text(raw, Settings(_env_file=None))

    assert "\x00" not in result.text
    assert "Page 1 of 3" not in result.text
    assert "12345678901234567890" not in result.text
    assert "Alex" in result.text


def test_repeated_headers_and_footers_are_removed_across_page_chunks():
    header = "Example Corporation Resume"
    raw = (
        f"{header}\nCandidate name\n\n"
        f"{header}\nWork history\n\n"
        f"{header}\nTechnical skills"
    )

    normalized, removed_count = _detect_repeated_headers_footers(raw)

    assert header not in normalized
    assert removed_count >= 3


def test_truncation_preserves_personal_info_skills_and_experience():
    raw = (
        "Alex Candidate\nalex@example.com\n\n"
        "Skills\nPython SQL React " + "skill " * 45 + "\n\n"
        "Experience\nSenior Engineer Acme Corp " + "achievement " * 130 + "\n\n"
        "Education\nUniversity degree " + "education " * 120 + "\n\n"
        "Projects\nProject details " + "project " * 120
    )
    settings = Settings(_env_file=None, max_input_tokens=300)

    result = normalize_text(raw, settings)

    assert result.was_truncated
    assert result.final_word_count <= 300
    assert "Alex Candidate" in result.text
    assert "Skills" in result.text
    assert "Python" in result.text
    assert "Experience" in result.text
    assert "Senior Engineer" in result.text

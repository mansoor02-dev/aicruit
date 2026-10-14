from app.schemas.resume import ResumeExtraction
from app.services.resume_validator import (
    _description_to_list,
    validate_extraction,
)


def test_email_is_cleaned_and_validated():
    valid = validate_extraction(
        ResumeExtraction(personal_info={"email": "  alex # @ example.com "})
    )
    assert valid.data["personal_info"]["email"] == "alex@example.com"
    assert not any("Invalid email" in warning for warning in valid.warnings)

    invalid = validate_extraction(
        ResumeExtraction(personal_info={"email": "not an email"})
    )
    assert any("Invalid email format" in warning for warning in invalid.warnings)


def test_phone_digit_length_validation_warns_for_short_and_long_numbers():
    short = validate_extraction(
        ResumeExtraction(personal_info={"phone": "123-45"})
    )
    long = validate_extraction(
        ResumeExtraction(personal_info={"phone": "1" * 16})
    )

    assert any("too short" in warning for warning in short.warnings)
    assert any("too long" in warning for warning in long.warnings)


def test_linkedin_and_github_urls_are_normalized():
    result = validate_extraction(
        ResumeExtraction(
            personal_info={
                "linkedin": "www.linkedin.com/in/alex",
                "github": "www.github.com/alex",
            }
        )
    )

    assert result.data["personal_info"]["linkedin"] == "https://www.linkedin.com/in/alex"
    assert result.data["personal_info"]["github"] == "https://www.github.com/alex"


def test_descriptions_split_on_newlines_and_bullets():
    assert _description_to_list("Built APIs\n• Improved latency\nOwned releases") == [
        "Built APIs",
        "Improved latency",
        "Owned releases",
    ]

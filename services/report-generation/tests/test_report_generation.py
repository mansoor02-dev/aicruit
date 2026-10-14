import asyncio

from app.schemas.reports import (
    CandidateReport,
    QuestionEntry,
    RecruiterSummary,
    ScoreResult,
)
from app.services.report_service import generate_report
from app.services.scoring import compute_overall_score, score_all_entries


class SuccessfulLLM:
    def __init__(self):
        self.calls = []

    async def complete_structured(self, prompt, response_model, values, **_kwargs):
        self.calls.append((response_model, values))
        if response_model is ScoreResult:
            return ScoreResult(score=4, remark="Explained the implementation clearly.")
        if response_model is RecruiterSummary:
            return RecruiterSummary(
                overall_remark="The candidate demonstrated a solid understanding."
            )
        if response_model is CandidateReport:
            return CandidateReport(
                strengths=["Explained the implementation clearly."],
                improvements=["Add more detail about trade-offs."],
            )
        raise AssertionError(f"Unexpected response schema: {response_model}")


class FailingLLM:
    async def complete_structured(self, *_args, **_kwargs):
        raise RuntimeError("provider unavailable")


def test_report_generation_uses_structured_outputs_and_python_aggregates():
    client = SuccessfulLLM()
    response = asyncio.run(
        generate_report(
            client,
            [
                QuestionEntry(
                    q="How did you improve performance?",
                    a="I profiled and optimized database queries.",
                    category="Databases",
                    ai_score=5,
                    remarks="Clear measurable improvement.",
                ),
                QuestionEntry(
                    q="How do you design an API?",
                    a="I use resource-oriented endpoints and validate requests.",
                    category="Backend",
                ),
            ],
        )
    )

    assert response.recruiter_report.overall_score == 9.0
    assert [item.score for item in response.recruiter_report.category_scores] == [
        10.0,
        8.0,
    ]
    assert response.recruiter_report.overall_remark.startswith("The candidate")
    assert response.candidate_report.strengths == [
        "Explained the implementation clearly."
    ]
    assert [call[0] for call in client.calls] == [
        ScoreResult,
        RecruiterSummary,
        CandidateReport,
    ]


def test_missing_score_uses_provider_failure_fallback_and_empty_answer_is_deterministic():
    entries = [
        QuestionEntry(
            q="Explain transactions.",
            a="A transaction groups operations atomically.",
            category="Databases",
        ),
        QuestionEntry(
            q="Explain indexing.",
            a="",
            category="Databases",
        ),
    ]

    scored = asyncio.run(score_all_entries(FailingLLM(), entries))

    assert [entry.score for entry in scored] == [6.0, 2.0]
    assert scored[0].remark == "Evaluation unavailable; a neutral score was used."
    assert scored[1].remark == "No answer was provided."


def test_supplied_score_is_preserved_when_remark_is_missing():
    class RemarkFailure:
        async def complete_structured(self, *_args, **_kwargs):
            raise RuntimeError("invalid structured response")

    entry = QuestionEntry(
        q="Explain indexing.",
        a="An index helps retrieve rows efficiently.",
        category="Databases",
        ai_score=4,
    )

    scored = asyncio.run(score_all_entries(RemarkFailure(), [entry]))

    assert scored[0].score == 8.0
    assert "supplied score was retained" in scored[0].remark


def test_empty_score_aggregation_is_rejected():
    try:
        compute_overall_score([])
    except ValueError as exc:
        assert "At least one" in str(exc)
    else:
        raise AssertionError("Expected empty aggregation to fail")


def test_report_still_returns_valid_fallbacks_when_all_provider_calls_fail():
    response = asyncio.run(
        generate_report(
            FailingLLM(),
            [
                QuestionEntry(
                    q="Explain indexing.",
                    a="An index supports faster database lookups.",
                    category="Databases",
                )
            ],
        )
    )

    assert response.recruiter_report.overall_score == 6.0
    assert response.recruiter_report.overall_remark
    assert response.candidate_report.strengths
    assert response.candidate_report.improvements


def test_question_and_category_cannot_be_blank():
    for field in ("q", "category"):
        values = {
            "q": "A question",
            "a": "An answer",
            "category": "Technical",
        }
        values[field] = "   "
        try:
            QuestionEntry(**values)
        except ValueError:
            continue
        raise AssertionError(f"Expected blank {field} to be rejected")


def test_generated_schema_enforces_score_and_feedback_constraints():
    for score in (0, 6):
        try:
            ScoreResult(score=score, remark="A remark")
        except ValueError:
            continue
        raise AssertionError(f"Expected score {score} to be rejected")

    for feedback in ([], ["  "]):
        try:
            CandidateReport(strengths=feedback, improvements=["Practise more."])
        except ValueError:
            continue
        raise AssertionError(f"Expected feedback {feedback!r} to be rejected")


def test_fully_supplied_evaluation_skips_per_entry_scoring_call():
    client = SuccessfulLLM()
    result = asyncio.run(
        score_all_entries(
            client,
            [
                QuestionEntry(
                    q="Question",
                    a="Answer",
                    category="General",
                    ai_score=3,
                    remarks="Supplied evaluation.",
                )
            ],
        )
    )

    assert result[0].score == 6.0
    assert client.calls == []

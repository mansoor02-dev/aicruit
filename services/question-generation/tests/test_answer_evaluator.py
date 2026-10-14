import asyncio

from app.services.answer_evaluator import AnswerEvaluator
from app.services.embedding import GeminiEmbedder


class UnusedGeminiEmbedder(GeminiEmbedder):
    def __init__(self):
        pass


class StubLLMClient:
    async def complete_json(
        self,
        prompt,
        response_model,
        system=None,
        model=None,
        max_tokens=1500,
        temperature=0.1,
    ):
        return response_model(
            score=0.8,
            confidence=0.9,
            feedback="Clear explanation.",
            decision="new_topic",
            remarks="The answer is sufficient.",
            score_reason="Covers key points.",
        )


def test_combined_evaluation_uses_structured_async_client():
    evaluator = AnswerEvaluator(
        embedder=UnusedGeminiEmbedder(),
        llm_client=StubLLMClient(),
    )

    evaluation, flow = asyncio.run(
        evaluator.evaluate_combined(
            question="How do indexes improve queries?",
            user_answer=(
                "Indexes improve query performance by locating matching rows "
                "without scanning every record."
            ),
        )
    )

    assert evaluation["pass"] is True
    assert evaluation["feedback"] == "Clear explanation."
    assert flow["decision"] == "new_topic"
    assert flow["score_value"] == 0.8

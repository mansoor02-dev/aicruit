import asyncio

from app.services.question_generator import QuestionGenerator


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
            question="How did you apply cache invalidation in production?"
        )


def test_followup_generation_preserves_question_metadata():
    generator = QuestionGenerator(dataset_questions=[], llm_client=StubLLMClient())

    question, metadata = asyncio.run(
        generator.generate_followup_question(
            previous_question="How does a cache work?",
            previous_answer="I used cache invalidation to prevent stale data.",
            evaluation_result={"decision": "same_topic", "score_value": 0.3},
            topic="Caching",
        )
    )

    assert question == "How did you apply cache invalidation in production?"
    assert metadata["scenario"] == "question_with_same_category"
    assert metadata["is_followup"] is True
    assert metadata["followup_angle"] == "elaboration"

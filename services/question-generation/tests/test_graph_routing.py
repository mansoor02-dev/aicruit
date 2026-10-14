import asyncio

from app.pipelines.orchestrator import InterviewOrchestrator
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
        return response_model(question="How did you use caching in production?")


class StubEvaluator:
    async def evaluate_combined(
        self, question, user_answer, reference_answer=None, is_followup=False
    ):
        return (
            {"confidence": 0.9, "feedback": "Good detail."},
            {
                "decision": "same_topic",
                "score_value": 0.4,
                "remarks": "Probe one detail.",
            },
        )


def test_graph_routes_initial_request_to_introduction():
    generator = QuestionGenerator(dataset_questions=[], llm_client=StubLLMClient())
    orchestrator = InterviewOrchestrator(StubEvaluator(), generator)

    question, metadata = asyncio.run(
        orchestrator.generate_next_question(resume_json={"name": "Sam"})
    )

    assert question.startswith("Hi Sam")
    assert metadata["scenario"] == "1st_question"


def test_graph_routes_evaluated_answer_to_followup():
    generator = QuestionGenerator(dataset_questions=[], llm_client=StubLLMClient())
    orchestrator = InterviewOrchestrator(StubEvaluator(), generator)

    question, metadata = asyncio.run(
        orchestrator.generate_next_question(
            previous_qa_list=[
                {"Q": "How does caching work?", "A": "I use caching to improve performance."}
            ],
            category="Caching",
        )
    )

    assert question == "How did you use caching in production?"
    assert metadata["is_followup"] is True
    assert metadata["evaluation"]["decision"] == "same_topic"
    assert metadata["evaluation"]["score"] == 0.4

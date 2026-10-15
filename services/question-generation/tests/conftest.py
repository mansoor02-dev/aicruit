import random
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from langchain_core.runnables import RunnableLambda

from app.config import Settings
from app.graph.builder import Dependencies, build_question_graph
from app.llm.chains import Chains
from app.schemas.llm import AnswerEvaluation, DraftEmail, GeneratedQuestion
from app.services.dataset import DatasetRepository

ROWS = [
    {
        "Id": "1",
        "Question": "What is caching?",
        "Answer": "Storing copies of data for fast access.",
        "Category": "Caching",
        "Difficulty": "easy",
    },
    {
        "Id": "2",
        "Question": "How does cache invalidation work?",
        "Answer": "Entries expire via TTL or explicit invalidation.",
        "Category": "Caching",
        "Difficulty": "medium",
    },
    {
        "Id": "3",
        "Question": "What is Python?",
        "Answer": "A high-level programming language.",
        "Category": "Python",
        "Difficulty": "easy",
    },
]


class FakeChatModel(RunnableLambda):
    """Runnable stand-in for a chat model with call counting.

    ``with_structured_output`` returns a runnable yielding ``result`` (or
    raising ``exc``). The fallback parser path is exercised by passing a raw
    JSON string as ``result``.
    """

    def __init__(self, result=None, exc=None, calls=None):
        self.calls: list = calls if calls is not None else []
        self._result = result
        self._exc = exc

        async def _run(inputs):
            self.calls.append(inputs)
            if self._exc is not None:
                raise self._exc
            return self._result

        super().__init__(_run)

    def with_structured_output(self, schema):
        return self


def stub_chain(value):
    """Wrap a fixed value (or raised exception) as a chain stub."""
    if isinstance(value, Exception):

        async def _raise(_inputs):
            raise value

        return RunnableLambda(_raise)

    async def _return(_inputs):
        return value

    return RunnableLambda(_return)


PASS_EVALUATION = (
    {
        "pass": True,
        "depth_score": 0.8,
        "confidence": 0.9,
        "feedback": "Clear explanation.",
        "answer_length": 12,
        "needs_followup": False,
    },
    {
        "decision": "new_topic",
        "remarks": "The answer is sufficient.",
        "score_value": 0.8,
        "score_reason": "Covers key points.",
    },
)

FOLLOWUP_EVALUATION = (
    {
        "pass": False,
        "depth_score": 0.4,
        "confidence": 0.9,
        "feedback": "Good detail.",
        "answer_length": 8,
        "needs_followup": True,
    },
    {
        "decision": "same_topic",
        "remarks": "Probe one detail.",
        "score_value": 0.4,
        "score_reason": "Needs elaboration.",
    },
)


def make_stub_chains(
    *,
    evaluation=FOLLOWUP_EVALUATION,
    followup="How did you use caching in production?",
    personalize="How did you apply cache invalidation in production?",
    question="What is caching?",
    email=None,
):
    """Build a ``Chains`` of stubs (no network, no API keys)."""
    return Chains(
        question=stub_chain(question),
        personalize=stub_chain(personalize),
        followup=stub_chain(followup),
        evaluation=stub_chain(evaluation),
        email=stub_chain(
            email
            or DraftEmail(subject="Interview update", body="Thank you.")
        ),
    )


def make_test_graph(
    *,
    chains=None,
    rows=None,
    seed=0,
    settings=None,
):
    """Compile a graph over stub chains and an in-memory dataset."""
    return build_question_graph(
        Dependencies(
            chains=chains or make_stub_chains(),
            dataset=DatasetRepository(list(rows) if rows is not None else ROWS),
            settings=settings or Settings(gemini_api_key="test"),
            rng=random.Random(seed),
        )
    )

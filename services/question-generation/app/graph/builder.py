"""Compile the interview question-generation graph from dependencies."""

from __future__ import annotations

import random
from dataclasses import dataclass

from langgraph.graph import END, START, StateGraph

from app.config import Settings
from app.llm.chains import Chains
from app.services.dataset import DatasetRepository

from .edges import route_after_eval, route_after_validation, route_entry
from .nodes import QuestionGraphNodes
from .state import QuestionGraphInput, QuestionGraphOutput, QuestionGraphState


@dataclass(frozen=True)
class Dependencies:
    """Everything the graph closes over (no module-level singletons)."""

    chains: Chains
    dataset: DatasetRepository
    settings: Settings
    rng: random.Random


def build_question_graph(deps: Dependencies):
    """Build and compile the one-turn question-generation flow."""
    nodes = QuestionGraphNodes(
        chains=deps.chains,
        dataset=deps.dataset,
        settings=deps.settings,
        rng=deps.rng,
    )
    max_followups = deps.settings.max_followups_per_topic

    graph = StateGraph(
        QuestionGraphState,
        input_schema=QuestionGraphInput,
        output_schema=QuestionGraphOutput,
    )
    graph.add_node("evaluate_answer", nodes.evaluate_answer)
    graph.add_node("pick_pool_question", nodes.pick_pool_question)
    graph.add_node("generate_introduction", nodes.generate_introduction)
    graph.add_node("generate_category_opener", nodes.generate_category_opener)
    graph.add_node("generate_followup", nodes.generate_followup)
    graph.add_node(
        "followup_template_fallback", nodes.followup_template_fallback
    )
    graph.add_node("generate_new_topic", nodes.generate_new_topic)

    graph.add_conditional_edges(
        START,
        route_entry,
        {
            "evaluate": "evaluate_answer",
            "pool": "pick_pool_question",
            "introduction": "generate_introduction",
            "opener": "generate_category_opener",
        },
    )
    graph.add_conditional_edges(
        "evaluate_answer",
        lambda state: route_after_eval(
            state, max_followups_per_topic=max_followups
        ),
        {
            "pool": "pick_pool_question",
            "followup": "generate_followup",
            "new_topic": "generate_new_topic",
        },
    )
    graph.add_conditional_edges(
        "generate_followup",
        route_after_validation,
        {
            "done": END,
            "retry": "generate_followup",
            "template": "followup_template_fallback",
        },
    )
    graph.add_edge("pick_pool_question", END)
    graph.add_edge("generate_introduction", END)
    graph.add_edge("generate_category_opener", END)
    graph.add_edge("followup_template_fallback", END)
    graph.add_edge("generate_new_topic", END)
    return graph.compile()

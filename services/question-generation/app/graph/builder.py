from langgraph.graph import END, START, StateGraph

from app.services.answer_evaluator import AnswerEvaluator
from app.services.question_generator import QuestionGenerator

from .edges import route_evaluated_answer, route_initial_request
from .nodes import QuestionGraphNodes
from .state import QuestionGraphState


def build_question_graph(
    evaluator: AnswerEvaluator,
    question_generator: QuestionGenerator,
):
    """Build the interview question-generation flow around shared async services."""
    nodes = QuestionGraphNodes(evaluator, question_generator)
    graph = StateGraph(QuestionGraphState)
    graph.add_node("evaluate_answer", nodes.evaluate_answer)
    graph.add_node("generate_introduction", nodes.generate_introduction)
    graph.add_node("generate_category_opener", nodes.generate_category_opener)
    graph.add_node("generate_followup", nodes.generate_followup)
    graph.add_node("generate_new_topic", nodes.generate_new_topic)

    graph.add_conditional_edges(
        START,
        route_initial_request,
        {
            "introduction": "generate_introduction",
            "category_opener": "generate_category_opener",
            "evaluate_answer": "evaluate_answer",
        },
    )
    graph.add_conditional_edges(
        "evaluate_answer",
        route_evaluated_answer,
        {
            "followup": "generate_followup",
            "new_topic": "generate_new_topic",
        },
    )
    graph.add_edge("generate_introduction", END)
    graph.add_edge("generate_category_opener", END)
    graph.add_edge("generate_followup", END)
    graph.add_edge("generate_new_topic", END)
    return graph.compile()

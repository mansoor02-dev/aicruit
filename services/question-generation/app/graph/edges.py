from .state import QuestionGraphState


def route_initial_request(state: QuestionGraphState) -> str:
    has_history = bool(state.get("previous_qa_list"))
    has_category = bool(state.get("category"))
    if not has_history and not has_category:
        return "introduction"
    if not has_history:
        return "category_opener"
    return "evaluate_answer"


def route_evaluated_answer(state: QuestionGraphState) -> str:
    decision = state.get("flow", {}).get("decision", "new_topic")
    return "followup" if decision in ("deep_dive", "same_topic") else "new_topic"

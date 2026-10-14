"""LangChain chat prompts used by the report-generation workflow."""

from langchain_core.prompts import ChatPromptTemplate

SCORE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a fair senior technical interviewer. Evaluate only the "
            "evidence in the question and answer. Return a score from 1 "
            "(incorrect or no answer) to 5 (excellent and thorough), and a "
            "concise factual remark. Do not infer candidate traits.",
        ),
        (
            "human",
            "Question:\n{question}\n\nCandidate answer:\n{answer}\n\n"
            "Existing score, if provided: {existing_score}\n"
            "Existing remark, if provided: {existing_remark}\n\n"
            "If an existing score is provided, preserve it; only write or "
            "improve the remark. If the answer is empty, use score 1 and "
            "state that no answer was provided.\n\n{format_instructions}",
        ),
    ]
)

RECRUITER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an expert HR analyst. Summarize the observed interview "
            "evidence professionally and concisely. Do not invent facts, "
            "make protected-class inferences, or recalculate scores.",
        ),
        (
            "human",
            "The Python-calculated overall score is {overall_score}/10. "
            "Category scores are {category_scores}.\n\n"
            "Interview evidence:\n{entries_text}\n\n"
            "Write a concise 2-3 sentence recruiter summary grounded only in "
            "these scores and remarks.\n\n{format_instructions}",
        ),
    ]
)

CANDIDATE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a friendly career coach. Be warm, motivating, specific, "
            "and constructive. Do not invent facts or mention numeric scores.",
        ),
        (
            "human",
            "Use the interview evidence below to produce 2-3 specific "
            "strengths and 2-3 polite, actionable areas for improvement. "
            "Base every point on the evidence.\n\n{entries_text}\n\n"
            "{format_instructions}",
        ),
    ]
)

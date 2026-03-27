"""QuadaState: shared state passed between LangGraph nodes."""

from typing import TypedDict


class QuadaState(TypedDict):
    user_query: str
    sql: str | None
    tables_used: list[str]
    resolved_terms: dict
    quality_results: list
    query_results: list
    error: str | None
    escalation_question: str | None
    user_clarification: str | None
    stop_reason: str | None

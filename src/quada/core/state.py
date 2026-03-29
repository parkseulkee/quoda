"""QuadaState: shared state passed between LangGraph nodes."""

from typing import Any, TypedDict


class QuadaState(TypedDict):
    user_query: str
    sql: str | None
    tables_used: list[str]
    resolved_terms: dict[str, Any]
    quality_results: list[dict]
    query_results: list[dict]
    error: str | None
    escalation_question: str | None
    user_clarification: str | None
    interpretation: dict | None
    stop_reason: str | None

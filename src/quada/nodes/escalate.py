"""escalate_node logic: pauses graph with interrupt() and handles user input."""

from langgraph.types import interrupt

from quada.core.state import QuadaState


def run_escalate_node(state: QuadaState) -> dict:
    """Pause graph for user input via interrupt(), then route based on stop_reason."""
    question = state.get("escalation_question", "입력이 필요합니다.")
    user_input: str = interrupt(question)

    match state["stop_reason"]:
        case "term_not_found":
            return {
                "user_clarification": user_input,
                "stop_reason": "term_clarified",
            }
        case "quality_warning":
            if user_input.strip().lower() in ("y", "yes", "예", "네"):
                return {"stop_reason": "execute_approved"}
            return {"stop_reason": "escalation_done"}
        case "sql_error":
            return {
                "user_clarification": f"이전 SQL 실행 오류: {state.get('error', '')}\n사용자 추가 정보: {user_input}",
                "stop_reason": "sql_retry",
            }
        case _:
            return {"stop_reason": "escalation_done"}

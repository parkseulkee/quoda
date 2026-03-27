"""execute_node logic: runs SQL and returns results. No LLM."""

from quada.core.state import QuadaState
from quada.db.executor import SQLExecutor


def run_execute_node(state: QuadaState, executor: SQLExecutor) -> dict:
    """Execute the SQL from state. Returns query_results or sql_error."""
    try:
        rows = executor.execute(state["sql"])
        return {"query_results": rows, "error": None, "stop_reason": "executed"}
    except Exception as e:
        error_msg = str(e)
        return {
            "error": error_msg,
            "stop_reason": "sql_error",
            "escalation_question": (
                f"SQL 실행 중 오류가 발생했습니다:\n{error_msg}\n\n"
                "다른 방식으로 쿼리를 재작성하겠습니다. 계속하시겠습니까? (y/n)"
            ),
        }

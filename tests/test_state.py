from quada.core.state import QuadaState
from quada.tools.base import TerminalResult


def test_quada_state_keys():
    state: QuadaState = {
        "user_query": "test",
        "sql": None,
        "tables_used": [],
        "resolved_terms": {},
        "quality_results": [],
        "query_results": [],
        "error": None,
        "escalation_question": None,
        "user_clarification": None,
        "stop_reason": None,
    }
    assert state["user_query"] == "test"
    assert state["stop_reason"] is None


def test_terminal_result_defaults():
    result = TerminalResult(stop_reason="sql_generated")
    assert result.stop_reason == "sql_generated"
    assert result.state_updates == {}
    assert result.display_value == ""


def test_terminal_result_with_updates():
    result = TerminalResult(
        stop_reason="sql_generated",
        state_updates={"sql": "SELECT 1", "tables_used": ["orders"]},
        display_value="SQL generated successfully",
    )
    assert result.state_updates["sql"] == "SELECT 1"

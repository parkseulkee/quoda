"""Tests for node functions."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from quada.core.state import QuadaState
from quada.nodes.execute import run_execute_node
from quada.nodes.escalate import run_escalate_node
from quada.nodes.semantic_query import run_semantic_query_node
from quada.nodes.quality import run_quality_node
from quada.nodes.interpret import run_interpret_node


def _make_state(**kwargs) -> QuadaState:
    defaults: QuadaState = {
        "user_query": "test",
        "sql": "SELECT 1",
        "tables_used": ["orders"],
        "resolved_terms": {},
        "quality_results": [],
        "query_results": [],
        "error": None,
        "escalation_question": None,
        "user_clarification": None,
        "stop_reason": None,
    }
    defaults.update(kwargs)
    return defaults


def test_execute_node_success():
    executor = MagicMock()
    executor.execute.return_value = [{"count": 42}]
    result = run_execute_node(_make_state(), executor)
    assert result["stop_reason"] == "executed"
    assert result["query_results"] == [{"count": 42}]
    assert result["error"] is None


def test_execute_node_failure():
    executor = MagicMock()
    executor.execute.side_effect = Exception("syntax error")
    result = run_execute_node(_make_state(), executor)
    assert result["stop_reason"] == "sql_error"
    assert "syntax error" in result["error"]
    assert "escalation_question" in result


def test_escalate_node_term_not_found():
    with patch("quada.nodes.escalate.interrupt", return_value="VIP는 연매출 100만원 이상"):
        result = run_escalate_node(_make_state(
            stop_reason="term_not_found",
            escalation_question="VIP 고객이 무엇인가요?",
        ))
    assert result["stop_reason"] == "term_clarified"
    assert result["user_clarification"] == "VIP는 연매출 100만원 이상"


def test_escalate_node_quality_warning_yes():
    with patch("quada.nodes.escalate.interrupt", return_value="y"):
        result = run_escalate_node(_make_state(
            stop_reason="quality_warning",
            escalation_question="품질 경고가 있습니다. 계속할까요?",
        ))
    assert result["stop_reason"] == "execute_approved"


def test_escalate_node_quality_warning_no():
    with patch("quada.nodes.escalate.interrupt", return_value="n"):
        result = run_escalate_node(_make_state(
            stop_reason="quality_warning",
            escalation_question="품질 경고가 있습니다. 계속할까요?",
        ))
    assert result["stop_reason"] == "escalation_done"


def test_escalate_node_sql_error():
    with patch("quada.nodes.escalate.interrupt", return_value="테이블명을 확인해주세요"):
        result = run_escalate_node(_make_state(
            stop_reason="sql_error",
            escalation_question="SQL 오류가 발생했습니다.",
            error="relation does not exist",
        ))
    assert result["stop_reason"] == "sql_retry"
    assert "sql_retry" == result["stop_reason"]


def test_semantic_query_node_calls_agent(tmp_path):
    # Setup: create .quada/metadata_index.json
    quada_dir = tmp_path / ".quada"
    quada_dir.mkdir()
    (quada_dir / "metadata_index.json").write_text('{"entities":[],"metrics":[],"glossary":[]}')

    mock_agent = MagicMock()
    mock_agent.run.return_value = {"stop_reason": "sql_generated", "sql": "SELECT 1", "tables_used": [], "resolved_terms": {}}

    result = run_semantic_query_node(_make_state(), mock_agent, tmp_path)
    assert result["stop_reason"] == "sql_generated"
    mock_agent.run.assert_called_once()


def test_quality_node_calls_agent():
    mock_agent = MagicMock()
    mock_agent.run.return_value = {"stop_reason": "quality_passed"}
    result = run_quality_node(_make_state(), mock_agent)
    assert result["stop_reason"] == "quality_passed"


def test_interpret_node_calls_agent():
    mock_agent = MagicMock()
    mock_agent.run.return_value = {"stop_reason": "done"}
    result = run_interpret_node(_make_state(), mock_agent)
    assert result["stop_reason"] == "done"

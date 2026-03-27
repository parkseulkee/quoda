"""Tests for InterpretAgent — tool call loop based."""
import json
from unittest.mock import MagicMock

from quada.agents.interpret import InterpretAgent
from quada.core.state import QuadaState
from quada.tools.base import TerminalResult


def _make_state(**kwargs) -> QuadaState:
    defaults: QuadaState = {
        "user_query": "이번달 매출",
        "sql": "SELECT SUM(amount) FROM orders",
        "tables_used": ["orders"],
        "resolved_terms": {},
        "quality_results": [],
        "query_results": [{"revenue": 100000000}],
        "error": None,
        "escalation_question": None,
        "user_clarification": None,
        "stop_reason": None,
    }
    defaults.update(kwargs)
    return defaults


def test_run_returns_done():
    mock_client = MagicMock()
    mock_client.completion_with_tools.return_value = (
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "tc1", "type": "function", "function": {
                "name": "finalize_interpretation",
                "arguments": json.dumps({
                    "summary": "매출은 100,000,000원입니다.",
                    "insights": ["전월 대비 증가"],
                    "follow_up_questions": ["월별 추이는?"],
                }),
            }}
        ]},
        [{"name": "finalize_interpretation", "args": {
            "summary": "매출은 100,000,000원입니다.",
            "insights": ["전월 대비 증가"],
            "follow_up_questions": ["월별 추이는?"],
        }, "id": "tc1"}],
    )

    agent = InterpretAgent(llm_client=mock_client)
    result = agent.run(_make_state())

    assert result["stop_reason"] == "done"


def test_run_includes_quality_context():
    """quality_results에 실패한 규칙이 있으면 LLM 메시지에 포함된다."""
    mock_client = MagicMock()
    mock_client.completion_with_tools.return_value = (
        {"role": "assistant", "content": "done"}, []
    )

    agent = InterpretAgent(llm_client=mock_client)
    agent.run(_make_state(quality_results=[{"status": "warn", "rule_name": "null_check", "message": "NULL 3.2%", "value": 0.032}]))

    call_kwargs = mock_client.completion_with_tools.call_args.kwargs
    user_msg = call_kwargs["messages"][1]["content"]
    assert "Quality warnings" in user_msg

"""Tests for BaseAgent tool call loop."""
import json
from unittest.mock import MagicMock

from quada.agents.base import BaseAgent
from quada.tools.base import TerminalResult


def _make_agent():
    mock_client = MagicMock()
    agent = BaseAgent(role="semantic_query", llm_client=mock_client, system_prompt="You are a test agent.")
    return agent, mock_client


def test_tool_loop_no_tool_calls_returns_none():
    """LLM이 tool을 호출하지 않으면 stop_reason=None, state_updates={}."""
    agent, mock_client = _make_agent()
    mock_client.completion_with_tools.return_value = (
        {"role": "assistant", "content": "Done"},
        [],  # no tool calls
    )

    stop_reason, updates = agent.run_tool_loop(
        messages=[{"role": "user", "content": "hi"}],
        tool_definitions=[],
        tool_executors={},
    )

    assert stop_reason is None
    assert updates == {}


def test_tool_loop_terminal_tool_stops_loop():
    """Terminal tool 호출 시 loop 종료 후 TerminalResult 반환."""
    agent, mock_client = _make_agent()

    mock_client.completion_with_tools.side_effect = [
        (
            {"role": "assistant", "content": "", "tool_calls": [{"id": "tc1", "type": "function", "function": {"name": "get_info", "arguments": "{}"}}]},
            [{"name": "get_info", "args": {}, "id": "tc1"}],
        ),
        (
            {"role": "assistant", "content": "", "tool_calls": [{"id": "tc2", "type": "function", "function": {"name": "finish", "arguments": "{}"}}]},
            [{"name": "finish", "args": {}, "id": "tc2"}],
        ),
    ]

    def get_info() -> str:
        return "some info"

    def finish() -> TerminalResult:
        return TerminalResult(
            stop_reason="sql_generated",
            state_updates={"sql": "SELECT 1"},
            display_value="SQL generated",
        )

    stop_reason, updates = agent.run_tool_loop(
        messages=[{"role": "user", "content": "go"}],
        tool_definitions=[],
        tool_executors={"get_info": get_info, "finish": finish},
    )

    assert stop_reason == "sql_generated"
    assert updates == {"sql": "SELECT 1"}
    assert mock_client.completion_with_tools.call_count == 2


def test_tool_loop_unknown_tool_returns_error_to_llm():
    """모르는 tool 호출 시 에러 메시지를 LLM에 반환하고 loop 계속."""
    agent, mock_client = _make_agent()

    mock_client.completion_with_tools.side_effect = [
        (
            {"role": "assistant", "content": "", "tool_calls": [{"id": "tc1", "type": "function", "function": {"name": "unknown_tool", "arguments": "{}"}}]},
            [{"name": "unknown_tool", "args": {}, "id": "tc1"}],
        ),
        ({"role": "assistant", "content": "ok"}, []),
    ]

    stop_reason, updates = agent.run_tool_loop(
        messages=[{"role": "user", "content": "go"}],
        tool_definitions=[],
        tool_executors={},
    )

    assert stop_reason is None
    # 두 번째 LLM 호출의 messages에 tool error 포함 확인
    second_call_messages = mock_client.completion_with_tools.call_args_list[1][1]["messages"]
    tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert "unknown" in tool_msgs[0]["content"].lower()

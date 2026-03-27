"""Tests for LLMClient.completion_with_tools."""
import json
from unittest.mock import MagicMock, patch

from quada.llm.client import LLMClient
from quada.core.config import LLMConfig, LLMModelConfig, AgentsLLMConfig


def _make_client():
    config = LLMConfig(
        orchestrator=LLMModelConfig(provider="anthropic", model="claude-haiku-4-5-20251001"),
        agents=AgentsLLMConfig(
            semantic_query=LLMModelConfig(provider="anthropic", model="claude-haiku-4-5-20251001"),
            quality=LLMModelConfig(provider="anthropic", model="claude-haiku-4-5-20251001"),
            interpret=LLMModelConfig(provider="anthropic", model="claude-haiku-4-5-20251001"),
        ),
    )
    return LLMClient(config)


def test_completion_with_tools_no_tool_calls():
    client = _make_client()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Hello"
    mock_response.choices[0].message.tool_calls = None

    with patch("quada.llm.client.litellm_completion", return_value=mock_response):
        msg, tool_calls = client.completion_with_tools(
            role="semantic_query",
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
        )

    assert msg == {"role": "assistant", "content": "Hello"}
    assert tool_calls == []


def test_completion_with_tools_with_tool_call():
    client = _make_client()

    tc = MagicMock()
    tc.id = "call_123"
    tc.function.name = "get_entity_definition"
    tc.function.arguments = json.dumps({"name": "customer"})

    mock_response = MagicMock()
    mock_response.choices[0].message.content = ""
    mock_response.choices[0].message.tool_calls = [tc]

    with patch("quada.llm.client.litellm_completion", return_value=mock_response):
        msg, tool_calls = client.completion_with_tools(
            role="semantic_query",
            messages=[{"role": "user", "content": "hi"}],
            tools=[{"type": "function", "function": {"name": "get_entity_definition", "parameters": {}}}],
        )

    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "get_entity_definition"
    assert tool_calls[0]["args"] == {"name": "customer"}
    assert tool_calls[0]["id"] == "call_123"
    assert "tool_calls" in msg

from unittest.mock import MagicMock

import pytest

from quada.agents.base import BaseAgent


def test_base_agent_call_llm():
    llm_client = MagicMock()
    llm_client.completion.return_value = '{"result": "ok"}'

    agent = BaseAgent(role="semantic_query", llm_client=llm_client, system_prompt="You are a test agent.")
    response = agent.call_llm("test message")

    assert response == '{"result": "ok"}'
    llm_client.completion.assert_called_once()
    call_args = llm_client.completion.call_args
    assert call_args.kwargs["role"] == "semantic_query"
    messages = call_args.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are a test agent."
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "test message"


def test_base_agent_call_llm_with_context():
    llm_client = MagicMock()
    llm_client.completion.return_value = "response"

    agent = BaseAgent(role="quality", llm_client=llm_client, system_prompt="System.")
    response = agent.call_llm("query", context={"key": "value"})

    call_args = llm_client.completion.call_args
    messages = call_args.kwargs["messages"]
    assert "key" in messages[1]["content"]

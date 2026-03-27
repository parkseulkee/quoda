from unittest.mock import patch, MagicMock

import pytest

from quada.core.config import LLMModelConfig, LLMConfig, AgentsLLMConfig
from quada.llm.client import LLMClient, _strip_code_fences


@pytest.fixture
def llm_config():
    return LLMConfig(
        orchestrator=LLMModelConfig(provider="anthropic", model="claude-opus-4-6"),
        agents=AgentsLLMConfig(
            semantic_query=LLMModelConfig(provider="anthropic", model="claude-haiku-4-5-20251001"),
            quality=LLMModelConfig(provider="openai", model="gpt-4o-mini"),
            interpret=LLMModelConfig(provider="anthropic", model="claude-sonnet-4-6"),
        ),
    )


def test_get_model_string_for_orchestrator(llm_config):
    client = LLMClient(llm_config)
    assert client.get_model_string("orchestrator") == "anthropic/claude-opus-4-6"


def test_get_model_string_for_agent(llm_config):
    client = LLMClient(llm_config)
    assert client.get_model_string("semantic_query") == "anthropic/claude-haiku-4-5-20251001"
    assert client.get_model_string("quality") == "openai/gpt-4o-mini"
    assert client.get_model_string("interpret") == "anthropic/claude-sonnet-4-6"


def test_get_model_string_invalid_role(llm_config):
    client = LLMClient(llm_config)
    with pytest.raises(ValueError, match="Unknown role"):
        client.get_model_string("unknown_agent")


@patch("quada.llm.client.litellm_completion")
def test_completion_calls_litellm(mock_completion, llm_config):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "test response"
    mock_completion.return_value = mock_response

    client = LLMClient(llm_config)
    result = client.completion(
        role="orchestrator",
        messages=[{"role": "user", "content": "hello"}],
    )
    assert result == "test response"
    mock_completion.assert_called_once_with(
        model="anthropic/claude-opus-4-6",
        messages=[{"role": "user", "content": "hello"}],
    )


class TestStripCodeFences:
    def test_strips_json_fence(self):
        text = '```json\n{"key": "value"}\n```'
        assert _strip_code_fences(text) == '{"key": "value"}'

    def test_strips_plain_fence(self):
        text = '```\nSELECT 1\n```'
        assert _strip_code_fences(text) == "SELECT 1"

    def test_strips_sql_fence(self):
        text = '```sql\nSELECT * FROM orders;\n```'
        assert _strip_code_fences(text) == "SELECT * FROM orders;"

    def test_no_fence_passthrough(self):
        text = '{"key": "value"}'
        assert _strip_code_fences(text) == '{"key": "value"}'

    def test_strips_whitespace(self):
        text = '  ```json\n{"a": 1}\n```  '
        assert _strip_code_fences(text) == '{"a": 1}'

"""Tests for the new QualityAgent (tool call loop pattern)."""
from unittest.mock import MagicMock

import pytest

from quada.agents.quality import QualityAgent
from quada.semantic.models import QualityRule


@pytest.fixture
def quality_agent():
    llm_client = MagicMock()
    executor = MagicMock()
    rules = [
        QualityRule(name="orders_status_not_null", type="null_ratio", table="orders", column="status", threshold=0.01),
    ]
    return QualityAgent(llm_client=llm_client, rules=rules, executor=executor)


def test_quality_agent_run_returns_passed(quality_agent):
    """QualityAgent.run() returns stop_reason='quality_passed' when LLM calls report_quality_passed."""
    # Simulate LLM calling report_quality_passed terminal tool
    quality_agent.llm_client.completion_with_tools.return_value = (
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "tc1", "type": "function", "function": {"name": "report_quality_passed", "arguments": "{}"}}
        ]},
        [{"id": "tc1", "name": "report_quality_passed", "args": {}}],
    )

    state = {
        "sql": "SELECT SUM(amount) FROM orders",
        "tables_used": ["orders"],
        "user_query": "총 매출은?",
    }
    result = quality_agent.run(state)
    assert result["stop_reason"] == "quality_passed"


def test_quality_agent_run_returns_warning(quality_agent):
    """QualityAgent.run() returns stop_reason='quality_warning' with escalation_question."""
    quality_agent.llm_client.completion_with_tools.return_value = (
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "tc1", "type": "function", "function": {
                "name": "report_quality_warning",
                "arguments": '{"message": "status NULL 3%", "question": "계속 진행? (y/n)"}',
            }}
        ]},
        [{"id": "tc1", "name": "report_quality_warning", "args": {"message": "status NULL 3%", "question": "계속 진행? (y/n)"}}],
    )

    state = {
        "sql": "SELECT SUM(amount) FROM orders",
        "tables_used": ["orders"],
        "user_query": "총 매출은?",
    }
    result = quality_agent.run(state)
    assert result["stop_reason"] == "quality_warning"
    assert result["escalation_question"] == "계속 진행? (y/n)"

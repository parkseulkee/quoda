"""Tests for SemanticQueryAgent."""
import json
from unittest.mock import MagicMock

from quada.agents.semantic_query import SemanticQueryAgent
from quada.core.state import QuadaState
from quada.semantic.index import MetadataIndex
from quada.semantic.models import Entity, Column, Metric, GlossaryTerm
from quada.semantic.loader import SemanticContext
from quada.tools.base import TerminalResult


def _make_agent_and_deps():
    mock_client = MagicMock()
    context = SemanticContext(
        entities=[Entity(
            name="customer", table="customers",
            columns=[Column(name="id", type="integer", primary_key=True)],
            relationships=[]
        )],
        metrics=[Metric(
            name="revenue", type="sum", expression="orders.amount",
            entities=["order"], dimensions=[], aliases=[]
        )],
        glossary=[GlossaryTerm(
            term="이탈 고객", definition="90일 구매 없는 고객",
            sql_condition="...", entity="customer", aliases=[]
        )],
    )
    index = MetadataIndex.build(context)
    agent = SemanticQueryAgent(llm_client=mock_client, semantic_context=context)
    return agent, mock_client, index


def _make_state(**kwargs) -> QuadaState:
    defaults = {
        "user_query": "고객 수 알려줘",
        "sql": None, "tables_used": [], "resolved_terms": {},
        "quality_results": [], "query_results": [], "error": None,
        "escalation_question": None, "user_clarification": None, "stop_reason": None,
    }
    defaults.update(kwargs)
    return defaults


def test_run_returns_sql_generated():
    agent, mock_client, index = _make_agent_and_deps()

    mock_client.completion_with_tools.return_value = (
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "tc1", "type": "function", "function": {
                "name": "generate_sql",
                "arguments": json.dumps({
                    "sql": "SELECT COUNT(*) FROM customers",
                    "tables_used": ["customers"],
                    "resolved_terms": {},
                }),
            }}
        ]},
        [{"name": "generate_sql", "args": {
            "sql": "SELECT COUNT(*) FROM customers",
            "tables_used": ["customers"],
            "resolved_terms": {},
        }, "id": "tc1"}],
    )

    result = agent.run(_make_state(), index)

    assert result["stop_reason"] == "sql_generated"
    assert result["sql"] == "SELECT COUNT(*) FROM customers"
    assert result["tables_used"] == ["customers"]


def test_run_returns_term_not_found():
    agent, mock_client, index = _make_agent_and_deps()

    mock_client.completion_with_tools.return_value = (
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "tc1", "type": "function", "function": {
                "name": "report_term_not_found",
                "arguments": json.dumps({
                    "term": "VIP 고객",
                    "question": "'VIP 고객'의 정의를 알려주세요.",
                }),
            }}
        ]},
        [{"name": "report_term_not_found", "args": {
            "term": "VIP 고객",
            "question": "'VIP 고객'의 정의를 알려주세요.",
        }, "id": "tc1"}],
    )

    result = agent.run(_make_state(user_query="VIP 고객 매출"), index)

    assert result["stop_reason"] == "term_not_found"
    assert result["escalation_question"] == "'VIP 고객'의 정의를 알려주세요."


def test_run_includes_clarification_in_context():
    """user_clarification이 있으면 LLM 메시지에 포함된다."""
    agent, mock_client, index = _make_agent_and_deps()

    mock_client.completion_with_tools.return_value = (
        {"role": "assistant", "content": "done"}, []
    )

    agent.run(_make_state(user_clarification="VIP는 연매출 100만원 이상"), index)

    call_kwargs = mock_client.completion_with_tools.call_args[1]
    user_msg = call_kwargs["messages"][1]["content"]
    assert "VIP는 연매출 100만원 이상" in user_msg


def test_run_llm_stops_without_terminal_returns_escalation():
    """LLM이 terminal tool 없이 멈추면 escalation으로 처리."""
    agent, mock_client, index = _make_agent_and_deps()

    mock_client.completion_with_tools.return_value = (
        {"role": "assistant", "content": "I cannot process this"}, []
    )

    result = agent.run(_make_state(), index)

    assert result["stop_reason"] == "term_not_found"
    assert "escalation_question" in result

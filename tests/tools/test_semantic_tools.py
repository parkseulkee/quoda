"""Tests for semantic tools — pure functions, no LLM calls."""
from quada.semantic.models import Entity, Column, Metric, GlossaryTerm, Relationship
from quada.semantic.loader import SemanticContext
from quada.tools.base import TerminalResult
from quada.tools.semantic_tools import (
    get_entity_definition,
    get_metric_definition,
    get_glossary_term,
    generate_sql,
    report_term_not_found,
)


def _make_context():
    entities = [
        Entity(
            name="customer",
            table="public.customers",
            description="서비스 고객",
            columns=[
                Column(name="id", type="integer", primary_key=True),
                Column(name="email", type="string"),
            ],
            relationships=[],
        )
    ]
    metrics = [
        Metric(
            name="revenue",
            description="총 매출",
            type="sum",
            expression="orders.amount",
            filter="orders.status = 'completed'",
            entities=["order"],
            dimensions=[],
            aliases=["매출"],
        )
    ]
    glossary = [
        GlossaryTerm(
            term="이탈 고객",
            definition="최근 90일 구매 없는 고객",
            sql_condition="customer.last_purchase_date < NOW() - INTERVAL '90 days'",
            entity="customer",
            aliases=["churned customer"],
        )
    ]
    return SemanticContext(entities=entities, metrics=metrics, glossary=glossary)


def test_get_entity_definition_found():
    ctx = _make_context()
    result = get_entity_definition("customer", ctx)
    assert isinstance(result, dict)
    assert result["name"] == "customer"
    assert result["table"] == "public.customers"
    assert any(c["name"] == "id" for c in result["columns"])


def test_get_entity_definition_not_found():
    ctx = _make_context()
    result = get_entity_definition("nonexistent", ctx)
    assert "error" in result


def test_get_metric_definition_found():
    ctx = _make_context()
    result = get_metric_definition("revenue", ctx)
    assert isinstance(result, dict)
    assert result["name"] == "revenue"
    assert result["expression"] == "orders.amount"


def test_get_metric_definition_not_found():
    ctx = _make_context()
    result = get_metric_definition("nonexistent", ctx)
    assert "error" in result


def test_get_glossary_term_found():
    ctx = _make_context()
    result = get_glossary_term("이탈 고객", ctx)
    assert isinstance(result, dict)
    assert result["term"] == "이탈 고객"
    assert "sql_condition" in result
    assert "aliases" not in result


def test_get_glossary_term_not_found():
    ctx = _make_context()
    result = get_glossary_term("없는 용어", ctx)
    assert "error" in result


def test_generate_sql_returns_terminal_result():
    result = generate_sql(
        sql="SELECT SUM(amount) FROM orders",
        tables_used=["orders"],
        resolved_terms={"매출": "revenue"},
    )
    assert isinstance(result, TerminalResult)
    assert result.stop_reason == "sql_generated"
    assert result.state_updates["sql"] == "SELECT SUM(amount) FROM orders"
    assert result.state_updates["tables_used"] == ["orders"]


def test_report_term_not_found_returns_terminal_result():
    result = report_term_not_found(
        term="알 수 없는 용어",
        question="'알 수 없는 용어'의 정의를 입력해주세요.",
    )
    assert isinstance(result, TerminalResult)
    assert result.stop_reason == "term_not_found"
    assert result.state_updates["escalation_question"] == "'알 수 없는 용어'의 정의를 입력해주세요."

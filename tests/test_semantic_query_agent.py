import json
from unittest.mock import MagicMock

import pytest

from quada.agents.semantic_query import SemanticQueryAgent
from quada.semantic.models import Entity, Column, Relationship, Metric, GlossaryTerm, Dimension
from quada.semantic.loader import SemanticContext
from quada.semantic.matcher import SemanticMatcher


@pytest.fixture
def semantic_context():
    return SemanticContext(
        entities=[
            Entity(
                name="customer",
                table="public.customers",
                columns=[
                    Column(name="id", type="integer", primary_key=True),
                    Column(name="last_purchase_date", type="timestamp"),
                ],
                relationships=[
                    Relationship(name="orders", type="one_to_many", entity="order", join="customer.id = order.customer_id"),
                ],
            ),
            Entity(
                name="order",
                table="public.orders",
                columns=[
                    Column(name="id", type="integer", primary_key=True),
                    Column(name="customer_id", type="integer"),
                    Column(name="amount", type="float"),
                    Column(name="status", type="string"),
                    Column(name="order_date", type="timestamp"),
                ],
                relationships=[],
            ),
        ],
        metrics=[
            Metric(
                name="revenue",
                description="완료된 주문의 총 매출액",
                type="sum",
                expression="orders.amount",
                filter="orders.status = 'completed'",
                entities=["order"],
                dimensions=[Dimension(name="period", expression="DATE_TRUNC('month', orders.order_date)")],
                aliases=["매출", "revenue"],
            ),
        ],
        glossary=[
            GlossaryTerm(
                term="이탈 고객",
                definition="최근 90일간 구매 이력이 없는 고객",
                sql_condition="customer.last_purchase_date < NOW() - INTERVAL '90 days'",
                entity="customer",
                aliases=["churned customer"],
            ),
        ],
    )


@pytest.fixture
def agent(semantic_context):
    llm_client = MagicMock()
    llm_client.completion.return_value = json.dumps({
        "resolved_terms": {"이탈 고객": "최근 90일간 구매 이력 없는 고객"},
        "sql": "SELECT SUM(o.amount) FROM public.customers c JOIN public.orders o ON c.id = o.customer_id WHERE o.status = 'completed' AND c.last_purchase_date < NOW() - INTERVAL '90 days'",
        "tables_used": ["public.customers", "public.orders"],
        "explanation": "이탈 고객의 매출 합계",
    })
    matcher = SemanticMatcher(
        glossary=semantic_context.glossary,
        metrics=semantic_context.metrics,
        llm_client=llm_client,
    )
    return SemanticQueryAgent(
        llm_client=llm_client,
        semantic_context=semantic_context,
        matcher=matcher,
    )


def test_generate_sql(agent):
    result = agent.generate_sql("이탈 고객의 매출 보여줘")
    assert result.sql is not None
    assert "public.orders" in result.sql or "orders" in result.sql
    assert len(result.tables_used) > 0


def test_generate_sql_returns_tables(agent):
    result = agent.generate_sql("이탈 고객의 매출 보여줘")
    assert "public.customers" in result.tables_used or "public.orders" in result.tables_used

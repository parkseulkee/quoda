import pytest

from quada.semantic.models import (
    Column,
    Entity,
    Relationship,
    Metric,
    Dimension,
    DerivedMetric,
    GlossaryTerm,
    QualityRule,
    QualityConfig,
)


def test_entity_model():
    entity = Entity(
        name="customer",
        description="서비스에 가입한 고객",
        table="public.customers",
        columns=[
            Column(name="id", type="integer", primary_key=True),
            Column(name="name", type="string"),
        ],
        relationships=[
            Relationship(name="orders", type="one_to_many", entity="order", join="customer.id = order.customer_id")
        ],
    )
    assert entity.name == "customer"
    assert entity.columns[0].primary_key is True
    assert entity.columns[1].primary_key is False
    assert entity.relationships[0].type == "one_to_many"


def test_metric_model():
    metric = Metric(
        name="revenue",
        description="완료된 주문의 총 매출액",
        type="sum",
        expression="orders.amount",
        filter="orders.status = 'completed'",
        entities=["order"],
        dimensions=[
            Dimension(name="period", expression="DATE_TRUNC('month', orders.order_date)")
        ],
        aliases=["매출", "매출액", "revenue"],
    )
    assert metric.type == "sum"
    assert len(metric.aliases) == 3
    assert metric.filter == "orders.status = 'completed'"


def test_derived_metric_model():
    metric = DerivedMetric(
        name="arpu",
        description="인당 매출",
        expression="revenue / dau",
        aliases=["ARPU", "객단가"],
    )
    assert metric.expression == "revenue / dau"


def test_glossary_term_model():
    term = GlossaryTerm(
        term="이탈 고객",
        definition="최근 90일간 구매 이력이 없는 고객",
        sql_condition="customer.last_purchase_date < NOW() - INTERVAL '90 days'",
        entity="customer",
        aliases=["churned customer", "이탈자"],
    )
    assert term.term == "이탈 고객"
    assert len(term.aliases) == 2


def test_metric_type_validation():
    with pytest.raises(ValueError):
        Metric(
            name="bad",
            description="bad",
            type="invalid_type",
            expression="x",
            entities=["x"],
        )

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from quada.semantic.matcher import SemanticMatcher, MatchResult
from quada.semantic.models import GlossaryTerm, Metric


@pytest.fixture
def glossary():
    return [
        GlossaryTerm(
            term="이탈 고객",
            definition="최근 90일간 구매 이력이 없는 고객",
            sql_condition="customer.last_purchase_date < NOW() - INTERVAL '90 days'",
            entity="customer",
            aliases=["churned customer", "이탈자", "비활성 고객"],
        ),
        GlossaryTerm(
            term="신규 고객",
            definition="최근 30일 이내 가입한 고객",
            sql_condition="customer.created_at >= NOW() - INTERVAL '30 days'",
            entity="customer",
            aliases=["new customer", "신규 가입자"],
        ),
    ]


@pytest.fixture
def metrics():
    return [
        Metric(
            name="revenue",
            description="매출",
            type="sum",
            expression="orders.amount",
            entities=["order"],
            aliases=["매출", "매출액", "revenue", "sales"],
        ),
    ]


@pytest.fixture
def matcher(glossary, metrics):
    llm_client = MagicMock()
    return SemanticMatcher(glossary=glossary, metrics=metrics, llm_client=llm_client)


def test_exact_match_glossary(matcher):
    result = matcher.match_term("이탈 고객")
    assert result.matched is True
    assert result.source_type == "glossary"
    assert result.term.term == "이탈 고객"
    assert result.match_type == "exact"


def test_exact_match_alias(matcher):
    result = matcher.match_term("churned customer")
    assert result.matched is True
    assert result.term.term == "이탈 고객"
    assert result.match_type == "exact"


def test_exact_match_metric(matcher):
    result = matcher.match_metric("매출")
    assert result.matched is True
    assert result.source_type == "metric"
    assert result.metric.name == "revenue"


def test_exact_match_metric_alias(matcher):
    result = matcher.match_metric("sales")
    assert result.matched is True
    assert result.metric.name == "revenue"


def test_no_exact_match_returns_unmatched(matcher):
    matcher.llm_client.completion.return_value = '{"match": null, "confidence": "none"}'
    result = matcher.match_term("VIP 고객")
    assert result.matched is False
    assert result.match_type == "none"


def test_fuzzy_match_calls_llm(matcher):
    matcher.llm_client.completion.return_value = '{"match": "이탈 고객", "confidence": "high"}'
    result = matcher.match_term("비활성 유저")
    assert result.matched is True
    assert result.match_type == "fuzzy"
    assert result.term.term == "이탈 고객"
    assert result.confidence == "high"
    matcher.llm_client.completion.assert_called_once()


def test_learn_alias(matcher, tmp_path):
    glossary_file = tmp_path / "terms.yaml"
    glossary_file.write_text("""glossary:
  - term: "이탈 고객"
    definition: "최근 90일간 구매 이력이 없는 고객"
    sql_condition: "customer.last_purchase_date < NOW() - INTERVAL '90 days'"
    entity: customer
    aliases:
      - "churned customer"
      - "이탈자"
      - "비활성 고객"
""")
    matcher.learn_alias("이탈 고객", "비활성 유저", glossary_file)
    # Check in-memory update
    term = next(t for t in matcher.glossary if t.term == "이탈 고객")
    assert "비활성 유저" in term.aliases

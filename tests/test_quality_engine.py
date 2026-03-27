import asyncio
from unittest.mock import MagicMock, AsyncMock

import pytest

from quada.quality.rules import (
    FreshnessRule,
    NullRatioRule,
    ValueRangeRule,
    UniqueRule,
    CustomSQLRule,
)
from quada.quality.engine import QualityEngine, QualityCheckResult, build_combined_sql
from quada.semantic.models import QualityRule


def test_build_combined_sql_single_table():
    rules = [
        QualityRule(name="freshness", type="freshness", table="orders", column="updated_at", threshold="24 hours"),
        QualityRule(name="null_check", type="null_ratio", table="orders", column="status", threshold=0.01),
        QualityRule(name="range_check", type="value_range", table="orders", column="amount", min=0, max=100000000),
    ]
    sql = build_combined_sql("orders", rules, where_clause="order_date >= '2026-02-01'")
    assert "MAX(updated_at)" in sql
    assert "status" in sql
    assert "amount" in sql
    assert "WHERE order_date >= '2026-02-01'" in sql


def test_build_combined_sql_no_rules():
    sql = build_combined_sql("orders", [], where_clause=None)
    assert sql is None


def test_freshness_rule_pass():
    rule = FreshnessRule(name="test", table="orders", column="updated_at", threshold="24 hours")
    from datetime import datetime, timedelta, timezone
    recent = datetime.now(timezone.utc) - timedelta(hours=2)
    result = rule.evaluate({"max_updated_at": recent})
    assert result.status == "pass"


def test_freshness_rule_fail():
    rule = FreshnessRule(name="test", table="orders", column="updated_at", threshold="24 hours")
    from datetime import datetime, timedelta, timezone
    old = datetime.now(timezone.utc) - timedelta(hours=48)
    result = rule.evaluate({"max_updated_at": old})
    assert result.status == "warn"


def test_null_ratio_rule_pass():
    rule = NullRatioRule(name="test", table="orders", column="status", threshold=0.05)
    result = rule.evaluate({"null_ratio_status": 0.01})
    assert result.status == "pass"


def test_null_ratio_rule_fail():
    rule = NullRatioRule(name="test", table="orders", column="status", threshold=0.01)
    result = rule.evaluate({"null_ratio_status": 0.05})
    assert result.status == "warn"


def test_value_range_rule_pass():
    rule = ValueRangeRule(name="test", table="orders", column="amount", min_val=0, max_val=100)
    result = rule.evaluate({"out_of_range_amount": 0})
    assert result.status == "pass"


def test_value_range_rule_fail():
    rule = ValueRangeRule(name="test", table="orders", column="amount", min_val=0, max_val=100)
    result = rule.evaluate({"out_of_range_amount": 5})
    assert result.status == "warn"

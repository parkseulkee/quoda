"""Quality engine: builds combined SQL, runs checks in parallel, aggregates results."""

import asyncio
from dataclasses import dataclass, field

from quada.db.executor import SQLExecutor
from quada.semantic.models import QualityRule
from quada.quality.rules import (
    FreshnessRule,
    NullRatioRule,
    ValueRangeRule,
    UniqueRule,
    CustomSQLRule,
    RuleResult,
)


@dataclass
class QualityCheckResult:
    """Aggregated quality check results."""
    results: list[RuleResult] = field(default_factory=list)

    @property
    def overall_status(self) -> str:
        statuses = [r.status for r in self.results]
        if "fail" in statuses:
            return "fail"
        if "warn" in statuses:
            return "warn"
        return "pass"

    @property
    def warnings(self) -> list[RuleResult]:
        return [r for r in self.results if r.status == "warn"]


def _create_typed_rule(rule: QualityRule):
    """Convert a QualityRule Pydantic model to a typed rule object."""
    if rule.type == "freshness":
        return FreshnessRule(rule.name, rule.table, rule.column, str(rule.threshold))
    elif rule.type == "null_ratio":
        return NullRatioRule(rule.name, rule.table, rule.column, float(rule.threshold))
    elif rule.type == "value_range":
        return ValueRangeRule(rule.name, rule.table, rule.column, float(rule.min), float(rule.max))
    elif rule.type == "unique":
        return UniqueRule(rule.name, rule.table, rule.column)
    elif rule.type == "custom_sql":
        return CustomSQLRule(rule.name, rule.table, rule.query, rule.threshold)
    else:
        raise ValueError(f"Unknown rule type: {rule.type}")


def build_combined_sql(
    table: str,
    rules: list[QualityRule],
    where_clause: str | None = None,
) -> str | None:
    """Build a single SQL query combining multiple rule checks for one table."""
    combinable_types = {"freshness", "null_ratio", "value_range", "unique"}
    combinable = [r for r in rules if r.type in combinable_types]
    if not combinable:
        return None

    fragments = []
    for rule in combinable:
        typed = _create_typed_rule(rule)
        fragments.append(typed.sql_fragment())

    select_clause = ",\n  ".join(fragments)
    sql = f"SELECT\n  {select_clause}\nFROM {table}"
    if where_clause:
        sql += f"\nWHERE {where_clause}"
    return sql


class QualityEngine:
    """Runs quality checks: combines rules into minimal queries, runs in parallel."""

    def __init__(self, executor: SQLExecutor):
        self.executor = executor

    async def check(
        self,
        rules: list[QualityRule],
        tables: list[str],
        where_clause: str | None = None,
    ) -> QualityCheckResult:
        """Run all quality rules for the given tables."""
        all_results: list[RuleResult] = []
        tasks = []

        for table in tables:
            table_rules = [r for r in rules if r.table == table]
            combinable = [r for r in table_rules if r.type != "custom_sql"]
            custom = [r for r in table_rules if r.type == "custom_sql"]

            # Combined query for combinable rules
            if combinable:
                tasks.append(self._run_combined(table, combinable, where_clause))

            # Individual queries for custom SQL rules
            for rule in custom:
                tasks.append(self._run_custom(rule))

        results = await asyncio.gather(*tasks)
        for result_list in results:
            all_results.extend(result_list)

        return QualityCheckResult(results=all_results)

    async def _run_combined(
        self, table: str, rules: list[QualityRule], where_clause: str | None
    ) -> list[RuleResult]:
        """Run combined SQL for a table's combinable rules."""
        sql = build_combined_sql(table, rules, where_clause)
        if not sql:
            return []
        rows = self.executor.execute(sql)
        if not rows:
            return [RuleResult(r.name, "warn", f"No data in {table}") for r in rules]
        row = rows[0]
        results = []
        for rule in rules:
            typed = _create_typed_rule(rule)
            results.append(typed.evaluate(row))
        return results

    async def _run_custom(self, rule: QualityRule) -> list[RuleResult]:
        """Run a custom SQL quality rule."""
        typed = _create_typed_rule(rule)
        rows = self.executor.execute(rule.query)
        row = rows[0] if rows else {"violations": 0}
        return [typed.evaluate(row)]

"""Quality tools: pure functions used by QualityAgent's tool call loop."""

import asyncio

from quada.db.executor import SQLExecutor
from quada.quality.engine import QualityEngine, QualityCheckResult
from quada.semantic.models import QualityRule
from quada.tools.base import TerminalResult


def get_quality_rules(tables: list[str], rules: list[QualityRule]) -> dict:
    """Get quality rules applicable to the given tables."""
    applicable = [
        {
            "name": r.name,
            "type": r.type,
            "table": r.table,
            "column": r.column,
            "threshold": r.threshold,
        }
        for r in rules
        if r.table in tables
    ]
    return {"rules": applicable, "count": len(applicable)}


def run_quality_checks(
    tables: list[str],
    rules: list[QualityRule],
    executor: SQLExecutor,
) -> dict:
    """Run all quality checks for the given tables and return results."""
    engine = QualityEngine(executor)
    result: QualityCheckResult = asyncio.run(
        engine.check(rules=rules, tables=tables, where_clause=None)
    )
    return {
        "overall_status": result.overall_status,
        "results": [
            {
                "rule_name": r.rule_name,
                "status": r.status,
                "message": r.message,
                "value": r.value,
            }
            for r in result.results
        ],
    }


def report_quality_passed() -> TerminalResult:
    """Terminal tool: quality checks passed, proceed to execution."""
    return TerminalResult(
        stop_reason="quality_passed",
        state_updates={},
        display_value="Quality checks passed.",
    )


def report_quality_warning(message: str, question: str) -> TerminalResult:
    """Terminal tool: quality issues found, ask user to confirm before proceeding."""
    return TerminalResult(
        stop_reason="quality_warning",
        state_updates={"escalation_question": question},
        display_value=f"Quality warning: {message}",
    )

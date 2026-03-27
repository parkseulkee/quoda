import json
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from quada.core.orchestrator import Orchestrator, OrchestratorResult
from quada.quality.rules import RuleResult
from quada.quality.engine import QualityCheckResult


@pytest.fixture
def orchestrator():
    llm_client = MagicMock()
    # Orchestrator intent parsing
    llm_client.completion.side_effect = [
        # First call: orchestrator intent
        json.dumps({
            "intent": "query",
            "terms_to_resolve": ["이탈 고객"],
            "metrics_needed": ["매출"],
            "time_filter": "지난달",
            "entities_involved": ["customer", "order"],
        }),
        # Subsequent calls handled by agents
    ]

    semantic_agent = MagicMock()
    semantic_agent.generate_sql.return_value = MagicMock(
        sql="SELECT SUM(amount) FROM orders",
        tables_used=["orders", "customers"],
        resolved_terms={"이탈 고객": "90일 미구매"},
        explanation="이탈 고객 매출 조회",
    )

    quality_agent = MagicMock()
    quality_agent.engine = MagicMock()
    quality_agent.engine.check = AsyncMock(return_value=QualityCheckResult(results=[
        RuleResult("freshness", "pass", "OK"),
    ]))
    quality_agent.analyze_impact.return_value = MagicMock(
        overall_status="pass",
        issues=[],
        recommendation="문제 없음",
    )

    interpret_agent = MagicMock()
    interpret_agent.interpret.return_value = MagicMock(
        summary="매출은 12,450,000원입니다.",
        insights=["전체의 12.7%"],
        quality_note=None,
        follow_up_questions=["추이는?"],
    )

    executor = MagicMock()
    executor.execute.return_value = [{"revenue": 12450000}]

    return Orchestrator(
        llm_client=llm_client,
        semantic_agent=semantic_agent,
        quality_agent=quality_agent,
        interpret_agent=interpret_agent,
        executor=executor,
        quality_rules=[],
    )


def test_orchestrator_run(orchestrator):
    result = asyncio.run(orchestrator.run("이탈 고객의 매출 보여줘"))
    assert isinstance(result, OrchestratorResult)
    assert result.sql is not None
    assert result.interpret_result is not None
    assert result.interpret_result.summary is not None


def test_orchestrator_skip_quality(orchestrator):
    result = asyncio.run(orchestrator.run("매출 보여줘", skip_quality=True))
    orchestrator.quality_agent.engine.check.assert_not_called()

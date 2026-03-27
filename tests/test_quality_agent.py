import json
from unittest.mock import MagicMock, AsyncMock

import pytest

from quada.agents.quality import QualityAgent
from quada.quality.engine import QualityCheckResult
from quada.quality.rules import RuleResult


@pytest.fixture
def quality_agent():
    llm_client = MagicMock()
    llm_client.completion.return_value = json.dumps({
        "overall_status": "warn",
        "issues": [
            {
                "rule": "orders_status_not_null",
                "status": "warn",
                "impact": "status 컬럼 NULL 3.2%로 매출이 과소 집계될 수 있음",
                "estimated_error": "~3%",
            }
        ],
        "recommendation": "매출이 실제보다 약 3% 낮을 수 있습니다.",
    })
    engine = MagicMock()
    return QualityAgent(llm_client=llm_client, engine=engine)


def test_analyze_impact(quality_agent):
    check_result = QualityCheckResult(results=[
        RuleResult("orders_freshness", "pass", "Data is fresh"),
        RuleResult("orders_status_not_null", "warn", "null ratio 3.2% exceeds 1%", "0.032"),
    ])
    analysis = quality_agent.analyze_impact(
        check_result=check_result,
        sql="SELECT SUM(amount) FROM orders WHERE status = 'completed'",
        user_query="이탈 고객의 매출",
    )
    assert analysis.overall_status == "warn"
    assert len(analysis.issues) > 0


def test_analyze_impact_all_pass(quality_agent):
    quality_agent.llm_client.completion.return_value = json.dumps({
        "overall_status": "pass",
        "issues": [],
        "recommendation": "데이터 품질에 문제가 없습니다.",
    })
    check_result = QualityCheckResult(results=[
        RuleResult("orders_freshness", "pass", "Data is fresh"),
    ])
    analysis = quality_agent.analyze_impact(
        check_result=check_result,
        sql="SELECT 1",
        user_query="test",
    )
    assert analysis.overall_status == "pass"

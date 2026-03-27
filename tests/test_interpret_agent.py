import json
from unittest.mock import MagicMock

import pytest

from quada.agents.interpret import InterpretAgent, InterpretResult


@pytest.fixture
def interpret_agent():
    llm_client = MagicMock()
    llm_client.completion.return_value = json.dumps({
        "summary": "지난달 이탈 고객 매출은 12,450,000원입니다.",
        "insights": ["전체 매출의 12.7%를 차지합니다."],
        "quality_note": "status NULL 3.2%로 실제 매출은 약 3% 높을 수 있습니다.",
        "follow_up_questions": ["이탈 고객의 주요 이탈 시점은?"],
    })
    return InterpretAgent(llm_client=llm_client)


def test_interpret_results(interpret_agent):
    quality_analysis = {
        "overall_status": "warn",
        "issues": [{"rule": "null_check", "status": "warn", "impact": "NULL 3.2%", "estimated_error": "~3%"}],
        "recommendation": "매출이 약 3% 과소 집계될 수 있습니다.",
    }
    result = interpret_agent.interpret(
        query_results=[{"revenue": 12450000}],
        sql="SELECT SUM(amount) as revenue FROM orders",
        user_query="이탈 고객의 매출",
        quality_analysis=quality_analysis,
    )
    assert isinstance(result, InterpretResult)
    assert "12,450,000" in result.summary
    assert len(result.insights) > 0
    assert result.quality_note is not None
    assert len(result.follow_up_questions) > 0


def test_interpret_without_quality_issues(interpret_agent):
    interpret_agent.llm_client.completion.return_value = json.dumps({
        "summary": "매출은 100,000,000원입니다.",
        "insights": ["전월 대비 증가"],
        "quality_note": None,
        "follow_up_questions": ["월별 추이는?"],
    })
    result = interpret_agent.interpret(
        query_results=[{"revenue": 100000000}],
        sql="SELECT SUM(amount) as revenue FROM orders",
        user_query="이번달 매출",
        quality_analysis=None,
    )
    assert result.quality_note is None

"""Tests for quality tools."""
from quada.tools.base import TerminalResult
from quada.tools.quality_tools import report_quality_passed, report_quality_warning


def test_report_quality_passed():
    result = report_quality_passed()
    assert isinstance(result, TerminalResult)
    assert result.stop_reason == "quality_passed"
    assert result.state_updates == {}


def test_report_quality_warning():
    result = report_quality_warning(
        message="orders.status NULL 3.2% — 매출 ~3% 과소 집계 가능",
        question="품질 경고가 있습니다. 계속 진행하시겠습니까? (y/n)",
    )
    assert isinstance(result, TerminalResult)
    assert result.stop_reason == "quality_warning"
    assert "escalation_question" in result.state_updates
    assert result.state_updates["escalation_question"] == "품질 경고가 있습니다. 계속 진행하시겠습니까? (y/n)"

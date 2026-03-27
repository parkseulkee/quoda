from types import SimpleNamespace

from quada.cli.display import format_quality_warning, format_interpret_result


def test_format_quality_warning():
    analysis = {
        "overall_status": "warn",
        "issues": [
            {"status": "warn", "rule": "null_check", "impact": "status NULL 3.2%", "estimated_error": "~3%"},
        ],
        "recommendation": "매출이 약 3% 과소 집계될 수 있습니다.",
    }
    output = format_quality_warning(analysis)
    assert "warn" in output.lower() or "⚠" in output
    assert "null_check" in output or "status" in output


def test_format_interpret_result():
    result = SimpleNamespace(
        summary="지난달 매출은 12,450,000원입니다.",
        insights=["전체 매출의 12.7%"],
        quality_note="약 3% 오차 가능",
        follow_up_questions=["월별 추이는?"],
    )
    output = format_interpret_result(result)
    assert "12,450,000" in output
    assert "12.7%" in output


def test_format_interpret_result_no_quality_note():
    result = SimpleNamespace(
        summary="매출은 100,000,000원입니다.",
        insights=["증가 추세"],
        quality_note=None,
        follow_up_questions=[],
    )
    output = format_interpret_result(result)
    assert "100,000,000" in output

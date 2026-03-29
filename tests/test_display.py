from io import StringIO

from rich.console import Console

from quada.cli.display import (
    print_agent_semantic,
    print_agent_quality,
    print_agent_execute,
    print_agent_interpret,
    print_final_output,
)


def _capture(fn, *args, **kwargs) -> str:
    """Capture Rich console output as plain text."""
    buf = StringIO()
    import quada.cli.display as display_mod
    original = display_mod.console
    display_mod.console = Console(file=buf, force_terminal=True, width=120)
    try:
        fn(*args, **kwargs)
    finally:
        display_mod.console = original
    return buf.getvalue()


def test_print_agent_semantic():
    state = {
        "resolved_terms": {"이탈 고객": {"sql_condition": "status = 'churned'"}},
        "tables_used": ["customers", "orders"],
        "sql": "SELECT * FROM customers WHERE status = 'churned'",
        "stop_reason": "sql_generated",
    }
    output = _capture(print_agent_semantic, state)
    assert "SemanticQueryAgent" in output
    assert "이탈 고객" in output
    assert "sql_generated" in output
    assert "QualityAgent" in output


def test_print_agent_quality_pass():
    state = {
        "tables_used": ["orders"],
        "quality_results": [
            {"rule_name": "orders_freshness", "status": "pass", "message": "Data is fresh"},
        ],
        "stop_reason": "quality_passed",
    }
    output = _capture(print_agent_quality, state)
    assert "QualityAgent" in output
    assert "PASS" in output
    assert "ExecuteNode" in output


def test_print_agent_quality_warning():
    state = {
        "tables_used": ["orders"],
        "quality_results": [
            {"rule_name": "null_check", "status": "warn", "message": "null ratio 8%"},
        ],
        "stop_reason": "quality_warning",
    }
    output = _capture(print_agent_quality, state)
    assert "WARN" in output
    assert "Escalate" in output


def test_print_agent_execute():
    state = {
        "query_results": [{"name": "a"}, {"name": "b"}],
        "error": None,
        "stop_reason": "executed",
    }
    output = _capture(print_agent_execute, state)
    assert "2 rows" in output
    assert "InterpretAgent" in output


def test_print_agent_execute_error():
    state = {
        "query_results": [],
        "error": "table not found",
        "stop_reason": "sql_error",
    }
    output = _capture(print_agent_execute, state)
    assert "table not found" in output
    assert "Escalate" in output


def test_print_agent_interpret():
    state = {"stop_reason": "done"}
    output = _capture(print_agent_interpret, state)
    assert "InterpretAgent" in output
    assert "END" in output


def test_print_final_output_full():
    state = {
        "sql": "SELECT name, SUM(amount) FROM orders GROUP BY name",
        "query_results": [{"name": "Kim", "total": 100000}],
        "interpretation": {
            "summary": "총 매출은 100,000원입니다.",
            "insights": ["Kim이 전체 매출을 차지"],
            "quality_note": "status NULL 8%",
            "follow_up_questions": ["월별 추이는?"],
            "chart": "CHART_PLACEHOLDER",
        },
    }
    output = _capture(print_final_output, state)
    assert "SELECT" in output
    assert "Kim" in output
    assert "100,000" in output
    assert "CHART_PLACEHOLDER" in output
    assert "월별 추이" in output


def test_print_final_output_no_interpretation():
    state = {
        "sql": "SELECT 1",
        "query_results": [{"col": 1}],
        "interpretation": None,
    }
    output = _capture(print_final_output, state)
    assert "Generated SQL" in output
    assert "col" in output

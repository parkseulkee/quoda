"""Interpret tools: result summarization and visualization."""

import json

from quada.tools.base import TerminalResult


def render_chart(rows: list[dict], chart_type: str = "bar") -> str:
    """Render a CLI chart from query results. Returns description of rendered chart."""
    if not rows:
        return "No data to visualize."

    try:
        import plotext as plt
        keys = list(rows[0].keys())
        if len(keys) >= 2:
            x_key, y_key = keys[0], keys[1]
            x_vals = [str(r[x_key]) for r in rows[:20]]
            y_vals = [float(r[y_key]) if r[y_key] is not None else 0 for r in rows[:20]]
            plt.clear_figure()
            if chart_type == "bar":
                plt.bar(x_vals, y_vals)
            else:
                plt.plot(x_vals, y_vals)
            plt.title("Query Results")
            plt.show()
            return f"Chart rendered: {chart_type} chart with {len(rows)} rows."
    except Exception:
        pass
    return f"Data ({len(rows)} rows): " + json.dumps(rows[:5], ensure_ascii=False, default=str)


def finalize_interpretation(
    summary: str,
    insights: list[str],
    follow_up_questions: list[str],
    quality_note: str | None = None,
) -> TerminalResult:
    """Terminal tool: LLM commits the final interpretation."""
    return TerminalResult(
        stop_reason="done",
        state_updates={},
        display_value=summary,
    )

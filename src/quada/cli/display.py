"""Rich-based CLI output formatting."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from quada.agents.interpret import InterpretResult
from quada.agents.quality import QualityAnalysis


console = Console()


def format_quality_warning(analysis: QualityAnalysis) -> str:
    """Format quality analysis as a readable string."""
    lines = []
    lines.append(f"⚠ Data Quality: {analysis.overall_status.upper()}")
    for issue in analysis.issues:
        lines.append(f"  - [{issue.status}] {issue.rule}: {issue.impact}")
        if issue.estimated_error:
            lines.append(f"    Estimated error: {issue.estimated_error}")
    lines.append(f"  Recommendation: {analysis.recommendation}")
    return "\n".join(lines)


def format_interpret_result(result: InterpretResult) -> str:
    """Format interpretation result as a readable string."""
    lines = []
    lines.append(f"📊 {result.summary}")
    if result.insights:
        lines.append("")
        lines.append("💡 Insights:")
        for insight in result.insights:
            lines.append(f"  - {insight}")
    if result.quality_note:
        lines.append("")
        lines.append(f"⚠ Quality note: {result.quality_note}")
    if result.follow_up_questions:
        lines.append("")
        lines.append("💬 Follow-up questions:")
        for q in result.follow_up_questions:
            lines.append(f"  - {q}")
    return "\n".join(lines)


def print_quality_warning(analysis: QualityAnalysis) -> None:
    """Print quality warning to console."""
    text = format_quality_warning(analysis)
    console.print(Panel(text, title="Data Quality", border_style="yellow"))


def print_interpret_result(result: InterpretResult) -> None:
    """Print interpretation result to console."""
    text = format_interpret_result(result)
    console.print(Panel(text, title="Result", border_style="green"))


def print_sql(sql: str) -> None:
    """Print generated SQL to console."""
    console.print(Panel(sql, title="Generated SQL", border_style="blue"))


def print_error(message: str) -> None:
    """Print error message to console."""
    console.print(f"[red]✗ {message}[/red]")

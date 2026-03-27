"""Rich-based CLI output formatting."""

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

console = Console()


def progress_callback(step: str, data: dict) -> None:
    """Real-time progress callback for the orchestrator pipeline."""

    if step == "intent_start":
        console.print("\n[bold cyan]1/5[/bold cyan] [dim]Parsing intent...[/dim]")

    elif step == "intent_done":
        console.print("     [green]done[/green]")

    elif step == "semantic_start":
        console.print("[bold cyan]2/5[/bold cyan] [dim]Resolving semantic layer & generating SQL...[/dim]")

    elif step == "semantic_done":
        # Show resolved terms
        terms = data.get("resolved_terms", {})
        if terms:
            console.print("     [bold]Resolved terms:[/bold]")
            for user_term, resolved in terms.items():
                console.print(f"       [yellow]{user_term}[/yellow] → {resolved}")

        # Show tables used
        tables = data.get("tables_used", [])
        if tables:
            console.print(f"     [bold]Tables:[/bold] {', '.join(tables)}")

        # Show explanation
        explanation = data.get("explanation", "")
        if explanation:
            console.print(f"     [bold]Explanation:[/bold] {explanation}")

        # Show SQL
        sql = data.get("sql", "")
        if sql:
            console.print()
            console.print(Panel(
                Syntax(sql, "sql", theme="monokai", word_wrap=True),
                title="Generated SQL",
                border_style="blue",
            ))

    elif step == "quality_start":
        tables = data.get("tables", [])
        console.print(f"[bold cyan]3/5[/bold cyan] [dim]Running quality checks on {', '.join(tables)}...[/dim]")

    elif step == "quality_done":
        results = data.get("results", [])
        for r in results:
            status = r["status"]
            color = "green" if status == "pass" else "yellow" if status == "warn" else "red"
            console.print(f"       [{color}]{status.upper()}[/{color}] {r['rule']}: {r['message']}")

    elif step == "quality_analysis_start":
        console.print("     [dim]Analyzing quality impact...[/dim]")

    elif step == "quality_analysis_done":
        console.print(f"     Recommendation: {data.get('recommendation', '')}")

    elif step == "execute_start":
        console.print("[bold cyan]4/5[/bold cyan] [dim]Executing SQL...[/dim]")

    elif step == "execute_done":
        row_count = data.get("row_count", 0)
        rows = data.get("rows", [])
        console.print(f"     [green]{row_count} rows returned[/green]")
        if rows:
            table = Table(show_header=True, header_style="bold", border_style="dim")
            for col in rows[0]:
                table.add_column(col)
            for row in rows[:20]:
                table.add_row(*[str(v) for v in row.values()])
            if row_count > 20:
                table.add_row(*["..." for _ in rows[0]])
            console.print(table)

    elif step == "interpret_start":
        console.print("[bold cyan]5/5[/bold cyan] [dim]Interpreting results...[/dim]")


def format_quality_warning(analysis: dict) -> str:
    """Format quality analysis as a readable string."""
    lines = []
    status = analysis.get("overall_status", "warn")
    lines.append(f"⚠ Data Quality: {status.upper()}")
    for issue in analysis.get("issues", []):
        lines.append(f"  - [{issue.get('status', '')}] {issue.get('rule', '')}: {issue.get('impact', '')}")
        if issue.get("estimated_error"):
            lines.append(f"    Estimated error: {issue['estimated_error']}")
    lines.append(f"  Recommendation: {analysis.get('recommendation', '')}")
    return "\n".join(lines)


def format_interpret_result(result) -> str:
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


def print_quality_warning(analysis: dict) -> None:
    """Print quality warning to console."""
    text = format_quality_warning(analysis)
    console.print(Panel(text, title="Data Quality", border_style="yellow"))


def print_interpret_result(result) -> None:
    """Print interpretation result to console."""
    text = format_interpret_result(result)
    console.print(Panel(text, title="Result", border_style="green"))


def print_sql(sql: str) -> None:
    """Print generated SQL to console."""
    console.print(Panel(sql, title="Generated SQL", border_style="blue"))


def print_error(message: str) -> None:
    """Print error message to console."""
    console.print(f"[red]✗ {message}[/red]")

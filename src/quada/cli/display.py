"""Rich-based CLI output formatting for agentic pipeline."""

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

console = Console()

# ── Route labels ─────────────────────────────────────────────

_NEXT_NODE: dict[str, str] = {
    "sql_generated": "QualityAgent",
    "term_not_found": "Escalate (사용자 확인)",
    "quality_passed": "ExecuteNode",
    "quality_warning": "Escalate (사용자 확인)",
    "executed": "InterpretAgent",
    "sql_error": "Escalate (사용자 확인)",
    "done": "END",
    "term_clarified": "SemanticQueryAgent (재시도)",
    "sql_retry": "SemanticQueryAgent (재시도)",
    "execute_approved": "ExecuteNode",
    "escalation_done": "END",
}


def _route_line(stop_reason: str) -> str:
    next_node = _NEXT_NODE.get(stop_reason, stop_reason)
    return f"[dim]stop_reason:[/dim] [bold]{stop_reason}[/bold] [dim]→ next:[/dim] [bold cyan]{next_node}[/bold cyan]"


# ── Agent flow panels ───────────────────────────────────────

def print_agent_semantic(state: dict) -> None:
    """Print SemanticQueryAgent results as an agent flow panel."""
    lines: list[str] = []

    resolved = state.get("resolved_terms", {})
    if resolved:
        lines.append("[bold]참조한 시맨틱 레이어:[/bold]")
        for user_term, definition in resolved.items():
            if isinstance(definition, dict):
                detail = definition.get("sql_condition") or definition.get("expression") or str(definition)
            else:
                detail = str(definition)
            lines.append(f"  [yellow]{user_term}[/yellow] → {detail}")

    tables = state.get("tables_used", [])
    if tables:
        lines.append(f"[bold]테이블:[/bold] {', '.join(tables)}")

    sql = state.get("sql")
    if sql:
        lines.append(f"[bold]생성 SQL:[/bold] [dim]{sql[:120]}{'...' if len(sql) > 120 else ''}[/dim]")

    stop = state.get("stop_reason", "")
    lines.append(_route_line(stop))

    console.print(Panel(
        "\n".join(lines),
        title="[bold green]SemanticQueryAgent[/bold green]",
        border_style="green",
        padding=(0, 1),
    ))


def print_agent_quality(state: dict) -> None:
    """Print QualityAgent results as an agent flow panel."""
    lines: list[str] = []

    tables = state.get("tables_used", [])
    if tables:
        lines.append(f"[bold]대상 테이블:[/bold] {', '.join(tables)}")

    results = state.get("quality_results", [])
    if results:
        for r in results:
            status = r.get("status", "")
            color = "green" if status == "pass" else "yellow" if status == "warn" else "red"
            lines.append(f"  [{color}]{status.upper():4s}[/{color}] {r.get('rule_name', '')}: {r.get('message', '')}")

    stop = state.get("stop_reason", "")
    lines.append(_route_line(stop))

    console.print(Panel(
        "\n".join(lines),
        title="[bold yellow]QualityAgent[/bold yellow]",
        border_style="yellow",
        padding=(0, 1),
    ))


def print_agent_execute(state: dict) -> None:
    """Print ExecuteNode results as an agent flow panel."""
    lines: list[str] = []

    rows = state.get("query_results", [])
    error = state.get("error")
    if error:
        lines.append(f"[red]오류: {error}[/red]")
    else:
        lines.append(f"[bold]{len(rows)} rows[/bold] returned")

    stop = state.get("stop_reason", "")
    lines.append(_route_line(stop))

    console.print(Panel(
        "\n".join(lines),
        title="[bold blue]ExecuteNode[/bold blue]",
        border_style="blue",
        padding=(0, 1),
    ))


def print_agent_interpret(state: dict) -> None:
    """Print InterpretAgent results as an agent flow panel."""
    lines: list[str] = []
    lines.append("[dim]결과 해석 완료[/dim]")

    stop = state.get("stop_reason", "")
    lines.append(_route_line(stop))

    console.print(Panel(
        "\n".join(lines),
        title="[bold magenta]InterpretAgent[/bold magenta]",
        border_style="magenta",
        padding=(0, 1),
    ))


def print_agent_escalate(state: dict) -> None:
    """Print Escalate node info as an agent flow panel."""
    lines: list[str] = []
    question = state.get("escalation_question", "")
    if question:
        lines.append(f"[yellow]{question}[/yellow]")

    stop = state.get("stop_reason", "")
    lines.append(_route_line(stop))

    console.print(Panel(
        "\n".join(lines),
        title="[bold red]Escalate[/bold red]",
        border_style="red",
        padding=(0, 1),
    ))


# ── Final output ─────────────────────────────────────────────

def print_final_output(state: dict) -> None:
    """Print final output: SQL → Data → Chart → Interpretation."""
    console.print()
    console.rule("[bold]Results[/bold]")
    console.print()

    # 1. SQL
    sql = state.get("sql")
    if sql:
        console.print(Panel(
            Syntax(sql, "sql", theme="monokai", word_wrap=True),
            title="Generated SQL",
            border_style="blue",
        ))

    # 2. Data table
    rows = state.get("query_results", [])
    if rows:
        table = Table(show_header=True, header_style="bold", border_style="dim")
        for col in rows[0].keys():
            table.add_column(str(col))
        for row in rows[:50]:
            table.add_row(*[str(v) if v is not None else "" for v in row.values()])
        if len(rows) > 50:
            table.add_row(*["..." for _ in rows[0]])
        console.print(table)
        console.print()

    # 3. Chart
    interpretation = state.get("interpretation") or {}
    chart = interpretation.get("chart")
    if chart:
        console.print(Panel(chart, title="Chart", border_style="cyan", padding=(0, 1)))
        console.print()

    # 4. Interpretation & Insights
    summary = interpretation.get("summary")
    if summary:
        lines: list[str] = []
        lines.append(f"[bold]{summary}[/bold]")

        insights = interpretation.get("insights", [])
        if insights:
            lines.append("")
            for insight in insights:
                lines.append(f"  - {insight}")

        quality_note = interpretation.get("quality_note")
        if quality_note:
            lines.append("")
            lines.append(f"[yellow]품질 참고: {quality_note}[/yellow]")

        follow_ups = interpretation.get("follow_up_questions", [])
        if follow_ups:
            lines.append("")
            lines.append("[dim]추가 질문:[/dim]")
            for q in follow_ups:
                lines.append(f"  [dim]- {q}[/dim]")

        console.print(Panel(
            "\n".join(lines),
            title="해석 & 인사이트",
            border_style="green",
            padding=(0, 1),
        ))


# ── Legacy helpers (kept for check command) ──────────────────

def print_sql(sql: str) -> None:
    """Print generated SQL to console."""
    console.print(Panel(sql, title="Generated SQL", border_style="blue"))


def print_error(message: str) -> None:
    """Print error message to console."""
    console.print(f"[red]✗ {message}[/red]")


def print_query_results(rows: list[dict]) -> None:
    """Print query results as a Rich table."""
    if not rows:
        console.print("[yellow]No results.[/yellow]")
        return
    table = Table(show_header=True, header_style="bold")
    for col in rows[0].keys():
        table.add_column(str(col))
    for row in rows[:100]:
        table.add_row(*[str(v) if v is not None else "" for v in row.values()])
    console.print(table)

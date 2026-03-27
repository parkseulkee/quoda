"""Typer CLI application: quada commands."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console

import quada
from quada.cli.display import (
    print_quality_warning,
    print_interpret_result,
    print_sql,
    print_error,
)
from quada.core.config import load_config
from quada.db.connector import create_engine_from_config
from quada.db.executor import SQLExecutor
from quada.llm.client import LLMClient
from quada.semantic.loader import SemanticLoader
from quada.semantic.matcher import SemanticMatcher
from quada.agents.semantic_query import SemanticQueryAgent
from quada.agents.quality import QualityAgent
from quada.agents.interpret import InterpretAgent
from quada.quality.engine import QualityEngine
from quada.core.orchestrator import Orchestrator

app = typer.Typer(name="quada", help="Semantic layer + data quality + natural language query agent")
console = Console()

TEMPLATE_QUADA_YAML = """database:
  type: postgresql
  host: localhost
  port: 5432
  name: mydb
  user: ${DB_USER}
  password: ${DB_PASSWORD}

semantic_layer:
  source: local

# API 키는 환경변수로 설정:
#   anthropic → export ANTHROPIC_API_KEY=sk-ant-...
#   openai    → export OPENAI_API_KEY=sk-...
llm:
  orchestrator:
    provider: anthropic
    model: claude-opus-4-6
  agents:
    semantic_query:
      provider: anthropic
      model: claude-haiku-4-5-20251001
    quality:
      provider: openai
      model: gpt-4o-mini
    interpret:
      provider: anthropic
      model: claude-sonnet-4-6
"""


def version_callback(value: bool):
    if value:
        console.print(f"quada {quada.__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-v", callback=version_callback, is_eager=True),
):
    """Quada: data agent with semantic layer and quality checks."""
    pass


@app.command()
def init(
    path: Path = typer.Option(".", help="Project directory"),
):
    """Initialize a new quada project."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    config_file = path / "quada.yaml"
    if not config_file.exists():
        config_file.write_text(TEMPLATE_QUADA_YAML)

    for dir_name in ["models", "metrics", "glossary", "quality"]:
        (path / dir_name).mkdir(exist_ok=True)

    console.print(f"[green]✓ Initialized quada project at {path}[/green]")


@app.command()
def validate(
    path: Path = typer.Option(".", help="Project directory"),
):
    """Validate quada project configuration and semantic layer."""
    config_path = Path(path) / "quada.yaml"
    if not config_path.exists():
        print_error(f"Config not found: {config_path}")
        raise typer.Exit(1)

    try:
        config = load_config(config_path)
        console.print("[green]✓ quada.yaml is valid[/green]")
    except Exception as e:
        print_error(f"Invalid config: {e}")
        raise typer.Exit(1)

    loader = SemanticLoader(
        models_dir=Path(path) / "models",
        metrics_dir=Path(path) / "metrics",
        glossary_dir=Path(path) / "glossary",
        quality_dir=Path(path) / "quality",
    )
    ctx = loader.load_all()
    console.print(f"  Entities: {len(ctx.entities)}")
    console.print(f"  Metrics: {len(ctx.metrics)}")
    console.print(f"  Glossary terms: {len(ctx.glossary)}")
    console.print(f"  Quality rules: {len(ctx.quality.rules)}")
    console.print("[green]✓ Semantic layer is valid[/green]")


@app.command()
def ask(
    query: str = typer.Argument(help="Natural language query"),
    path: Path = typer.Option(".", help="Project directory"),
    skip_quality: bool = typer.Option(False, "--skip-quality", help="Skip quality checks"),
    show_sql: bool = typer.Option(False, "--show-sql", help="Show generated SQL"),
):
    """Ask a natural language question about your data."""
    config_path = Path(path) / "quada.yaml"
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        print_error(f"Config not found: {config_path}. Run 'quada init' first.")
        raise typer.Exit(1)

    # Build components
    engine = create_engine_from_config(config.database)
    executor = SQLExecutor(engine)
    llm_client = LLMClient(config.llm)

    loader = SemanticLoader(
        models_dir=Path(path) / "models",
        metrics_dir=Path(path) / "metrics",
        glossary_dir=Path(path) / "glossary",
        quality_dir=Path(path) / "quality",
    )
    ctx = loader.load_all()

    matcher = SemanticMatcher(glossary=ctx.glossary, metrics=ctx.metrics, llm_client=llm_client)
    semantic_agent = SemanticQueryAgent(llm_client=llm_client, semantic_context=ctx, matcher=matcher)
    quality_engine = QualityEngine(executor)
    quality_agent = QualityAgent(llm_client=llm_client, engine=quality_engine)
    interpret_agent = InterpretAgent(llm_client=llm_client)

    orchestrator = Orchestrator(
        llm_client=llm_client,
        semantic_agent=semantic_agent,
        quality_agent=quality_agent,
        interpret_agent=interpret_agent,
        executor=executor,
        quality_rules=ctx.quality.rules,
    )

    # Run pipeline
    result = asyncio.run(orchestrator.run(query, skip_quality=skip_quality))

    if show_sql:
        print_sql(result.sql)

    if result.quality_analysis and result.quality_analysis.overall_status != "pass":
        print_quality_warning(result.quality_analysis)
        proceed = typer.confirm("Proceed with execution?", default=True)
        if not proceed:
            raise typer.Exit(0)

    print_interpret_result(result.interpret_result)


@app.command()
def check(
    table: str = typer.Argument(None, help="Table to check (optional, checks all if omitted)"),
    path: Path = typer.Option(".", help="Project directory"),
):
    """Run data quality checks."""
    config_path = Path(path) / "quada.yaml"
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        print_error(f"Config not found: {config_path}. Run 'quada init' first.")
        raise typer.Exit(1)

    engine = create_engine_from_config(config.database)
    executor = SQLExecutor(engine)

    loader = SemanticLoader(quality_dir=Path(path) / "quality")
    quality_config = loader.load_quality_rules()

    rules = quality_config.rules
    if table:
        rules = [r for r in rules if r.table == table]

    if not rules:
        console.print("[yellow]No quality rules found.[/yellow]")
        raise typer.Exit(0)

    tables = list({r.table for r in rules})
    quality_engine = QualityEngine(executor)
    result = asyncio.run(quality_engine.check(rules=rules, tables=tables))

    for r in result.results:
        status_color = "green" if r.status == "pass" else "yellow" if r.status == "warn" else "red"
        console.print(f"  [{status_color}]{r.status.upper()}[/{status_color}] {r.rule_name}: {r.message}")

    console.print(f"\nOverall: [{'green' if result.overall_status == 'pass' else 'yellow'}]{result.overall_status.upper()}[/]")


@app.command(name="config")
def config_show(
    path: Path = typer.Option(".", help="Project directory"),
):
    """Show current configuration."""
    config_path = Path(path) / "quada.yaml"
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        print_error(f"Config not found: {config_path}")
        raise typer.Exit(1)

    console.print(f"Database: {config.database.type}://{config.database.host}:{config.database.port}/{config.database.name}")
    console.print(f"Semantic layer: {config.semantic_layer.source}")
    console.print(f"Orchestrator LLM: {config.llm.orchestrator.provider}/{config.llm.orchestrator.model}")
    console.print(f"Semantic Query LLM: {config.llm.agents.semantic_query.provider}/{config.llm.agents.semantic_query.model}")
    console.print(f"Quality LLM: {config.llm.agents.quality.provider}/{config.llm.agents.quality.model}")
    console.print(f"Interpret LLM: {config.llm.agents.interpret.provider}/{config.llm.agents.interpret.model}")

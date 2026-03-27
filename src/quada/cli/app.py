"""Typer CLI application: quada commands."""

import asyncio
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

import quada
from quada.cli.display import (
    print_quality_warning,
    print_interpret_result,
    print_sql,
    print_error,
    print_query_results,
)
from quada.core.config import load_config
from quada.db.connector import create_engine_from_config
from quada.db.executor import SQLExecutor
from quada.llm.client import LLMClient
from quada.semantic.index import MetadataIndex
from quada.semantic.loader import SemanticLoader
from quada.core.orchestrator import build_graph
from quada.core.state import QuadaState
from quada.quality.engine import QualityEngine

app = typer.Typer(name="quada", help="Semantic layer + data quality + natural language query agent")
console = Console()
load_dotenv()

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


@app.command(name="index")
def index_build(
    path: Path = typer.Option(".", help="Project directory"),
):
    """Build metadata index from semantic layer YAML files."""
    load_dotenv(Path(path) / ".env")
    config_path = Path(path) / "quada.yaml"
    if not config_path.exists():
        print_error(f"Config not found: {config_path}. Run 'quada init' first.")
        raise typer.Exit(1)

    loader = SemanticLoader(
        models_dir=Path(path) / "models",
        metrics_dir=Path(path) / "metrics",
        glossary_dir=Path(path) / "glossary",
        quality_dir=Path(path) / "quality",
    )
    ctx = loader.load_all()
    index = MetadataIndex.build(ctx)
    quada_dir = Path(path) / ".quada"
    index.save(quada_dir)

    console.print(f"[green]✓ metadata_index.json saved to {quada_dir}[/green]")
    console.print(f"  Entities: {len(index.data['entities'])}")
    console.print(f"  Metrics:  {len(index.data['metrics'])}")
    console.print(f"  Glossary: {len(index.data['glossary'])}")


@app.command()
def ask(
    query: str = typer.Argument(help="Natural language query"),
    path: Path = typer.Option(".", help="Project directory"),
    skip_quality: bool = typer.Option(False, "--skip-quality", help="Skip quality checks"),
):
    """Ask a natural language question about your data."""
    load_dotenv(Path(path) / ".env")
    config_path = Path(path) / "quada.yaml"
    project_dir = Path(path).resolve()

    try:
        config = load_config(config_path)
    except FileNotFoundError:
        print_error(f"Config not found: {config_path}. Run 'quada init' first.")
        raise typer.Exit(1)

    index_path = project_dir / ".quada" / "metadata_index.json"
    if not index_path.exists():
        print_error("metadata_index.json not found. Run 'quada index build' first.")
        raise typer.Exit(1)

    engine = create_engine_from_config(config.database)
    executor = SQLExecutor(engine)
    llm_client = LLMClient(config.llm)

    loader = SemanticLoader(
        models_dir=project_dir / "models",
        metrics_dir=project_dir / "metrics",
        glossary_dir=project_dir / "glossary",
        quality_dir=project_dir / "quality",
    )
    ctx = loader.load_all()

    graph = build_graph(
        llm_client=llm_client,
        semantic_context=ctx,
        executor=executor,
        project_dir=project_dir,
    )

    initial_state: QuadaState = {
        "user_query": query,
        "sql": None,
        "tables_used": [],
        "resolved_terms": {},
        "quality_results": [],
        "query_results": [],
        "error": None,
        "escalation_question": None,
        "user_clarification": None,
        "stop_reason": None,
    }

    thread_config = {"configurable": {"thread_id": "quada-session"}}

    # Run graph with interrupt/resume loop
    graph.invoke(initial_state, config=thread_config)

    while True:
        state_snapshot = graph.get_state(thread_config)
        if not state_snapshot.next:
            break
        current_values = state_snapshot.values
        question = current_values.get("escalation_question", "입력이 필요합니다.")
        console.print(f"\n[yellow]{question}[/yellow]")
        user_input = typer.prompt("")
        from langgraph.types import Command
        graph.invoke(Command(resume=user_input), config=thread_config)

    # Get final state and display results
    final_state = graph.get_state(thread_config).values
    if final_state.get("sql"):
        print_sql(final_state["sql"])
    if final_state.get("query_results"):
        print_query_results(final_state["query_results"])


@app.command()
def check(
    table: str = typer.Argument(None, help="Table to check (optional, checks all if omitted)"),
    path: Path = typer.Option(".", help="Project directory"),
):
    """Run data quality checks."""
    load_dotenv(Path(path) / ".env")
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

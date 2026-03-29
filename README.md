# quada

> Natural language data queries, with quality you can trust.

---

## Table of Contents

- [Why quada?](#why-quada)
- [How It Works](#how-it-works)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
- [Configuration](#configuration)
- [Semantic Layer](#semantic-layer)
- [Quality Rules](#quality-rules)
- [Architecture](#architecture)
- [Tutorial](#tutorial)

---

## Why quada?

Most data tools make you choose between **speed** and **trust**.

You can get a fast answer from a chatbot that hallucinates SQL — or you can wait for a data analyst who understands your business context and checks the data before answering.

quada is built on the belief that both are possible at the same time.

The root problem is that business knowledge lives in people's heads, not in the database. Words like "churned customer" or "active revenue" mean something specific to your team, but that meaning is never captured anywhere queryable. When a non-technical user asks a question, the system has no way to know what they actually mean — so it guesses, and guesses wrong.

quada solves this with a **semantic layer**: a small set of YAML files where you define your entities, metrics, and business terms once. From that point, every natural language query is resolved against real definitions, not LLM intuition.

And before answering, quada always checks the data itself. If the underlying table is stale, has unexpected NULLs, or violates a range constraint, you'll know before you trust the result.

---

## How It Works

When you ask a question, quada runs it through a multi-agent pipeline:

```
"Show me revenue from churned customers"
         ↓
[semantic_query]  Resolves "churned customer" from glossary, generates SQL
         ↓
[quality]         Checks freshness, null ratios, and value ranges on target tables
         ↓
[execute]         Runs the SQL (read-only)
         ↓
[interpret]       Summarizes results in natural language + renders a chart
```

If anything is uncertain — a missing term, a quality warning, an ambiguous query — the pipeline pauses and asks you directly. No silent failures.

Each step is an independent agent running its own LLM + tool-call loop (ReAct), so it can retry, self-correct, and call multiple tools before moving on.

---

## Key Features

**Semantic layer as first-class citizen**
Define your entities, metrics, and business terms in YAML. quada resolves all queries against these definitions, not raw table names.

**Quality-first**
Before answering, quada validates the data: freshness, null ratios, value ranges, uniqueness, and custom SQL rules. Quality warnings are surfaced to you, not hidden.

**Human-in-the-loop**
If a term is missing or data quality is concerning, the pipeline pauses and prompts you — then resumes from where it stopped.

**Multi-model LLM routing**
Assign different LLM providers and models to different agents. Use a fast, cheap model for quality checks and a powerful model for interpretation.

**Read-only by design**
quada never writes to your database. All SQL execution is read-only.

**CLI-native**
Runs entirely in the terminal. Charts are rendered inline with ASCII.

---

## Quick Start

```bash
# Install
uv sync

# Initialize a project
uv run quada init --path ./my-project

# Build the metadata index
uv run quada index --path ./my-project

# Ask a question
export ANTHROPIC_API_KEY=sk-ant-...
uv run quada ask "Show me revenue from churned customers" --path ./my-project
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `quada init` | Scaffold a new quada project with a `quada.yaml` template |
| `quada validate` | Validate `quada.yaml` and the semantic layer definitions |
| `quada index` | Build the metadata index from the semantic layer |
| `quada check` | Run all quality rules and report results |
| `quada ask "<question>"` | Query data in natural language |
| `quada config` | Print the resolved configuration |
| `quada --version` | Print the version |

All commands accept `--path` to specify the project directory (defaults to current directory).

```bash
uv run quada ask "Total revenue this month" --path ./my-project
uv run quada check --path ./my-project
uv run quada config --path ./my-project
```

---

## Configuration

`quada init` generates a `quada.yaml` in your project directory. Configure your database connection, LLM providers, and semantic layer paths here.

Environment variables are supported via `${VAR_NAME}` syntax.

```yaml
database:
  type: postgresql       # postgresql or sqlite
  host: localhost
  port: 5432
  name: mydb
  user: ${DB_USER}
  password: ${DB_PASSWORD}

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
```

Different agents can use different models. Tune for cost, latency, or capability per step.

---

## Semantic Layer

The semantic layer is a set of YAML files that encode your business knowledge. quada reads these at index time and uses them to resolve every natural language query.

```
my-project/
  models/      entity definitions (tables, columns, relationships)
  metrics/     computed metrics (e.g. revenue, churn rate)
  glossary/    business term definitions (e.g. "churned customer")
  quality/     data quality rules
```

Before querying, build the index:

```bash
uv run quada index --path ./my-project
```

This generates `.quada/metadata_index.json` — a lightweight summary the LLM uses to decide which definitions to fetch in full. This keeps token usage low even with large semantic layers.

See `tests/fixtures/` or `tutorial/` for examples.

---

## Quality Rules

Define quality rules in `quality/rules.yaml`. Rules on the same table are batched into a single SQL query for efficiency.

| Type | Description | Key Parameters |
|------|-------------|----------------|
| `freshness` | Data has been updated recently | `column`, `threshold` (e.g. `"24 hours"`) |
| `null_ratio` | NULL rate in a column is within bounds | `column`, `threshold` (0.0–1.0) |
| `value_range` | Numeric column values are within range | `column`, `min`, `max` |
| `unique` | No duplicate values in a column | `column` |
| `custom_sql` | Arbitrary SQL returns a `violations` count | `query`, `threshold` |

Results are reported as **pass** or **warn**. If warnings are present, `quada ask` will prompt you before proceeding.

```yaml
- name: orders_freshness
  type: freshness
  table: orders
  column: updated_at
  threshold: "24 hours"

- name: orders_status_not_null
  type: null_ratio
  table: orders
  column: status
  threshold: 0.05

- name: orders_amount_range
  type: value_range
  table: orders
  column: amount
  min: 0
  max: 1000000

- name: customers_email_unique
  type: unique
  table: customers
  column: email

- name: no_future_orders
  type: custom_sql
  table: orders
  query: >
    SELECT COUNT(*) as violations
    FROM orders
    WHERE order_date > DATE('now')
  threshold: 0
```

---

## Architecture

quada is built on [LangGraph](https://github.com/langchain-ai/langgraph). The pipeline is a `StateGraph` with conditional routing based on each node's output.

```
CLI
 ↓
StateGraph (stop_reason-based conditional routing)
 ├─ semantic_query_node  — resolves terms, fetches definitions, generates SQL
 ├─ quality_node         — validates data quality for target tables
 ├─ execute_node         — executes SQL (read-only)
 ├─ interpret_node       — summarizes results, renders charts
 └─ escalate_node        — interrupt() for human-in-the-loop input
```

```
src/quada/
  core/       QuadaState, StateGraph orchestrator
  agents/     base agent (tool call loop), semantic_query, quality, interpret
  nodes/      graph node functions
  tools/      tool definitions (semantic, quality, interpret)
  semantic/   YAML models, loader, MetadataIndex builder
  db/         connector, read-only executor
  llm/        LiteLLM client, system prompts
  quality/    rule engine (batches rules into SQL)
  cli/        Typer app, Rich display
  viz/        Plotext chart rendering
```

**Stack:** LangGraph · LiteLLM · SQLAlchemy · Pydantic · Typer · Rich

---

## Tutorial

The `tutorial/` directory contains a SQLite-based sample project with 10 customers and 25 orders.

### 1. Setup

```bash
uv sync
uv run python tutorial/setup_db.py
```

### 2. Validate

```bash
uv run quada validate --path tutorial/
```

```
✓ quada.yaml is valid
  Entities: 2, Metrics: 1, Glossary terms: 3, Quality rules: 3
✓ Semantic layer is valid
```

### 3. Build index

```bash
uv run quada index --path tutorial/
```

```
✓ metadata_index.json saved to tutorial/.quada
  Entities: 2, Metrics: 1, Glossary: 3
```

### 4. Run quality checks

```bash
uv run quada check --path tutorial/
```

```
  PASS orders_freshness: Data is fresh
  WARN orders_status_not_null: status null ratio 8.0% exceeds threshold 5.0%
  PASS orders_amount_range: amount values within range

Overall: WARN
```

### 5. Ask questions

```bash
export ANTHROPIC_API_KEY=sk-ant-...

uv run quada ask "Show me revenue from churned customers" --path tutorial/
uv run quada ask "Number of new customers" --path tutorial/
uv run quada ask "Total revenue this month" --path tutorial/
```

### Sample Data

| Table | Rows | Notes |
|-------|------|-------|
| customers | 10 | 2 churned, 4 new, 4 active |
| orders | 25 | 20 completed, 1 cancelled, 1 pending, 1 refunded, 2 NULL status |

### Semantic Layer

- **models/**: `customers`, `orders` entity definitions
- **metrics/**: `revenue` (sum of completed order amounts)
- **glossary/**: `churned customer`, `new customer`, `active customer`
- **quality/**: freshness, null ratio, value range, unique, custom SQL rules

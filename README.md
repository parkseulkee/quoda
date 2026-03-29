# quada

Semantic layer + data quality + natural language query CLI agent.

## Setup

```bash
uv sync
```

## Test

```bash
uv run pytest tests/ -v
```

## CLI

```bash
# Check version
uv run quada --version

# Initialize project
uv run quada init --path ./my-project

# Validate configuration
uv run quada validate --path ./my-project

# Build metadata index (required before running ask)
uv run quada index --path ./my-project

# Query data in natural language (requires DB connection + LLM API key)
uv run quada ask "Show me revenue from churned customers" --path ./my-project

# Run quality checks (requires DB connection)
uv run quada check --path ./my-project

# Show configuration
uv run quada config --path ./my-project
```

## Project Structure

```
src/quada/
  core/       state, orchestrator (LangGraph StateGraph)
  agents/     base (tool call loop), semantic_query, quality, interpret
  nodes/      semantic_query, quality, execute, interpret, escalate
  tools/      base (TerminalResult), semantic_tools, quality_tools, interpret_tools
  semantic/   models, loader, index (MetadataIndex)
  db/         connector, executor
  llm/        client, prompts
  quality/    rules, engine
  cli/        app, display
  viz/        charts
```

## Architecture

quada runs as a LangGraph-based agentic pipeline.

```
CLI
 ↓
StateGraph (conditional routing based on stop_reason)
 ├─ semantic_query_node  — looks up MetadataIndex, fetches only needed definitions, generates SQL
 ├─ quality_node         — validates data quality + impact analysis for target tables
 ├─ execute_node         — executes SQL (read-only)
 ├─ interpret_node       — interprets results in natural language + visualization
 └─ escalate_node        — waits for user input via interrupt() (human-in-the-loop)
```

Each node operates as an LLM + tool call loop (ReAct). On failure, it escalates to the user via `escalate_node`.

### MetadataIndex

`quada index` generates `.quada/metadata_index.json`, which stores a lightweight summary of the semantic layer. When `quada ask` runs, the LLM reads this index to decide which entity/metric/glossary definitions to fetch in detail.

## Configuration

`quada init` generates `quada.yaml` where you configure the DB, LLM, and semantic layer.
Environment variables can be referenced using `${VAR_NAME}` syntax.

```yaml
database:
  type: postgresql
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

## Semantic Layer

Define your semantic layer as YAML files in `models/`, `metrics/`, `glossary/`, and `quality/` directories.
See `tests/fixtures/` or `tutorial/` for examples.

## Tutorial

The `tutorial/` directory contains a SQLite-based sample project.
A small dataset with 10 customers and 25 orders lets you try out all features end-to-end.

### 1. Setup

```bash
uv sync
uv run python tutorial/setup_db.py
```

### 2. Validate configuration

```bash
uv run quada validate --path tutorial/
```

Expected output:
```
✓ quada.yaml is valid
  Entities: 2
  Metrics: 1
  Glossary terms: 3
  Quality rules: 3
✓ Semantic layer is valid
```

### 3. Build metadata index

```bash
uv run quada index --path tutorial/
```

Expected output:
```
✓ metadata_index.json saved to tutorial/.quada
  Entities: 2
  Metrics:  1
  Glossary: 3
```

### 4. Run quality checks

```bash
uv run quada check --path tutorial/
```

Expected output:
```
  PASS orders_freshness: Data is fresh
  WARN orders_status_not_null: status null ratio 8.0% exceeds threshold 5.0%
  PASS orders_amount_range: amount values within range

Overall: WARN
```

The `orders` table has 2 rows with a NULL `status`, triggering a warning.

### 5. Natural language queries (requires LLM API key)

```bash
export ANTHROPIC_API_KEY=sk-ant-...

uv run quada ask "Show me revenue from churned customers" --path tutorial/
uv run quada ask "Number of new customers" --path tutorial/
uv run quada ask "Total revenue this month" --path tutorial/
```

If there are quality warnings, quada will ask whether to proceed.
If a term is not found, you can enter its definition interactively.

### Sample Data

| Table | Rows | Notes |
|-------|------|-------|
| customers | 10 | 2 churned, 4 new, 4 active |
| orders | 25 | 20 completed, 1 cancelled, 1 pending, 1 refunded, 2 NULL status |

### Semantic Layer Structure

- **models/**: `customers` and `orders` entity definitions
- **metrics/**: `revenue` (sum of completed order amounts)
- **glossary/**: `churned customer`, `new customer`, `active customer` business terms
- **quality/**: freshness, null ratio, value range, unique, and custom SQL rules

## Quality Check Rules

Defined in `quality/rules.yaml`. Rules targeting the same table are batched into a single SQL query.

| Type | Description | Key Parameters |
|------|-------------|----------------|
| `freshness` | Checks whether data has been updated recently | `column`, `threshold` (e.g. `"24 hours"`) |
| `null_ratio` | Checks whether the NULL ratio in a column is within bounds | `column`, `threshold` (0.0–1.0, e.g. `0.05` = 5%) |
| `value_range` | Checks whether numeric column values are within a specified range | `column`, `min`, `max` |
| `unique` | Checks for duplicate values in a column | `column` |
| `custom_sql` | Checks violation count via an arbitrary SQL query | `query` (must return a `violations` column), `threshold` |

### Rule Definition Examples

```yaml
# freshness — check recency
- name: orders_freshness
  type: freshness
  table: orders
  column: updated_at
  threshold: "24 hours"

# null_ratio — check NULL rate
- name: orders_status_not_null
  type: null_ratio
  table: orders
  column: status
  threshold: 0.05

# value_range — check numeric bounds
- name: orders_amount_range
  type: value_range
  table: orders
  column: amount
  min: 0
  max: 1000000

# unique — check for duplicates
- name: customers_email_unique
  type: unique
  table: customers
  column: email

# custom_sql — custom query
- name: no_future_orders
  type: custom_sql
  table: orders
  query: >
    SELECT COUNT(*) as violations
    FROM orders
    WHERE order_date > DATE('now')
  threshold: 0
```

Results are reported as **pass** or **warn**.

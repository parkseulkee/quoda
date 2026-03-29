# 📊 quada
**[KR](README.ko.md)**

> **Natural language data queries, with quality you can trust.**

quada bridges the gap between "fast answers" and "trustworthy data." Beyond simple SQL generation, it understands your business context (Semantic Layer) and self-validates data quality before returning any result.

---

## ✨ Key Features

- **Semantic Layer:** Define business terms (e.g., "churned customers") in YAML so queries are grounded in real definitions, not LLM guesses.
- **Quality-First:** Automatically checks data freshness, NULL ratios, and value ranges before answering.
- **Human-in-the-loop:** Asks the user when questions are ambiguous or quality issues are detected — never makes unilateral judgments.
- **Multi-model Routing:** Assigns the best-fit LLM (Claude, GPT, etc.) per agent to balance cost and performance.
- **CLI-Native:** Runs directly in the terminal with ASCII chart visualizations.


## 🛠 How It Works

quada operates through a **Multi-agent Pipeline** where each stage performs self-correction independently.

1. **Semantic Query:** Looks up definitions from the business glossary and generates SQL.
2. **Quality Check:** Validates data quality on the target table (warns on issues found).
3. **Execute:** Runs the SQL (read-only guaranteed).
4. **Interpret:** Summarizes results in natural language and renders charts.


## 🚀 Quick Start

```bash
# 1. Install and initialize a project
uv sync
uv run quada init --path ./my-project

# 2. Build the metadata index
uv run quada index --path ./my-project

# 3. Ask in natural language
export ANTHROPIC_API_KEY=sk-ant-...
uv run quada ask "Show me last month's revenue from churned customers" --path ./my-project
```


## ⚙️ Configuration (`quada.yaml`)

Each agent can be assigned its own model freely.

```yaml
llm:
  orchestrator: { provider: anthropic, model: claude-3-5-sonnet }
  agents:
    semantic_query: { provider: anthropic, model: claude-3-haiku }  # fast and cheap
    quality: { provider: openai, model: gpt-4o-mini }               # efficient validation
    interpret: { provider: anthropic, model: claude-3-5-sonnet }    # precise summarization
```


## ✅ Quality Rules

Define data trust specs in `quality/rules.yaml` to run automatic checks before every query.

| Type | Description | Key Parameters |
| :--- | :--- | :--- |
| `freshness` | Checks data recency | `column`, `threshold` (e.g. "24 hours") |
| `null_ratio` | Checks NULL tolerance | `column`, `threshold` (0.0–1.0) |
| `value_range` | Validates numeric ranges | `column`, `min`, `max` |
| `unique` | Detects duplicate data | `column` |
| `custom_sql` | Custom SQL assertion | `query`, `threshold` |


## 💻 CLI Reference

| Command | Description |
| :--- | :--- |
| `quada init` | Create a new project template |
| `quada index` | Index metadata based on the semantic layer |
| `quada check` | Run all quality rules and report |
| `quada ask "<q>"` | Query data in natural language |
| `quada validate` | Validate config files and semantic definitions |


## 🏗 Architecture

Designed as a **LangGraph**-based state machine for flexible workflow orchestration.

- **Framework:** LangGraph, LiteLLM, SQLAlchemy, Pydantic
- **Interface:** Typer (CLI), Rich (Display), Plotext (Charts)


## 📖 Tutorial

Try the full feature set with a sample SQLite project (10 customers, 25 orders).

→ **[Go to Tutorial](tutorial/TUTORIAL.md)**

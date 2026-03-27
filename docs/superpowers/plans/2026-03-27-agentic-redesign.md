# Agentic Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** LangGraph StateGraph 기반으로 Orchestrator를 완전 교체하고, 각 Sub Agent가 fine-grained tool call loop로 동작하며, interrupt()로 human-in-the-loop을 처리한다.

**Architecture:** Orchestrator는 `conditional_edge` 코드로 stop_reason 기반 라우팅을 수행한다. 각 노드(Sub Agent)는 자체 LLM + tool call loop를 가지며 로컬 messages만 사용해 State isolation을 보장한다. escalate_node는 `interrupt()`로 그래프를 pause하고 Checkpointer로 State를 보존한다.

**Tech Stack:** LangGraph>=0.2, LiteLLM (기존), Python 3.11+

---

## File Map

**신규:**
- `src/quada/core/state.py` — QuadaState TypedDict
- `src/quada/tools/__init__.py` — 빈 파일
- `src/quada/tools/base.py` — TerminalResult dataclass
- `src/quada/tools/semantic_tools.py` — get_entity_definition, get_metric_definition, get_glossary_term, generate_sql, report_term_not_found (순수 함수)
- `src/quada/tools/quality_tools.py` — get_quality_rules, run_*_check, analyze_impact, report_quality_warning, report_quality_passed (순수 함수)
- `src/quada/tools/interpret_tools.py` — summarize_results, render_chart, suggest_followup_questions
- `src/quada/nodes/__init__.py` — 빈 파일
- `src/quada/nodes/semantic_query.py` — run_semantic_query_node() 순수 함수
- `src/quada/nodes/quality.py` — run_quality_node() 순수 함수
- `src/quada/nodes/execute.py` — run_execute_node() 순수 함수
- `src/quada/nodes/interpret.py` — run_interpret_node() 순수 함수
- `src/quada/nodes/escalate.py` — run_escalate_node() 순수 함수 (interrupt() 포함)
- `src/quada/semantic/index.py` — MetadataIndex.build(), save(), load()

**교체:**
- `src/quada/llm/client.py` — completion_with_tools() 추가
- `src/quada/agents/base.py` — tool call loop 지원
- `src/quada/agents/semantic_query.py` — index-first + tool call loop
- `src/quada/agents/quality.py` — fine-grained tools + tool call loop
- `src/quada/agents/interpret.py` — tool call loop
- `src/quada/core/orchestrator.py` — LangGraph StateGraph + conditional edges
- `src/quada/cli/app.py` — index build 명령 추가, ask 명령 교체

**삭제:**
- `src/quada/semantic/matcher.py`

---

### Task 1: QuadaState + TerminalResult + langgraph 의존성

**Files:**
- Modify: `pyproject.toml`
- Create: `src/quada/core/state.py`
- Create: `src/quada/tools/__init__.py`
- Create: `src/quada/tools/base.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: langgraph 의존성 추가**

`pyproject.toml`의 dependencies 목록에 추가:
```toml
dependencies = [
    "typer>=0.15.0",
    "rich>=13.0.0",
    "sqlalchemy>=2.0.0",
    "psycopg2-binary>=2.9.0",
    "litellm>=1.55.0,!=1.82.8",
    "pydantic>=2.0.0",
    "pyyaml>=6.0.0",
    "plotext>=5.3.0",
    "python-dotenv>=1.2.2",
    "langgraph>=0.2",
]
```

- [ ] **Step 2: 의존성 설치**

```bash
uv sync
```

Expected: langgraph 설치 완료

- [ ] **Step 3: QuadaState 작성**

`src/quada/core/state.py`:
```python
"""QuadaState: shared state passed between LangGraph nodes."""

from typing import TypedDict


class QuadaState(TypedDict):
    user_query: str
    sql: str | None
    tables_used: list[str]
    resolved_terms: dict          # {"이탈 고객": {sql_condition: ...}, "매출": {expression: ...}}
    quality_results: list         # list of RuleResult-like dicts
    query_results: list           # list of row dicts
    error: str | None             # SQL 실행 오류 메시지
    escalation_question: str | None  # escalate_node에서 interrupt()에 전달할 질문
    user_clarification: str | None   # 사용자가 입력한 답변
    stop_reason: str | None       # 노드 간 routing 제어
```

- [ ] **Step 4: TerminalResult 작성**

`src/quada/tools/__init__.py`: 빈 파일

`src/quada/tools/base.py`:
```python
"""TerminalResult: returned by terminal tools to end the tool call loop."""

from dataclasses import dataclass, field


@dataclass
class TerminalResult:
    """Tool이 반환하면 tool call loop가 종료되고 state_updates가 QuadaState에 반영된다."""
    stop_reason: str
    state_updates: dict = field(default_factory=dict)
    display_value: str = ""  # LLM에게 tool 결과로 보여줄 텍스트
```

- [ ] **Step 5: 테스트 작성**

`tests/test_state.py`:
```python
from quada.core.state import QuadaState
from quada.tools.base import TerminalResult


def test_quada_state_keys():
    state: QuadaState = {
        "user_query": "test",
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
    assert state["user_query"] == "test"
    assert state["stop_reason"] is None


def test_terminal_result_defaults():
    result = TerminalResult(stop_reason="sql_generated")
    assert result.stop_reason == "sql_generated"
    assert result.state_updates == {}
    assert result.display_value == ""


def test_terminal_result_with_updates():
    result = TerminalResult(
        stop_reason="sql_generated",
        state_updates={"sql": "SELECT 1", "tables_used": ["orders"]},
        display_value="SQL generated successfully",
    )
    assert result.state_updates["sql"] == "SELECT 1"
```

- [ ] **Step 6: 테스트 실행**

```bash
uv run pytest tests/test_state.py -v
```

Expected: 3 passed

- [ ] **Step 7: 커밋**

```bash
git add pyproject.toml src/quada/core/state.py src/quada/tools/__init__.py src/quada/tools/base.py tests/test_state.py
git commit -m "feat: add QuadaState, TerminalResult, langgraph dependency"
```

---

### Task 2: llm/client.py — tool calling 지원

**Files:**
- Modify: `src/quada/llm/client.py`
- Create: `tests/test_llm_client_tools.py`

- [ ] **Step 1: 테스트 작성 (실패 확인용)**

`tests/test_llm_client_tools.py`:
```python
"""Tests for LLMClient.completion_with_tools."""
import json
from unittest.mock import MagicMock, patch

from quada.llm.client import LLMClient
from quada.core.config import LLMConfig, AgentLLMConfig, AgentsLLMConfig


def _make_client():
    config = LLMConfig(
        orchestrator=AgentLLMConfig(provider="anthropic", model="claude-haiku-4-5-20251001"),
        agents=AgentsLLMConfig(
            semantic_query=AgentLLMConfig(provider="anthropic", model="claude-haiku-4-5-20251001"),
            quality=AgentLLMConfig(provider="anthropic", model="claude-haiku-4-5-20251001"),
            interpret=AgentLLMConfig(provider="anthropic", model="claude-haiku-4-5-20251001"),
        ),
    )
    return LLMClient(config)


def test_completion_with_tools_no_tool_calls():
    client = _make_client()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Hello"
    mock_response.choices[0].message.tool_calls = None

    with patch("quada.llm.client.litellm_completion", return_value=mock_response):
        msg, tool_calls = client.completion_with_tools(
            role="semantic_query",
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
        )

    assert msg == {"role": "assistant", "content": "Hello"}
    assert tool_calls == []


def test_completion_with_tools_with_tool_call():
    client = _make_client()

    tc = MagicMock()
    tc.id = "call_123"
    tc.function.name = "get_entity_definition"
    tc.function.arguments = json.dumps({"name": "customer"})

    mock_response = MagicMock()
    mock_response.choices[0].message.content = ""
    mock_response.choices[0].message.tool_calls = [tc]

    with patch("quada.llm.client.litellm_completion", return_value=mock_response):
        msg, tool_calls = client.completion_with_tools(
            role="semantic_query",
            messages=[{"role": "user", "content": "hi"}],
            tools=[{"type": "function", "function": {"name": "get_entity_definition", "parameters": {}}}],
        )

    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "get_entity_definition"
    assert tool_calls[0]["args"] == {"name": "customer"}
    assert tool_calls[0]["id"] == "call_123"
    assert "tool_calls" in msg
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```bash
uv run pytest tests/test_llm_client_tools.py -v
```

Expected: FAIL — `completion_with_tools` 없음

- [ ] **Step 3: completion_with_tools 구현**

`src/quada/llm/client.py` 전체 교체:
```python
"""LiteLLM wrapper with per-agent model configuration and tool calling support."""

import json
import re

from litellm import completion as litellm_completion

from quada.core.config import LLMConfig


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences from LLM responses."""
    stripped = re.sub(r"^```\w*\n?", "", text.strip())
    stripped = re.sub(r"\n?```$", "", stripped.strip())
    return stripped.strip()


class LLMClient:
    """Unified LLM client that routes to the correct model per agent role."""

    def __init__(self, config: LLMConfig):
        self.config = config

    def get_model_string(self, role: str) -> str:
        """Get the LiteLLM model string for a given role."""
        if role == "orchestrator":
            cfg = self.config.orchestrator
        elif hasattr(self.config.agents, role):
            cfg = getattr(self.config.agents, role)
        else:
            raise ValueError(f"Unknown role: {role}")
        return f"{cfg.provider}/{cfg.model}"

    def completion(self, role: str, messages: list[dict]) -> str:
        """Call LLM completion for the given role, returns text."""
        model = self.get_model_string(role)
        response = litellm_completion(model=model, messages=messages)
        content = response.choices[0].message.content
        return _strip_code_fences(content)

    def completion_with_tools(
        self,
        role: str,
        messages: list[dict],
        tools: list[dict],
    ) -> tuple[dict, list[dict]]:
        """Call LLM with tool definitions.

        Returns:
            (message_dict, tool_calls)
            message_dict: {"role": "assistant", "content": ..., "tool_calls": [...]}
            tool_calls: [{"name": str, "args": dict, "id": str}, ...]
        """
        model = self.get_model_string(role)
        kwargs = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools

        response = litellm_completion(**kwargs)
        message = response.choices[0].message

        msg_dict: dict = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append({
                    "name": tc.function.name,
                    "args": json.loads(tc.function.arguments),
                    "id": tc.id,
                })

        return msg_dict, tool_calls
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_llm_client_tools.py -v
```

Expected: 2 passed

- [ ] **Step 5: 커밋**

```bash
git add src/quada/llm/client.py tests/test_llm_client_tools.py
git commit -m "feat: add completion_with_tools to LLMClient"
```

---

### Task 3: agents/base.py — tool call loop

**Files:**
- Modify: `src/quada/agents/base.py`
- Create: `tests/test_agent_base.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_agent_base.py`:
```python
"""Tests for BaseAgent tool call loop."""
import json
from unittest.mock import MagicMock, patch

from quada.agents.base import BaseAgent
from quada.tools.base import TerminalResult


def _make_agent():
    mock_client = MagicMock()
    agent = BaseAgent(role="semantic_query", llm_client=mock_client, system_prompt="You are a test agent.")
    return agent, mock_client


def test_tool_loop_no_tool_calls_returns_none():
    """LLM이 tool을 호출하지 않으면 stop_reason=None, state_updates={}."""
    agent, mock_client = _make_agent()
    mock_client.completion_with_tools.return_value = (
        {"role": "assistant", "content": "Done"},
        [],  # no tool calls
    )

    stop_reason, updates = agent.run_tool_loop(
        messages=[{"role": "user", "content": "hi"}],
        tool_definitions=[],
        tool_executors={},
    )

    assert stop_reason is None
    assert updates == {}


def test_tool_loop_terminal_tool_stops_loop():
    """Terminal tool 호출 시 loop 종료 후 TerminalResult 반환."""
    agent, mock_client = _make_agent()

    # First call: LLM calls a regular tool
    # Second call: LLM calls terminal tool
    mock_client.completion_with_tools.side_effect = [
        (
            {"role": "assistant", "content": "", "tool_calls": [{"id": "tc1", "type": "function", "function": {"name": "get_info", "arguments": "{}"}}]},
            [{"name": "get_info", "args": {}, "id": "tc1"}],
        ),
        (
            {"role": "assistant", "content": "", "tool_calls": [{"id": "tc2", "type": "function", "function": {"name": "finish", "arguments": "{}"}}]},
            [{"name": "finish", "args": {}, "id": "tc2"}],
        ),
    ]

    def get_info() -> str:
        return "some info"

    def finish() -> TerminalResult:
        return TerminalResult(
            stop_reason="sql_generated",
            state_updates={"sql": "SELECT 1"},
            display_value="SQL generated",
        )

    stop_reason, updates = agent.run_tool_loop(
        messages=[{"role": "user", "content": "go"}],
        tool_definitions=[],
        tool_executors={"get_info": get_info, "finish": finish},
    )

    assert stop_reason == "sql_generated"
    assert updates == {"sql": "SELECT 1"}
    assert mock_client.completion_with_tools.call_count == 2


def test_tool_loop_unknown_tool_returns_error_to_llm():
    """모르는 tool 호출 시 에러 메시지를 LLM에 반환하고 loop 계속."""
    agent, mock_client = _make_agent()

    mock_client.completion_with_tools.side_effect = [
        (
            {"role": "assistant", "content": "", "tool_calls": [{"id": "tc1", "type": "function", "function": {"name": "unknown_tool", "arguments": "{}"}}]},
            [{"name": "unknown_tool", "args": {}, "id": "tc1"}],
        ),
        ({"role": "assistant", "content": "ok"}, []),
    ]

    stop_reason, updates = agent.run_tool_loop(
        messages=[{"role": "user", "content": "go"}],
        tool_definitions=[],
        tool_executors={},
    )

    assert stop_reason is None
    # 두 번째 LLM 호출의 messages에 tool error 포함 확인
    second_call_messages = mock_client.completion_with_tools.call_args_list[1][1]["messages"]
    tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert "unknown" in tool_msgs[0]["content"].lower()
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```bash
uv run pytest tests/test_agent_base.py -v
```

Expected: FAIL

- [ ] **Step 3: BaseAgent 교체**

`src/quada/agents/base.py`:
```python
"""Base agent with tool call loop support."""

import json

from quada.llm.client import LLMClient
from quada.tools.base import TerminalResult


class BaseAgent:
    """Base class for quada agents. Provides tool call loop via run_tool_loop()."""

    def __init__(self, role: str, llm_client: LLMClient, system_prompt: str):
        self.role = role
        self.llm_client = llm_client
        self.system_prompt = system_prompt

    def run_tool_loop(
        self,
        messages: list[dict],
        tool_definitions: list[dict],
        tool_executors: dict[str, callable],
    ) -> tuple[str | None, dict]:
        """Run ReAct tool call loop until LLM stops or a TerminalResult is returned.

        Args:
            messages: Initial messages (system + user). Modified in-place during loop.
            tool_definitions: OpenAI-format tool schemas.
            tool_executors: {tool_name: callable(**args) -> str | dict | TerminalResult}

        Returns:
            (stop_reason, state_updates)
            stop_reason is None if LLM stopped calling tools without a terminal tool.
        """
        while True:
            msg_dict, tool_calls = self.llm_client.completion_with_tools(
                role=self.role,
                messages=messages,
                tools=tool_definitions,
            )
            messages.append(msg_dict)

            if not tool_calls:
                return None, {}

            for tc in tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                tool_id = tc["id"]

                executor = tool_executors.get(tool_name)
                if executor is None:
                    result_content = f"Error: unknown tool '{tool_name}'"
                    messages.append({"role": "tool", "tool_call_id": tool_id, "content": result_content})
                    continue

                result = executor(**tool_args)

                if isinstance(result, TerminalResult):
                    messages.append({"role": "tool", "tool_call_id": tool_id, "content": result.display_value})
                    return result.stop_reason, result.state_updates

                if isinstance(result, dict):
                    result_content = json.dumps(result, ensure_ascii=False)
                else:
                    result_content = str(result)

                messages.append({"role": "tool", "tool_call_id": tool_id, "content": result_content})
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_agent_base.py -v
```

Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add src/quada/agents/base.py tests/test_agent_base.py
git commit -m "feat: add tool call loop to BaseAgent"
```

---

### Task 4: semantic/index.py — MetadataIndex

**Files:**
- Create: `src/quada/semantic/index.py`
- Create: `tests/test_semantic_index.py`
- Create: `tests/fixtures/models/customers.yaml`
- Create: `tests/fixtures/metrics/revenue.yaml`
- Create: `tests/fixtures/glossary/terms.yaml`

- [ ] **Step 1: fixture YAML 작성**

`tests/fixtures/models/customers.yaml`:
```yaml
entity:
  name: customer
  description: "서비스에 가입한 고객"
  table: public.customers
  columns:
    - name: id
      type: integer
      primary_key: true
    - name: email
      type: string
    - name: last_purchase_date
      type: timestamp
      description: "마지막 구매일"
    - name: segment
      type: string
```

`tests/fixtures/metrics/revenue.yaml`:
```yaml
metric:
  name: revenue
  description: "완료된 주문의 총 매출액"
  type: sum
  expression: "orders.amount"
  filter: "orders.status = 'completed'"
  entities:
    - order
  dimensions: []
  aliases:
    - "매출"
    - "매출액"
```

`tests/fixtures/glossary/terms.yaml`:
```yaml
glossary:
  - term: "이탈 고객"
    definition: "최근 90일간 구매 이력이 없는 고객"
    sql_condition: "customer.last_purchase_date < NOW() - INTERVAL '90 days'"
    entity: customer
    aliases:
      - "churned customer"
      - "비활성 고객"
```

- [ ] **Step 2: 테스트 작성**

`tests/test_semantic_index.py`:
```python
"""Tests for MetadataIndex build, save, load."""
import json
from pathlib import Path
import tempfile

import pytest

from quada.semantic.index import MetadataIndex
from quada.semantic.loader import SemanticLoader


FIXTURES = Path(__file__).parent / "fixtures"


def _load_context():
    loader = SemanticLoader(
        models_dir=FIXTURES / "models",
        metrics_dir=FIXTURES / "metrics",
        glossary_dir=FIXTURES / "glossary",
    )
    return loader.load_all()


def test_build_includes_entities():
    ctx = _load_context()
    index = MetadataIndex.build(ctx)
    names = [e["name"] for e in index.data["entities"]]
    assert "customer" in names


def test_build_entity_has_required_fields():
    ctx = _load_context()
    index = MetadataIndex.build(ctx)
    entity = index.data["entities"][0]
    assert "name" in entity
    assert "table" in entity
    assert "description" in entity
    assert "key_columns" in entity
    assert isinstance(entity["key_columns"], list)


def test_build_includes_metrics():
    ctx = _load_context()
    index = MetadataIndex.build(ctx)
    names = [m["name"] for m in index.data["metrics"]]
    assert "revenue" in names


def test_build_metric_has_required_fields():
    ctx = _load_context()
    index = MetadataIndex.build(ctx)
    metric = index.data["metrics"][0]
    assert "name" in metric
    assert "description" in metric
    assert "entities" in metric


def test_build_includes_glossary():
    ctx = _load_context()
    index = MetadataIndex.build(ctx)
    terms = [g["term"] for g in index.data["glossary"]]
    assert "이탈 고객" in terms


def test_build_glossary_no_aliases():
    """aliases는 인덱스에 포함하지 않는다."""
    ctx = _load_context()
    index = MetadataIndex.build(ctx)
    for term in index.data["glossary"]:
        assert "aliases" not in term


def test_save_and_load(tmp_path):
    ctx = _load_context()
    index = MetadataIndex.build(ctx)

    quada_dir = tmp_path / ".quada"
    index.save(quada_dir)

    assert (quada_dir / "metadata_index.json").exists()

    loaded = MetadataIndex.load(quada_dir)
    assert loaded.data["entities"] == index.data["entities"]
    assert loaded.data["metrics"] == index.data["metrics"]
    assert loaded.data["glossary"] == index.data["glossary"]


def test_load_raises_if_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        MetadataIndex.load(tmp_path / ".quada")
```

- [ ] **Step 3: 테스트 실행 (실패 확인)**

```bash
uv run pytest tests/test_semantic_index.py -v
```

Expected: FAIL — MetadataIndex 없음

- [ ] **Step 4: MetadataIndex 구현**

`src/quada/semantic/index.py`:
```python
"""MetadataIndex: builds and persists a lightweight index of semantic layer YAML files."""

import json
from dataclasses import dataclass
from pathlib import Path

from quada.semantic.loader import SemanticContext


@dataclass
class MetadataIndex:
    """Lightweight index for LLM to decide which entities/metrics/glossary to look up."""

    data: dict  # {"entities": [...], "metrics": [...], "glossary": [...]}

    @classmethod
    def build(cls, context: SemanticContext) -> "MetadataIndex":
        """Build index from a loaded SemanticContext."""
        entities = [
            {
                "name": e.name,
                "table": e.table,
                "description": e.description,
                "key_columns": [c.name for c in e.columns],
            }
            for e in context.entities
        ]

        metrics = [
            {
                "name": m.name,
                "description": m.description,
                "entities": getattr(m, "entities", []),
            }
            for m in context.metrics
        ]

        glossary = [
            {
                "term": t.term,
                "description": t.definition,
                "entity": t.entity,
            }
            for t in context.glossary
        ]

        return cls(data={"entities": entities, "metrics": metrics, "glossary": glossary})

    def save(self, quada_dir: Path) -> None:
        """Save index to <quada_dir>/metadata_index.json."""
        quada_dir.mkdir(parents=True, exist_ok=True)
        index_path = quada_dir / "metadata_index.json"
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, quada_dir: Path) -> "MetadataIndex":
        """Load index from <quada_dir>/metadata_index.json."""
        index_path = quada_dir / "metadata_index.json"
        if not index_path.exists():
            raise FileNotFoundError(
                f"metadata_index.json not found at {index_path}. Run 'quada index build' first."
            )
        with open(index_path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(data=data)

    def to_json_string(self) -> str:
        """Serialize index to JSON string for LLM context."""
        return json.dumps(self.data, ensure_ascii=False, indent=2)
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/test_semantic_index.py -v
```

Expected: 8 passed

- [ ] **Step 6: 커밋**

```bash
git add src/quada/semantic/index.py tests/test_semantic_index.py tests/fixtures/
git commit -m "feat: add MetadataIndex build/save/load"
```

---

### Task 5: quada index build CLI 명령

**Files:**
- Modify: `src/quada/cli/app.py`

- [ ] **Step 1: index 명령 추가**

`src/quada/cli/app.py` 상단 import에 추가:
```python
from quada.semantic.index import MetadataIndex
```

기존 `validate` 명령 다음에 추가:
```python
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
```

- [ ] **Step 2: .gitignore에 .quada/ 추가**

`.gitignore` 파일에 추가 (없으면 생성):
```
.quada/
```

- [ ] **Step 3: 동작 확인 (예시 프로젝트 있을 경우)**

```bash
uv run quada index build --help
```

Expected: index build 명령 도움말 출력

- [ ] **Step 4: 커밋**

```bash
git add src/quada/cli/app.py .gitignore
git commit -m "feat: add quada index build CLI command"
```

---

### Task 6: tools/semantic_tools.py — Semantic Agent 순수 함수 도구

**Files:**
- Create: `src/quada/tools/semantic_tools.py`
- Create: `tests/tools/__init__.py`
- Create: `tests/tools/test_semantic_tools.py`

- [ ] **Step 1: 테스트 작성**

`tests/tools/__init__.py`: 빈 파일

`tests/tools/test_semantic_tools.py`:
```python
"""Tests for semantic tools — pure functions, no LLM calls."""
from quada.semantic.models import Entity, Column, Metric, GlossaryTerm, Relationship
from quada.semantic.loader import SemanticContext
from quada.tools.base import TerminalResult
from quada.tools.semantic_tools import (
    get_entity_definition,
    get_metric_definition,
    get_glossary_term,
    generate_sql,
    report_term_not_found,
)


def _make_context():
    entities = [
        Entity(
            name="customer",
            table="public.customers",
            description="서비스 고객",
            columns=[
                Column(name="id", type="integer", primary_key=True),
                Column(name="email", type="string"),
            ],
            relationships=[],
        )
    ]
    metrics = [
        Metric(
            name="revenue",
            description="총 매출",
            type="sum",
            expression="orders.amount",
            filter="orders.status = 'completed'",
            entities=["order"],
            dimensions=[],
            aliases=["매출"],
        )
    ]
    glossary = [
        GlossaryTerm(
            term="이탈 고객",
            definition="최근 90일 구매 없는 고객",
            sql_condition="customer.last_purchase_date < NOW() - INTERVAL '90 days'",
            entity="customer",
            aliases=["churned customer"],
        )
    ]
    return SemanticContext(entities=entities, metrics=metrics, glossary=glossary)


def test_get_entity_definition_found():
    ctx = _make_context()
    result = get_entity_definition("customer", ctx)
    assert isinstance(result, dict)
    assert result["name"] == "customer"
    assert result["table"] == "public.customers"
    assert any(c["name"] == "id" for c in result["columns"])


def test_get_entity_definition_not_found():
    ctx = _make_context()
    result = get_entity_definition("nonexistent", ctx)
    assert "error" in result


def test_get_metric_definition_found():
    ctx = _make_context()
    result = get_metric_definition("revenue", ctx)
    assert isinstance(result, dict)
    assert result["name"] == "revenue"
    assert result["expression"] == "orders.amount"


def test_get_metric_definition_not_found():
    ctx = _make_context()
    result = get_metric_definition("nonexistent", ctx)
    assert "error" in result


def test_get_glossary_term_found():
    ctx = _make_context()
    result = get_glossary_term("이탈 고객", ctx)
    assert isinstance(result, dict)
    assert result["term"] == "이탈 고객"
    assert "sql_condition" in result
    assert "aliases" not in result  # 인덱스에 aliases 없음


def test_get_glossary_term_not_found():
    ctx = _make_context()
    result = get_glossary_term("없는 용어", ctx)
    assert "error" in result


def test_generate_sql_returns_terminal_result():
    result = generate_sql(
        sql="SELECT SUM(amount) FROM orders",
        tables_used=["orders"],
        resolved_terms={"매출": "revenue"},
    )
    assert isinstance(result, TerminalResult)
    assert result.stop_reason == "sql_generated"
    assert result.state_updates["sql"] == "SELECT SUM(amount) FROM orders"
    assert result.state_updates["tables_used"] == ["orders"]


def test_report_term_not_found_returns_terminal_result():
    result = report_term_not_found(
        term="알 수 없는 용어",
        question="'알 수 없는 용어'의 정의를 입력해주세요.",
    )
    assert isinstance(result, TerminalResult)
    assert result.stop_reason == "term_not_found"
    assert result.state_updates["escalation_question"] == "'알 수 없는 용어'의 정의를 입력해주세요."
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```bash
uv run pytest tests/tools/test_semantic_tools.py -v
```

Expected: FAIL

- [ ] **Step 3: semantic_tools.py 구현**

`src/quada/tools/semantic_tools.py`:
```python
"""Semantic tools: pure functions used by SemanticQueryAgent's tool call loop."""

from quada.semantic.loader import SemanticContext
from quada.tools.base import TerminalResult


def get_entity_definition(name: str, context: SemanticContext) -> dict:
    """Get full entity definition (columns, relationships, table name).

    Called by LLM when it decides it needs schema info for a specific entity.
    """
    for entity in context.entities:
        if entity.name.lower() == name.lower():
            return {
                "name": entity.name,
                "table": entity.table,
                "description": entity.description,
                "columns": [
                    {
                        "name": c.name,
                        "type": c.type,
                        "primary_key": c.primary_key,
                        "description": c.description,
                    }
                    for c in entity.columns
                ],
                "relationships": [
                    {
                        "name": r.name,
                        "type": r.type,
                        "entity": r.entity,
                        "join": r.join,
                    }
                    for r in entity.relationships
                ],
            }
    return {"error": f"Entity '{name}' not found in semantic layer."}


def get_metric_definition(name: str, context: SemanticContext) -> dict:
    """Get full metric definition (expression, filter, dimensions).

    Called by LLM when it identifies a metric in the user query.
    """
    for metric in context.metrics:
        if metric.name.lower() == name.lower():
            result = {
                "name": metric.name,
                "description": metric.description,
                "expression": getattr(metric, "expression", ""),
                "entities": getattr(metric, "entities", []),
            }
            if hasattr(metric, "filter") and metric.filter:
                result["filter"] = metric.filter
            if hasattr(metric, "dimensions"):
                result["dimensions"] = [
                    {"name": d.name, "expression": d.expression}
                    for d in metric.dimensions
                ]
            return result
    return {"error": f"Metric '{name}' not found in semantic layer."}


def get_glossary_term(term: str, context: SemanticContext) -> dict:
    """Get full glossary term definition (sql_condition, entity, definition).

    Called by LLM when it encounters a business term in the user query.
    """
    for t in context.glossary:
        if t.term.lower() == term.lower():
            return {
                "term": t.term,
                "definition": t.definition,
                "sql_condition": t.sql_condition,
                "entity": t.entity,
            }
    return {"error": f"Glossary term '{term}' not found."}


def generate_sql(
    sql: str,
    tables_used: list[str],
    resolved_terms: dict,
) -> TerminalResult:
    """Terminal tool: LLM commits the SQL it generated.

    The LLM calls this tool when it has gathered enough context and generated SQL.
    sql, tables_used, resolved_terms are provided by the LLM in the tool call arguments.
    """
    return TerminalResult(
        stop_reason="sql_generated",
        state_updates={
            "sql": sql,
            "tables_used": tables_used,
            "resolved_terms": resolved_terms,
        },
        display_value=f"SQL committed: {sql[:100]}{'...' if len(sql) > 100 else ''}",
    )


def report_term_not_found(term: str, question: str) -> TerminalResult:
    """Terminal tool: LLM signals that a term cannot be resolved.

    Triggers escalation to ask user for the definition.
    """
    return TerminalResult(
        stop_reason="term_not_found",
        state_updates={"escalation_question": question},
        display_value=f"Escalating: term '{term}' not found.",
    )
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/tools/test_semantic_tools.py -v
```

Expected: 8 passed

- [ ] **Step 5: 커밋**

```bash
git add src/quada/tools/semantic_tools.py tests/tools/
git commit -m "feat: add semantic tools (pure functions)"
```

---

### Task 7: agents/semantic_query.py — index-first + tool call loop

**Files:**
- Modify: `src/quada/agents/semantic_query.py`
- Create: `tests/test_semantic_agent.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_semantic_agent.py`:
```python
"""Tests for SemanticQueryAgent."""
import json
from unittest.mock import MagicMock

from quada.agents.semantic_query import SemanticQueryAgent
from quada.core.state import QuadaState
from quada.semantic.index import MetadataIndex
from quada.semantic.models import Entity, Column, Metric, GlossaryTerm
from quada.semantic.loader import SemanticContext
from quada.tools.base import TerminalResult


def _make_agent():
    mock_client = MagicMock()
    context = SemanticContext(
        entities=[Entity(name="customer", table="customers", columns=[Column(name="id", type="integer", primary_key=True)], relationships=[])],
        metrics=[Metric(name="revenue", type="sum", expression="orders.amount", entities=["order"], dimensions=[], aliases=[])],
        glossary=[GlossaryTerm(term="이탈 고객", definition="90일 구매 없는 고객", sql_condition="...", entity="customer", aliases=[])],
    )
    index = MetadataIndex.build(context)
    return SemanticQueryAgent(llm_client=mock_client, semantic_context=context), mock_client, index


def test_run_returns_sql_generated(mocker):
    agent, mock_client, index = _make_agent()

    # LLM immediately calls generate_sql terminal tool
    mock_client.completion_with_tools.return_value = (
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "tc1", "type": "function", "function": {
                "name": "generate_sql",
                "arguments": json.dumps({
                    "sql": "SELECT COUNT(*) FROM customers",
                    "tables_used": ["customers"],
                    "resolved_terms": {},
                }),
            }}
        ]},
        [{"name": "generate_sql", "args": {
            "sql": "SELECT COUNT(*) FROM customers",
            "tables_used": ["customers"],
            "resolved_terms": {},
        }, "id": "tc1"}],
    )

    state: QuadaState = {
        "user_query": "고객 수 알려줘",
        "sql": None, "tables_used": [], "resolved_terms": {},
        "quality_results": [], "query_results": [], "error": None,
        "escalation_question": None, "user_clarification": None, "stop_reason": None,
    }

    result = agent.run(state, index)

    assert result["stop_reason"] == "sql_generated"
    assert result["sql"] == "SELECT COUNT(*) FROM customers"


def test_run_returns_term_not_found(mocker):
    agent, mock_client, index = _make_agent()

    mock_client.completion_with_tools.return_value = (
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "tc1", "type": "function", "function": {
                "name": "report_term_not_found",
                "arguments": json.dumps({
                    "term": "VIP 고객",
                    "question": "'VIP 고객'의 정의를 알려주세요.",
                }),
            }}
        ]},
        [{"name": "report_term_not_found", "args": {
            "term": "VIP 고객",
            "question": "'VIP 고객'의 정의를 알려주세요.",
        }, "id": "tc1"}],
    )

    state: QuadaState = {
        "user_query": "VIP 고객 매출",
        "sql": None, "tables_used": [], "resolved_terms": {},
        "quality_results": [], "query_results": [], "error": None,
        "escalation_question": None, "user_clarification": None, "stop_reason": None,
    }

    result = agent.run(state, index)

    assert result["stop_reason"] == "term_not_found"
    assert "escalation_question" in result
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```bash
uv run pytest tests/test_semantic_agent.py -v
```

Expected: FAIL

- [ ] **Step 3: SemanticQueryAgent 교체**

`src/quada/agents/semantic_query.py`:
```python
"""Semantic Query Agent: resolves terms and generates SQL via tool call loop."""

from quada.agents.base import BaseAgent
from quada.core.state import QuadaState
from quada.llm.client import LLMClient
from quada.llm.prompts import SEMANTIC_QUERY_SYSTEM_PROMPT
from quada.semantic.index import MetadataIndex
from quada.semantic.loader import SemanticContext
from quada.tools.semantic_tools import (
    get_entity_definition,
    get_metric_definition,
    get_glossary_term,
    generate_sql,
    report_term_not_found,
)

_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_entity_definition",
            "description": "Get full entity schema (columns, relationships, table name) by entity name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Entity name from the metadata index"}
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_metric_definition",
            "description": "Get full metric definition (expression, filter, dimensions) by metric name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Metric name from the metadata index"}
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_glossary_term",
            "description": "Get full glossary term definition (sql_condition, entity) by term name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "term": {"type": "string", "description": "Glossary term from the metadata index"}
                },
                "required": ["term"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_sql",
            "description": "Commit the final SQL you have generated. Call this when you have gathered all needed context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "The SQL query you generated"},
                    "tables_used": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of table names used in the SQL",
                    },
                    "resolved_terms": {
                        "type": "object",
                        "description": "Map of user terms to their resolved definitions",
                    },
                },
                "required": ["sql", "tables_used", "resolved_terms"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report_term_not_found",
            "description": "Call this when a term cannot be resolved from the metadata index. Triggers user escalation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "term": {"type": "string", "description": "The term that could not be resolved"},
                    "question": {"type": "string", "description": "Question to ask the user for clarification"},
                },
                "required": ["term", "question"],
            },
        },
    },
]


class SemanticQueryAgent(BaseAgent):
    """Resolves semantic terms from metadata index and generates SQL via tool call loop."""

    def __init__(self, llm_client: LLMClient, semantic_context: SemanticContext):
        super().__init__(
            role="semantic_query",
            llm_client=llm_client,
            system_prompt=SEMANTIC_QUERY_SYSTEM_PROMPT,
        )
        self.context = semantic_context

    def run(self, state: QuadaState, index: MetadataIndex) -> dict:
        """Run tool call loop. Returns state updates dict."""
        clarification = state.get("user_clarification")

        user_content = (
            f"User query: {state['user_query']}\n\n"
            f"Metadata Index (use this to decide which definitions to look up):\n"
            f"{index.to_json_string()}"
        )
        if clarification:
            user_content += f"\n\nUser clarification: {clarification}"

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
        ]

        tool_executors = {
            "get_entity_definition": lambda name: get_entity_definition(name, self.context),
            "get_metric_definition": lambda name: get_metric_definition(name, self.context),
            "get_glossary_term": lambda term: get_glossary_term(term, self.context),
            "generate_sql": generate_sql,
            "report_term_not_found": report_term_not_found,
        }

        stop_reason, state_updates = self.run_tool_loop(
            messages=messages,
            tool_definitions=_TOOL_DEFINITIONS,
            tool_executors=tool_executors,
        )

        if stop_reason is None:
            # LLM stopped without calling a terminal tool — treat as error
            return {
                "stop_reason": "term_not_found",
                "escalation_question": "쿼리를 처리할 수 없습니다. 질문을 다시 작성해주세요.",
            }

        return {"stop_reason": stop_reason, **state_updates}
```

- [ ] **Step 4: pytest-mock 설치 (필요 시)**

```bash
uv add --dev pytest-mock
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/test_semantic_agent.py -v
```

Expected: 2 passed

- [ ] **Step 6: 커밋**

```bash
git add src/quada/agents/semantic_query.py tests/test_semantic_agent.py pyproject.toml uv.lock
git commit -m "feat: rewrite SemanticQueryAgent with index-first tool call loop"
```

---

### Task 8: tools/quality_tools.py + agents/quality.py

**Files:**
- Create: `src/quada/tools/quality_tools.py`
- Modify: `src/quada/agents/quality.py`
- Create: `tests/tools/test_quality_tools.py`

- [ ] **Step 1: 테스트 작성**

`tests/tools/test_quality_tools.py`:
```python
"""Tests for quality tools."""
from quada.tools.base import TerminalResult
from quada.tools.quality_tools import report_quality_passed, report_quality_warning


def test_report_quality_passed():
    result = report_quality_passed()
    assert isinstance(result, TerminalResult)
    assert result.stop_reason == "quality_passed"


def test_report_quality_warning():
    result = report_quality_warning(
        message="orders.status NULL 3.2% — 매출 ~3% 과소 집계 가능",
        question="품질 경고가 있습니다. 계속 진행하시겠습니까? (y/n)",
    )
    assert isinstance(result, TerminalResult)
    assert result.stop_reason == "quality_warning"
    assert "escalation_question" in result.state_updates
```

- [ ] **Step 2: quality_tools.py 구현**

`src/quada/tools/quality_tools.py`:
```python
"""Quality tools: pure functions used by QualityAgent's tool call loop."""

import asyncio

from quada.db.executor import SQLExecutor
from quada.quality.engine import QualityEngine, QualityCheckResult
from quada.semantic.models import QualityRule
from quada.tools.base import TerminalResult


def get_quality_rules(tables: list[str], rules: list[QualityRule]) -> dict:
    """Get quality rules applicable to the given tables."""
    applicable = [
        {
            "name": r.name,
            "type": r.type,
            "table": r.table,
            "column": r.column,
            "threshold": r.threshold,
        }
        for r in rules
        if r.table in tables
    ]
    return {"rules": applicable, "count": len(applicable)}


def run_quality_checks(
    tables: list[str],
    rules: list[QualityRule],
    executor: SQLExecutor,
) -> dict:
    """Run all quality checks for the given tables and return results."""
    engine = QualityEngine(executor)
    result: QualityCheckResult = asyncio.run(
        engine.check(rules=rules, tables=tables, where_clause=None)
    )
    return {
        "overall_status": result.overall_status,
        "results": [
            {
                "rule_name": r.rule_name,
                "status": r.status,
                "message": r.message,
                "value": r.value,
            }
            for r in result.results
        ],
    }


def report_quality_passed() -> TerminalResult:
    """Terminal tool: quality checks passed, proceed to execution."""
    return TerminalResult(
        stop_reason="quality_passed",
        state_updates={},
        display_value="Quality checks passed.",
    )


def report_quality_warning(message: str, question: str) -> TerminalResult:
    """Terminal tool: quality issues found, ask user to confirm before proceeding."""
    return TerminalResult(
        stop_reason="quality_warning",
        state_updates={"escalation_question": question},
        display_value=f"Quality warning: {message}",
    )
```

- [ ] **Step 3: 테스트 통과 확인**

```bash
uv run pytest tests/tools/test_quality_tools.py -v
```

Expected: 2 passed

- [ ] **Step 4: QualityAgent 교체**

`src/quada/agents/quality.py`:
```python
"""Quality Agent: runs quality checks and analyzes impact via tool call loop."""

from quada.agents.base import BaseAgent
from quada.core.state import QuadaState
from quada.db.executor import SQLExecutor
from quada.llm.client import LLMClient
from quada.llm.prompts import QUALITY_AGENT_SYSTEM_PROMPT
from quada.semantic.models import QualityRule
from quada.tools.quality_tools import (
    get_quality_rules,
    run_quality_checks,
    report_quality_passed,
    report_quality_warning,
)

_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_quality_rules",
            "description": "Get quality rules applicable to the given tables.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Table names to get rules for",
                    }
                },
                "required": ["tables"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_quality_checks",
            "description": "Run all quality checks for the given tables and return results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Table names to check",
                    }
                },
                "required": ["tables"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report_quality_passed",
            "description": "Call this when all quality checks pass. Proceeds to SQL execution.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report_quality_warning",
            "description": "Call this when quality issues are found. Include impact analysis in the message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Impact analysis: what quality issues were found and how they affect the query",
                    },
                    "question": {
                        "type": "string",
                        "description": "Question to ask the user (e.g. 'Quality warning found. Proceed? (y/n)')",
                    },
                },
                "required": ["message", "question"],
            },
        },
    },
]


class QualityAgent(BaseAgent):
    """Runs quality checks and analyzes their impact via tool call loop."""

    def __init__(self, llm_client: LLMClient, rules: list[QualityRule], executor: SQLExecutor):
        super().__init__(
            role="quality",
            llm_client=llm_client,
            system_prompt=QUALITY_AGENT_SYSTEM_PROMPT,
        )
        self.rules = rules
        self.executor = executor

    def run(self, state: QuadaState) -> dict:
        """Run quality check tool loop. Returns state updates dict."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"SQL to execute: {state['sql']}\n"
                    f"Tables used: {state['tables_used']}\n"
                    f"User query: {state['user_query']}\n\n"
                    "Run quality checks on the tables and analyze their impact on this query."
                ),
            },
        ]

        tool_executors = {
            "get_quality_rules": lambda tables: get_quality_rules(tables, self.rules),
            "run_quality_checks": lambda tables: run_quality_checks(tables, self.rules, self.executor),
            "report_quality_passed": lambda: report_quality_passed(),
            "report_quality_warning": report_quality_warning,
        }

        stop_reason, state_updates = self.run_tool_loop(
            messages=messages,
            tool_definitions=_TOOL_DEFINITIONS,
            tool_executors=tool_executors,
        )

        if stop_reason is None:
            return {"stop_reason": "quality_passed"}

        result = {"stop_reason": stop_reason}
        if state_updates:
            result.update(state_updates)
        return result
```

- [ ] **Step 5: 커밋**

```bash
git add src/quada/tools/quality_tools.py src/quada/agents/quality.py tests/tools/test_quality_tools.py
git commit -m "feat: add quality tools and rewrite QualityAgent with tool call loop"
```

---

### Task 9: tools/interpret_tools.py + agents/interpret.py

**Files:**
- Create: `src/quada/tools/interpret_tools.py`
- Modify: `src/quada/agents/interpret.py`

- [ ] **Step 1: interpret_tools.py 구현**

`src/quada/tools/interpret_tools.py`:
```python
"""Interpret tools: result summarization and visualization."""

import json

from quada.tools.base import TerminalResult


def render_chart(rows: list[dict], chart_type: str = "bar") -> str:
    """Render a CLI chart from query results. Returns description of rendered chart."""
    if not rows:
        return "No data to visualize."

    # plotext 기반 차트 렌더링 (간단한 텍스트 표현)
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
```

- [ ] **Step 2: InterpretAgent 교체**

`src/quada/agents/interpret.py`:
```python
"""Interpret Agent: summarizes results and generates insights via tool call loop."""

from quada.agents.base import BaseAgent
from quada.core.state import QuadaState
from quada.llm.client import LLMClient
from quada.llm.prompts import INTERPRET_AGENT_SYSTEM_PROMPT
from quada.tools.interpret_tools import render_chart, finalize_interpretation

_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "render_chart",
            "description": "Render a CLI chart from query results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "rows": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Query result rows",
                    },
                    "chart_type": {
                        "type": "string",
                        "enum": ["bar", "line"],
                        "description": "Chart type",
                    },
                },
                "required": ["rows"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finalize_interpretation",
            "description": "Call this when you have completed the interpretation. Provide summary, insights, and follow-up questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Natural language summary of the results"},
                    "insights": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key insights from the data",
                    },
                    "follow_up_questions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Suggested follow-up questions",
                    },
                    "quality_note": {
                        "type": "string",
                        "description": "Note about data quality impact on results (optional)",
                    },
                },
                "required": ["summary", "insights", "follow_up_questions"],
            },
        },
    },
]


class InterpretAgent(BaseAgent):
    """Interprets query results with natural language summary and insights."""

    def __init__(self, llm_client: LLMClient):
        super().__init__(
            role="interpret",
            llm_client=llm_client,
            system_prompt=INTERPRET_AGENT_SYSTEM_PROMPT,
        )

    def run(self, state: QuadaState) -> dict:
        """Run interpretation tool loop. Returns state updates dict."""
        quality_context = ""
        if state.get("quality_results"):
            failed = [r for r in state["quality_results"] if r.get("status") != "pass"]
            if failed:
                quality_context = f"\nQuality warnings: {failed}"

        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"User query: {state['user_query']}\n"
                    f"SQL executed: {state.get('sql', '')}\n"
                    f"Results ({len(state['query_results'])} rows): "
                    f"{state['query_results'][:50]}"
                    f"{quality_context}"
                ),
            },
        ]

        tool_executors = {
            "render_chart": render_chart,
            "finalize_interpretation": finalize_interpretation,
        }

        stop_reason, state_updates = self.run_tool_loop(
            messages=messages,
            tool_definitions=_TOOL_DEFINITIONS,
            tool_executors=tool_executors,
        )

        return {"stop_reason": stop_reason or "done"}
```

- [ ] **Step 3: 커밋**

```bash
git add src/quada/tools/interpret_tools.py src/quada/agents/interpret.py
git commit -m "feat: add interpret tools and rewrite InterpretAgent with tool call loop"
```

---

### Task 10: nodes/ — 5개 노드 순수 함수

**Files:**
- Create: `src/quada/nodes/__init__.py`
- Create: `src/quada/nodes/semantic_query.py`
- Create: `src/quada/nodes/quality.py`
- Create: `src/quada/nodes/execute.py`
- Create: `src/quada/nodes/interpret.py`
- Create: `src/quada/nodes/escalate.py`

- [ ] **Step 1: 노드 파일들 생성**

`src/quada/nodes/__init__.py`: 빈 파일

`src/quada/nodes/semantic_query.py`:
```python
"""semantic_query_node: wraps SemanticQueryAgent.run() for LangGraph."""

from pathlib import Path

from quada.agents.semantic_query import SemanticQueryAgent
from quada.core.state import QuadaState
from quada.semantic.index import MetadataIndex


def run_semantic_query_node(
    state: QuadaState,
    agent: SemanticQueryAgent,
    project_dir: Path,
) -> dict:
    """Run semantic query agent. Loads metadata index from .quada/."""
    index = MetadataIndex.load(project_dir / ".quada")
    return agent.run(state, index)
```

`src/quada/nodes/quality.py`:
```python
"""quality_node: wraps QualityAgent.run() for LangGraph."""

from quada.agents.quality import QualityAgent
from quada.core.state import QuadaState


def run_quality_node(state: QuadaState, agent: QualityAgent) -> dict:
    """Run quality agent."""
    return agent.run(state)
```

`src/quada/nodes/execute.py`:
```python
"""execute_node: runs SQL and returns results. No LLM."""

from quada.core.state import QuadaState
from quada.db.executor import SQLExecutor


def run_execute_node(state: QuadaState, executor: SQLExecutor) -> dict:
    """Execute the SQL from state. Returns query_results or sql_error."""
    try:
        rows = executor.execute(state["sql"])
        return {"query_results": rows, "error": None, "stop_reason": "executed"}
    except Exception as e:
        error_msg = str(e)
        return {
            "error": error_msg,
            "stop_reason": "sql_error",
            "escalation_question": (
                f"SQL 실행 중 오류가 발생했습니다:\n{error_msg}\n\n"
                "다른 방식으로 쿼리를 재작성하겠습니다. 계속하시겠습니까? (y/n)"
            ),
        }
```

`src/quada/nodes/interpret.py`:
```python
"""interpret_node: wraps InterpretAgent.run() for LangGraph."""

from quada.agents.interpret import InterpretAgent
from quada.core.state import QuadaState


def run_interpret_node(state: QuadaState, agent: InterpretAgent) -> dict:
    """Run interpret agent."""
    return agent.run(state)
```

`src/quada/nodes/escalate.py`:
```python
"""escalate_node: pauses graph with interrupt() and handles user input."""

from langgraph.types import interrupt

from quada.core.state import QuadaState


def run_escalate_node(state: QuadaState) -> dict:
    """Pause graph for user input via interrupt(), then route based on stop_reason."""
    question = state.get("escalation_question", "입력이 필요합니다.")
    user_input: str = interrupt(question)

    match state["stop_reason"]:
        case "term_not_found":
            return {
                "user_clarification": user_input,
                "stop_reason": "term_clarified",
            }
        case "quality_warning":
            if user_input.strip().lower() in ("y", "yes", "예", "네"):
                return {"stop_reason": "execute_approved"}
            return {"stop_reason": "escalation_done"}
        case "sql_error":
            return {
                "user_clarification": f"이전 SQL 실행 오류: {state.get('error', '')}\n사용자 추가 정보: {user_input}",
                "stop_reason": "sql_retry",
            }
        case _:
            return {"stop_reason": "escalation_done"}
```

- [ ] **Step 2: 커밋**

```bash
git add src/quada/nodes/
git commit -m "feat: add node functions for LangGraph (semantic_query, quality, execute, interpret, escalate)"
```

---

### Task 11: core/orchestrator.py — LangGraph StateGraph

**Files:**
- Modify: `src/quada/core/orchestrator.py`
- Create: `tests/test_orchestrator.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_orchestrator.py`:
```python
"""Tests for build_graph — validates graph structure and routing."""
from unittest.mock import MagicMock, patch
from pathlib import Path

from quada.core.orchestrator import build_graph
from quada.core.state import QuadaState


def _make_deps(tmp_path):
    mock_llm = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.quality.rules = []
    mock_executor = MagicMock()
    return mock_llm, mock_ctx, mock_executor, tmp_path


def test_build_graph_returns_compiled_graph(tmp_path):
    llm, ctx, executor, project_dir = _make_deps(tmp_path)
    graph = build_graph(
        llm_client=llm,
        semantic_context=ctx,
        executor=executor,
        project_dir=project_dir,
    )
    # LangGraph compiled graph has invoke method
    assert hasattr(graph, "invoke")


def test_graph_routing_sql_generated_goes_to_quality(tmp_path):
    """semantic_query → quality when stop_reason = sql_generated."""
    llm, ctx, executor, project_dir = _make_deps(tmp_path)

    # Create a .quada/metadata_index.json for the semantic node
    quada_dir = tmp_path / ".quada"
    quada_dir.mkdir()
    (quada_dir / "metadata_index.json").write_text('{"entities":[],"metrics":[],"glossary":[]}')

    graph = build_graph(
        llm_client=llm,
        semantic_context=ctx,
        executor=executor,
        project_dir=project_dir,
    )

    # Patch SemanticQueryAgent.run to return sql_generated
    with patch("quada.agents.semantic_query.SemanticQueryAgent.run") as mock_sem, \
         patch("quada.agents.quality.QualityAgent.run") as mock_qual:
        mock_sem.return_value = {
            "sql": "SELECT 1",
            "tables_used": ["orders"],
            "resolved_terms": {},
            "stop_reason": "sql_generated",
        }
        mock_qual.return_value = {"stop_reason": "quality_passed"}

        # executor.execute called for execute_node
        executor.execute.return_value = [{"count": 1}]

        with patch("quada.agents.interpret.InterpretAgent.run") as mock_interp:
            mock_interp.return_value = {"stop_reason": "done"}

            initial_state: QuadaState = {
                "user_query": "고객 수",
                "sql": None, "tables_used": [], "resolved_terms": {},
                "quality_results": [], "query_results": [], "error": None,
                "escalation_question": None, "user_clarification": None,
                "stop_reason": None,
            }

            result = graph.invoke(
                initial_state,
                config={"configurable": {"thread_id": "test-1"}},
            )

        assert result["stop_reason"] == "done"
        mock_sem.assert_called_once()
        mock_qual.assert_called_once()
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```bash
uv run pytest tests/test_orchestrator.py::test_build_graph_returns_compiled_graph -v
```

Expected: FAIL — build_graph 없음

- [ ] **Step 3: orchestrator.py 교체**

`src/quada/core/orchestrator.py`:
```python
"""Orchestrator: builds and compiles the LangGraph StateGraph."""

from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from quada.agents.interpret import InterpretAgent
from quada.agents.quality import QualityAgent
from quada.agents.semantic_query import SemanticQueryAgent
from quada.core.state import QuadaState
from quada.db.executor import SQLExecutor
from quada.llm.client import LLMClient
from quada.nodes.escalate import run_escalate_node
from quada.nodes.execute import run_execute_node
from quada.nodes.interpret import run_interpret_node
from quada.nodes.quality import run_quality_node
from quada.nodes.semantic_query import run_semantic_query_node
from quada.semantic.loader import SemanticContext


def build_graph(
    llm_client: LLMClient,
    semantic_context: SemanticContext,
    executor: SQLExecutor,
    project_dir: Path,
):
    """Build and compile the LangGraph StateGraph.

    Returns a compiled graph with MemorySaver checkpointer for interrupt() support.
    """
    semantic_agent = SemanticQueryAgent(llm_client=llm_client, semantic_context=semantic_context)
    quality_agent = QualityAgent(
        llm_client=llm_client,
        rules=semantic_context.quality.rules,
        executor=executor,
    )
    interpret_agent = InterpretAgent(llm_client=llm_client)

    # Node closures — capture agents and dependencies
    def semantic_query_node(state: QuadaState) -> dict:
        return run_semantic_query_node(state, semantic_agent, project_dir)

    def quality_node(state: QuadaState) -> dict:
        return run_quality_node(state, quality_agent)

    def execute_node(state: QuadaState) -> dict:
        return run_execute_node(state, executor)

    def interpret_node(state: QuadaState) -> dict:
        return run_interpret_node(state, interpret_agent)

    def escalate_node(state: QuadaState) -> dict:
        return run_escalate_node(state)

    def route(state: QuadaState) -> str:
        return state["stop_reason"]

    # Build graph
    graph = StateGraph(QuadaState)

    graph.add_node("semantic_query", semantic_query_node)
    graph.add_node("quality", quality_node)
    graph.add_node("execute", execute_node)
    graph.add_node("interpret", interpret_node)
    graph.add_node("escalate", escalate_node)

    graph.set_entry_point("semantic_query")

    graph.add_conditional_edges("semantic_query", route, {
        "sql_generated": "quality",
        "term_not_found": "escalate",
    })
    graph.add_conditional_edges("quality", route, {
        "quality_passed": "execute",
        "quality_warning": "escalate",
    })
    graph.add_conditional_edges("execute", route, {
        "executed": "interpret",
        "sql_error": "escalate",
    })
    graph.add_conditional_edges("interpret", route, {
        "done": END,
    })
    graph.add_conditional_edges("escalate", route, {
        "term_clarified": "semantic_query",
        "sql_retry": "semantic_query",
        "execute_approved": "execute",
        "escalation_done": END,
    })

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_orchestrator.py -v
```

Expected: 2 passed

- [ ] **Step 5: 커밋**

```bash
git add src/quada/core/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: rewrite Orchestrator as LangGraph StateGraph with conditional edges"
```

---

### Task 12: cli/app.py — ask 명령 교체 + matcher.py 삭제

**Files:**
- Modify: `src/quada/cli/app.py`
- Delete: `src/quada/semantic/matcher.py`

- [ ] **Step 1: matcher.py 삭제**

```bash
git rm src/quada/semantic/matcher.py
```

- [ ] **Step 2: ask 명령 교체**

`src/quada/cli/app.py`의 import 수정:
```python
from quada.core.orchestrator import build_graph
from quada.core.state import QuadaState
from quada.semantic.index import MetadataIndex
```

기존 `ask` 명령 전체 교체:
```python
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

    # Check metadata index exists
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

    thread_id = "quada-session"
    config_dict = {"configurable": {"thread_id": thread_id}}

    # Run graph with interrupt() support
    while True:
        result = graph.invoke(initial_state, config=config_dict)

        # Check if graph is waiting for interrupt
        state_snapshot = graph.get_state(config_dict)
        if state_snapshot.next:
            # Graph interrupted — get escalation question from state
            current_state = state_snapshot.values
            question = current_state.get("escalation_question", "입력이 필요합니다.")
            console.print(f"\n[yellow]{question}[/yellow]")
            user_input = typer.prompt("")

            # Resume graph with user input
            from langgraph.types import Command
            initial_state = Command(resume=user_input)
        else:
            break

    # Display final results
    if result.get("query_results"):
        from quada.cli.display import print_sql, print_query_results
        print_sql(result.get("sql", ""))
        print_query_results(result["query_results"])
```

- [ ] **Step 3: display.py에 print_query_results 확인/추가**

`src/quada/cli/display.py`에 없으면 추가:
```python
def print_query_results(rows: list[dict]) -> None:
    """Print query results as a Rich table."""
    from rich.table import Table
    from rich.console import Console
    console = Console()
    if not rows:
        console.print("[yellow]No results.[/yellow]")
        return
    table = Table(show_header=True)
    for col in rows[0].keys():
        table.add_column(str(col))
    for row in rows[:100]:
        table.add_row(*[str(v) for v in row.values()])
    console.print(table)
```

- [ ] **Step 4: 기존 SemanticMatcher import 제거**

`src/quada/cli/app.py`에서 이 줄 삭제:
```python
from quada.semantic.matcher import SemanticMatcher  # 삭제
```

그리고 기존 ask 명령의 `matcher = SemanticMatcher(...)` 관련 코드 모두 제거 (Step 2에서 전체 교체했으므로 자동 처리됨)

- [ ] **Step 5: 전체 import 정리 확인**

`src/quada/cli/app.py` 최종 imports:
```python
import typer
from dotenv import load_dotenv
from pathlib import Path
from rich.console import Console

import quada
from quada.cli.display import print_error, print_sql
from quada.core.config import load_config
from quada.core.orchestrator import build_graph
from quada.core.state import QuadaState
from quada.db.connector import create_engine_from_config
from quada.db.executor import SQLExecutor
from quada.llm.client import LLMClient
from quada.semantic.index import MetadataIndex
from quada.semantic.loader import SemanticLoader
```

- [ ] **Step 6: 전체 테스트 실행**

```bash
uv run pytest -v
```

Expected: 모든 테스트 통과

- [ ] **Step 7: 커밋**

```bash
git add src/quada/cli/app.py src/quada/cli/display.py
git commit -m "feat: wire ask command to LangGraph, add interrupt/resume loop, remove SemanticMatcher"
```

---

## Self-Review

**Spec coverage 확인:**

| Spec 요구사항 | 구현 Task |
|---|---|
| LangGraph StateGraph 기반 Orchestrator | Task 11 |
| 5개 노드, 로컬 messages | Task 10, 11 |
| stop_reason 기반 routing (사이클 포함) | Task 11 |
| interrupt() 기반 human-in-the-loop | Task 10 (escalate_node), Task 12 |
| Semantic Query Agent index-first | Task 7 |
| quada index build CLI | Task 5 |
| .quada/metadata_index.json | Task 4 |
| QuadaState | Task 1 |
| TerminalResult 패턴 | Task 1 |
| Tool call loop in BaseAgent | Task 3 |
| completion_with_tools in LLMClient | Task 2 |
| semantic_tools (순수 함수) | Task 6 |
| quality_tools (순수 함수) | Task 8 |
| interpret_tools | Task 9 |
| matcher.py 삭제 | Task 12 |

**Placeholder 없음 확인:** 모든 task에 실제 코드 포함됨.

**Type consistency 확인:**
- `QuadaState` — Task 1에서 정의, 모든 노드/에이전트에서 동일하게 사용
- `TerminalResult(stop_reason, state_updates, display_value)` — Task 1에서 정의, Task 6/8/9에서 일관되게 사용
- `completion_with_tools` — Task 2에서 정의, Task 3 BaseAgent에서 사용
- `run_tool_loop(messages, tool_definitions, tool_executors)` — Task 3에서 정의, Task 7/8/9에서 사용
- `agent.run(state, ...)` — 각 에이전트의 진입점으로 일관성 있음

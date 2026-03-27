# Quada Agentic Redesign Spec

> 기존 하드코딩된 순차 파이프라인을 LangGraph 기반 Supervisor + Sub Agent 구조로 완전 교체

## Problem

기존 Orchestrator는 `semantic → quality → execute → interpret` 순서가 코드에 고정되어 있다.
LLM이 의도 파악에 사용되지만 그 결과가 실행 흐름에 반영되지 않으며, 실패 시 복구 로직이 없다.
또한 Semantic Agent는 모든 YAML 정의를 LLM에 통째로 전달하여 토큰 낭비와 hallucination이 발생한다.

## Why LangGraph

quada의 실행 흐름에는 세 가지 이유로 LangGraph가 적합하다:

1. **사이클 존재**: `term_not_found` / `sql_error` → escalate → semantic_query_node 재시도 흐름이 사이클을 형성
2. **Human-in-the-loop**: `escalate_node`에서 사용자 입력을 기다려야 하며, LangGraph의 `interrupt()`가 이를 처리
3. **State 영속성**: `interrupt()` pause 동안 State를 Checkpointer가 보존, `Command(resume=...)` 으로 재개

## Solution

LangGraph StateGraph를 사용한 Supervisor 패턴:
- Routing은 LLM이 아닌 `conditional_edge` 코드로 구현 — `stop_reason`으로 다음 노드 결정
- 각 노드는 **로컬 messages**를 구성하여 자체 LLM + tool call loop 실행 — 노드 간 컨텍스트 오염 없음
- 사용자 입력이 필요한 시점에 `interrupt()`로 그래프 pause → 사용자 응답 후 재개
- Semantic Query Agent는 전체 YAML 대신 metadata_index를 먼저 보고 LLM이 필요한 항목만 상세 조회

## Architecture

### StateGraph (사이클 포함)

```
                    ┌─────────────────────────────────┐
                    ↓                                 │ (term_not_found → 재시도)
semantic_query_node → quality_node → execute_node → interpret_node → END
        ↑                ↓                ↓
        │          escalate_node ←────────┘ (quality_warning / sql_error)
        │                ↓ interrupt()
        │          [사용자 입력 대기]
        │                ↓ Command(resume=...)
        └────────────────┘ (term_not_found: 사용자 정의 반영 후 재시도)
```

### 노드 구성

```
├─ semantic_query_node  (Sub Agent: LLM + tool call loop)
├─ quality_node         (Sub Agent: LLM + tool call loop)
├─ execute_node         (코드만, LLM 없음)
├─ interpret_node       (Sub Agent: LLM + tool call loop)
└─ escalate_node        (interrupt()로 사용자 입력 대기, LLM 없음)
```

### State — 구조화된 출력만, messages 없음

```python
class QuadaState(TypedDict):
    user_query: str
    sql: str | None
    tables_used: list[str]
    resolved_terms: dict        # {"이탈 고객": {sql_condition: ...}, "매출": {expression: ...}}
    quality_results: list
    query_results: list
    error: str | None
    escalation_question: str | None
    user_clarification: str | None   # escalate 후 사용자가 입력한 답변
    stop_reason: str | None
```

**messages는 State에 없다.** 각 노드가 로컬로 생성하고, 노드 종료 시 사라진다.
노드 간에는 구조화된 필드(sql, quality_results 등)만 공유된다.

### 각 노드의 State 접근

| 노드 | 읽는 State 필드 | 쓰는 State 필드 |
|---|---|---|
| semantic_query | `user_query`, `user_clarification` | `sql`, `tables_used`, `resolved_terms` |
| quality | `sql`, `tables_used` | `quality_results` |
| execute | `sql` | `query_results` |
| interpret | `query_results`, `quality_results`, `user_query` | - |
| escalate | `stop_reason`, `escalation_question` | `user_clarification` |

각 노드는 자기 역할에 필요한 최소 필드만 읽어 로컬 messages를 구성한다:

```python
def quality_node(state: QuadaState):
    messages = [
        SystemMessage(QUALITY_SYSTEM_PROMPT),
        HumanMessage(f"SQL: {state['sql']}\nTables: {state['tables_used']}")
    ]
    # quality agent의 tool call loop — semantic agent의 YAML 대화 내용 안 봄
    result = run_tool_loop(agent, messages, quality_tools)
    return {"quality_results": result.checks, "stop_reason": result.stop_reason}
```

### Routing (stop_reason → next node)

| stop_reason | 다음 노드 | 설명 |
|---|---|---|
| `sql_generated` | `quality_node` | SQL 생성 완료 |
| `term_not_found` | `escalate_node` | 시맨틱 용어 미매칭 → 사용자에게 정의 요청 |
| `term_clarified` | `semantic_query_node` | 사용자 정의 반영 후 재시도 (사이클) |
| `quality_passed` | `execute_node` | 품질 통과 |
| `quality_warning` | `escalate_node` | 품질 경고 → 사용자 확인 요청 |
| `execute_approved` | `execute_node` | 사용자가 품질 경고 수락 |
| `sql_error` | `escalate_node` | SQL 실행 오류 |
| `executed` | `interpret_node` | SQL 실행 완료 |
| `done` | `END` | 해석 완료 |
| `escalation_done` | `END` | 사용자 거부 또는 복구 불가 |

### Human-in-the-loop: escalate_node

```python
from langgraph.types import interrupt, Command

def escalate_node(state: QuadaState):
    user_input = interrupt(state["escalation_question"])  # 그래프 pause

    match state["stop_reason"]:
        case "term_not_found":
            return {"user_clarification": user_input, "stop_reason": "term_clarified"}
        case "quality_warning":
            if user_input.strip().lower() in ("y", "yes"):
                return {"stop_reason": "execute_approved"}
            return {"stop_reason": "escalation_done"}
        case "sql_error":
            return {"stop_reason": "escalation_done"}
```

CLI에서 재개:
```python
graph.invoke(
    Command(resume=user_input),
    config={"configurable": {"thread_id": session_id}}
)
```

---

## Semantic Query Agent — Index-First Selective Loading

YAML 전체를 LLM에 주는 대신, 경량 인덱스를 먼저 보여주고 LLM이 필요한 항목만 선택해 상세 내용을 조회하는 방식.
핵심은 **metadata_index를 얼마나 잘 만드느냐**에 있다.

### metadata_index.json

`quada index build` 명령으로 생성되며 `.quada/metadata_index.json`에 저장된다 (gitignore 대상).
모든 YAML을 파싱하여 LLM이 "어떤 항목을 상세 조회할지" 판단하기에 충분한 정보만 담는다.

```json
{
  "entities": [
    {
      "name": "customer",
      "table": "customers",
      "aliases": ["고객"],
      "description": "서비스에 가입한 고객",
      "key_columns": ["id", "email", "last_purchase_date", "segment"]
    },
    {
      "name": "order",
      "table": "orders",
      "aliases": ["주문"],
      "description": "고객의 구매 주문",
      "key_columns": ["id", "customer_id", "amount", "status", "order_date"]
    }
  ],
  "metrics": [
    {
      "name": "revenue",
      "aliases": ["매출", "수익", "매출액"],
      "description": "완료된 주문의 총 매출액",
      "entities": ["order"]
    },
    {
      "name": "dau",
      "aliases": ["일간 활성 사용자", "DAU"],
      "description": "하루 동안 앱을 사용한 유저 수",
      "entities": ["customer"]
    }
  ],
  "glossary": [
    {
      "term": "이탈 고객",
      "aliases": ["churned customer", "비활성 고객", "이탈자"],
      "description": "최근 90일간 구매 이력이 없는 고객",
      "entity": "customer"
    },
    {
      "term": "신규 고객",
      "aliases": ["new customer", "신규 가입자"],
      "description": "최근 30일 이내 가입한 고객",
      "entity": "customer"
    }
  ]
}
```

**인덱스 설계 원칙:**
- `aliases`: LLM이 사용자 용어와 매핑하는 핵심 필드 — 충분히 넣을수록 좋다
- `key_columns`: 컬럼명만 (타입/설명 없음) — "이 테이블에 내가 필요한 컬럼이 있는가?" 판단용
- `entities`: metric이 어떤 테이블 기반인지 — 조인 구조 추론용
- `entity`: glossary 용어가 어느 테이블에 적용되는지

### Runtime 동작

`semantic_query_node` 실행 시:
1. `.quada/metadata_index.json`을 로드하여 **초기 messages에 포함** — LLM이 전체 인덱스를 본다
2. LLM이 인덱스를 읽고 "어떤 entity/metric/glossary 항목을 상세 조회할지" 판단
3. LLM이 `get_*_definition` 도구를 호출해 필요한 항목의 전체 YAML만 읽어옴
4. 충분한 컨텍스트가 모이면 `generate_sql` 호출

```python
def semantic_query_node(state: QuadaState):
    index = load_metadata_index()  # .quada/metadata_index.json
    clarification = state.get("user_clarification")

    messages = [
        SystemMessage(SEMANTIC_SYSTEM_PROMPT),
        HumanMessage(
            f"Query: {state['user_query']}\n"
            f"Metadata Index:\n{json.dumps(index, ensure_ascii=False)}"
            + (f"\nUser clarification: {clarification}" if clarification else "")
        )
    ]
    # tool call loop — LLM이 get_*_definition 호출 후 generate_sql
```

### ReAct 루프 예시

사용자 쿼리: `"지난달 이탈 고객의 매출 보여줘"`

```
[초기 컨텍스트] metadata_index.json 전체

LLM 판단: "이탈 고객" → glossary 항목, "매출" → revenue metric, customer/order entity 필요

1. LLM → get_glossary_term("이탈 고객")
   ← {sql_condition: "customer.last_purchase_date < NOW() - INTERVAL '90 days'", entity: "customer"}

2. LLM → get_metric_definition("revenue")
   ← {expression: "orders.amount", filter: "orders.status = 'completed'", entities: ["order"]}

3. LLM → get_entity_definition("order")
   ← {table: "orders", columns: [...], relationships: [...]}

4. LLM → generate_sql(...)
   ← "SELECT SUM(o.amount) FROM orders o JOIN customers c ..."
   → stop_reason = "sql_generated"
```

LLM은 전체 YAML 대신 이 쿼리에 필요한 3개 항목의 상세 정보만 보고 SQL을 생성한다.

### 도구 목록

| Tool | 설명 | stop_reason |
|---|---|---|
| `get_entity_definition(name)` | entity 전체 정의 (컬럼, 관계, PK) | - |
| `get_metric_definition(name)` | metric 전체 정의 (expression, filter, dimensions) | - |
| `get_glossary_term(term)` | glossary 전체 정의 (sql_condition, aliases) | - |
| `generate_sql(context)` | 조회된 정의들로 SQL 생성 | `sql_generated` |
| `report_term_not_found(term)` | 매칭 불가 시 에스컬레이션 | `term_not_found` |

---

## Agent Tools 전체

### Semantic Query Agent

| Tool | stop_reason |
|---|---|
| `get_entity_definition(name)` | - |
| `get_metric_definition(name)` | - |
| `get_glossary_term(term)` | - |
| `generate_sql(context)` | `sql_generated` |
| `report_term_not_found(term)` | `term_not_found` |

### Quality Agent

| Tool | stop_reason |
|---|---|
| `get_quality_rules(tables)` | - |
| `run_freshness_check(table, column, threshold)` | - |
| `run_null_ratio_check(table, column, threshold)` | - |
| `run_value_range_check(table, column, min, max)` | - |
| `run_custom_sql_check(query, threshold)` | - |
| `analyze_impact(failures, sql)` | - |
| `report_quality_warning(message)` | `quality_warning` |
| `report_quality_passed()` | `quality_passed` |

### Execute Node (LLM 없음)

| Tool | stop_reason |
|---|---|
| `execute_sql(sql)` | `executed` / `sql_error` |

### Interpret Agent

| Tool | stop_reason |
|---|---|
| `summarize_results(rows, quality_context)` | - |
| `render_chart(rows, chart_type)` | - |
| `suggest_followup_questions(query, results)` | `done` |

---

## Code Structure

```
src/quada/
├── core/
│   ├── orchestrator.py     → 완전 교체: LangGraph StateGraph + conditional edges
│   ├── state.py            → 신규: QuadaState TypedDict 정의
│   └── config.py           → 유지
├── agents/
│   ├── base.py             → 교체: tool call loop 지원
│   ├── semantic_query.py   → 교체: index-first 로드 + tool call loop
│   ├── quality.py          → 교체: fine-grained tools + tool call loop
│   └── interpret.py        → 교체: fine-grained tools + tool call loop
├── tools/                  → 신규: 각 Agent의 tool 함수 (순수 함수)
│   ├── semantic_tools.py   → get_*_definition, generate_sql, report_term_not_found
│   ├── quality_tools.py    → run_*_check, analyze_impact
│   └── interpret_tools.py  → summarize_results, render_chart
├── nodes/                  → 신규: LangGraph 노드 함수
│   ├── semantic_query.py   → semantic_query_node()
│   ├── quality.py          → quality_node()
│   ├── execute.py          → execute_node()
│   ├── interpret.py        → interpret_node()
│   └── escalate.py         → escalate_node() — interrupt() 포함
├── semantic/
│   ├── index.py            → 신규: YAML → metadata_index.json 빌드 / .quada/에 저장 및 로드
│   ├── loader.py           → 유지: YAML 파싱, 전체 정의 로드 (get_*_definition 도구가 사용)
│   ├── models.py           → 유지: Pydantic 모델
│   ├── matcher.py          → 제거: index-first 방식으로 대체
│   └── dbt_adapter.py      → 유지
└── ... (나머지 유지)
```

**의존성 방향 (단방향):**
```
CLI → core/orchestrator → nodes → agents → tools → semantic/quality/db/llm
```

## Tech Stack 변경

| 항목 | 기존 | 변경 |
|---|---|---|
| Orchestration | 직접 구현 (순차) | LangGraph StateGraph |
| Agent 패턴 | 1회 LLM 호출 | Tool call loop (ReAct) |
| Routing | 하드코딩 | stop_reason 기반 conditional_edge |
| Human-in-the-loop | 없음 | LangGraph interrupt() + Checkpointer |
| Metadata 전달 | 전체 YAML → LLM | index 먼저 → LLM이 선택 → 상세 조회 |
| Index 관리 | 없음 | `.quada/metadata_index.json` (`quada index build`로 생성) |

추가 의존성: `langgraph>=0.2`

## Error Handling

| 에러 | stop_reason | 처리 |
|---|---|---|
| 시맨틱 용어 미매칭 | `term_not_found` | escalate → 사용자 정의 입력 → semantic_query_node 재시도 |
| SQL 실행 오류 | `sql_error` | escalate → 사용자에게 오류 안내 → END |
| 품질 경고 | `quality_warning` | escalate → 영향도 + 사용자 확인 → Y: execute / N: END |

## Testing Strategy

| Layer | 대상 | 방법 |
|---|---|---|
| Unit | `tools/` 함수 | 순수 함수, mock 없이 테스트 가능 |
| Unit | `semantic/index.py` 인덱스 빌드 로직 | fixture YAML로 검증 |
| Unit | Agent tool call loop | LLM mock |
| Integration | 노드 간 State 전달 + 사이클 | LangGraph test utilities |
| Integration | interrupt() / resume | LangGraph `MemorySaver` + `Command(resume=...)` |
| E2E | 전체 그래프 실행 | 실제 LLM + testcontainers PostgreSQL |

## Scope

### In Scope
- LangGraph StateGraph 기반 Orchestrator 교체
- 5개 노드, 로컬 messages (State isolation)
- stop_reason 기반 routing (사이클 포함)
- interrupt() 기반 human-in-the-loop
- Semantic Query Agent index-first 선택적 로드
- `quada index build` CLI 명령 추가
- `.quada/metadata_index.json` 생성 및 로드
- QuadaState 정의

### Out of Scope (향후)
- Vector DB 기반 시맨틱 검색
- 기존 semantic/quality/db/llm 레이어 내부 로직 변경 (semantic/index.py 신규 제외)
- dbt 연동, 클라우드 DB 지원

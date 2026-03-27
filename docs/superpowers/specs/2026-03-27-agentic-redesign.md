# Quada Agentic Redesign Spec

> 기존 하드코딩된 순차 파이프라인을 LangGraph 기반 Supervisor + Sub Agent 구조로 완전 교체

## Problem

기존 Orchestrator는 `semantic → quality → execute → interpret` 순서가 코드에 고정되어 있다.
LLM이 의도 파악에 사용되지만 그 결과가 실행 흐름에 반영되지 않으며, 실패 시 복구 로직이 없다.

## Why LangGraph

quada의 실행 흐름에는 세 가지 이유로 LangGraph가 적합하다:

1. **사이클 존재**: `term_not_found` / `sql_error` → escalate → semantic_query_node 재시도 흐름이 사이클을 형성
2. **Human-in-the-loop**: `escalate_node`에서 사용자 입력을 기다려야 하며, LangGraph의 `interrupt()`가 이를 처리
3. **State 영속성**: `interrupt()` pause 동안 State를 Checkpointer가 보존, `Command(resume=...)` 으로 재개

커스텀 구현으로도 가능하지만 사이클 + interrupt + 상태 영속성을 직접 구현하면 LangGraph의 절반을 다시 짜는 셈이다.

## Solution

LangGraph StateGraph를 사용한 Supervisor 패턴:
- Routing은 LLM이 아닌 `conditional_edge` 코드로 구현 — `stop_reason`으로 다음 노드 결정
- 각 노드는 자체 LLM + fine-grained tool call loop를 가진 Sub Agent
- 사용자 입력이 필요한 시점에 `interrupt()`로 그래프 pause → 사용자 응답 후 재개
- 사이클: escalate 후 관련 노드로 복귀 가능

## Architecture

### StateGraph (사이클 포함)

```
                    ┌─────────────────────────────────┐
                    ↓                                 │ (term_not_found / sql_error → 재시도)
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

### State

```python
class QuadaState(TypedDict):
    user_query: str
    messages: list                   # LangGraph 표준 메시지 히스토리
    sql: str | None
    tables_used: list[str]
    resolved_terms: dict
    quality_results: list
    query_results: list
    error: str | None                # 현재 에러 컨텍스트
    escalation_question: str | None  # interrupt()에 전달할 질문
    user_clarification: str | None   # 사용자가 입력한 답변
    stop_reason: str | None          # 노드 간 routing 제어
```

### Routing (stop_reason → next node)

| stop_reason | 다음 노드 | 설명 |
|---|---|---|
| `sql_generated` | `quality_node` | SQL 생성 완료 |
| `term_not_found` | `escalate_node` | 시맨틱 용어 미매칭 → 사용자에게 정의 요청 |
| `term_clarified` | `semantic_query_node` | 사용자 정의 반영 후 재시도 (사이클) |
| `quality_passed` | `execute_node` | 품질 통과 |
| `quality_warning` | `escalate_node` | 품질 경고 → 사용자 확인 요청 |
| `execute_approved` | `execute_node` | 사용자가 품질 경고 수락 후 실행 |
| `sql_error` | `escalate_node` | SQL 실행 오류 → 사용자에게 오류 안내 |
| `executed` | `interpret_node` | SQL 실행 완료 |
| `done` | `END` | 해석 완료 |
| `escalation_done` | `END` | 사용자가 거부하거나 복구 불가 |

### Human-in-the-loop: escalate_node

```python
from langgraph.types import interrupt, Command

def escalate_node(state: QuadaState):
    # 그래프 pause — State는 Checkpointer에 보존
    user_input = interrupt(state["escalation_question"])

    # 사용자 응답에 따라 다음 stop_reason 결정
    match state["stop_reason"]:
        case "term_not_found":
            # 사용자 정의를 State에 반영 후 semantic_query_node 재시도
            return {"user_clarification": user_input, "stop_reason": "term_clarified"}
        case "quality_warning":
            if user_input.strip().lower() in ("y", "yes"):
                return {"stop_reason": "execute_approved"}
            else:
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

## Agent Tools

### Semantic Query Agent

| Tool | 설명 | stop_reason |
|---|---|---|
| `lookup_glossary_term(term)` | glossary에서 비즈니스 용어 조회 | - |
| `lookup_metric(name)` | metric 정의 조회 (expression, filter, aliases) | - |
| `lookup_entity(name)` | entity/table 스키마 조회 | - |
| `generate_sql(context)` | 조회한 컨텍스트로 SQL 생성 | `sql_generated` |
| `report_term_not_found(term)` | 매칭 실패 시 에스컬레이션 요청 | `term_not_found` |

`user_clarification`이 State에 있으면 해당 내용을 컨텍스트에 포함하여 재시도.

### Quality Agent

| Tool | 설명 | stop_reason |
|---|---|---|
| `get_quality_rules(tables)` | 대상 테이블의 품질 규칙 로드 | - |
| `run_freshness_check(table, column, threshold)` | 최신성 검사 | - |
| `run_null_ratio_check(table, column, threshold)` | NULL 비율 검사 | - |
| `run_value_range_check(table, column, min, max)` | 값 범위 검사 | - |
| `run_custom_sql_check(query, threshold)` | 커스텀 SQL 규칙 실행 | - |
| `analyze_impact(failures, sql)` | 실패한 규칙이 현재 쿼리에 미치는 영향 LLM 분석 | - |
| `report_quality_warning(message)` | warn → 사용자 확인 요청 | `quality_warning` |
| `report_quality_passed()` | 품질 통과 | `quality_passed` |

### Execute Node (LLM 없음)

| Tool | 설명 | stop_reason |
|---|---|---|
| `execute_sql(sql)` | read-only 트랜잭션으로 SQL 실행 | `executed` / `sql_error` |

### Interpret Agent

| Tool | 설명 | stop_reason |
|---|---|---|
| `summarize_results(rows, quality_context)` | 결과를 자연어로 요약, 품질 경고 반영 | - |
| `render_chart(rows, chart_type)` | CLI 차트 생성 (plotext) | - |
| `suggest_followup_questions(query, results)` | 후속 질문 제안 | `done` |

## Code Structure

```
src/quada/
├── core/
│   ├── orchestrator.py     → 완전 교체: LangGraph StateGraph + conditional edges
│   ├── state.py            → 신규: QuadaState TypedDict 정의
│   └── config.py           → 유지
├── agents/
│   ├── base.py             → 교체: BaseAgent가 LangGraph tool call loop 지원
│   ├── semantic_query.py   → 교체: fine-grained tools + tool call loop
│   ├── quality.py          → 교체: fine-grained tools + tool call loop
│   └── interpret.py        → 교체: fine-grained tools + tool call loop
├── tools/                  → 신규: 각 Agent의 tool 함수 모음 (순수 함수)
│   ├── semantic_tools.py   → lookup_glossary_term, lookup_metric, generate_sql ...
│   ├── quality_tools.py    → run_*_check, analyze_impact ...
│   └── interpret_tools.py  → summarize_results, render_chart ...
├── nodes/                  → 신규: LangGraph 노드 함수
│   ├── semantic_query.py   → semantic_query_node()
│   ├── quality.py          → quality_node()
│   ├── execute.py          → execute_node()
│   ├── interpret.py        → interpret_node()
│   └── escalate.py         → escalate_node() — interrupt() 포함
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

LangGraph 의존성 추가: `langgraph>=0.2`

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
| Unit | Agent tool call loop | LLM mock |
| Integration | 노드 간 State 전달 + 사이클 | LangGraph test utilities |
| Integration | interrupt() / resume | LangGraph `MemorySaver` + `Command(resume=...)` |
| E2E | 전체 그래프 실행 | 실제 LLM + testcontainers PostgreSQL |

## Scope

### In Scope
- LangGraph StateGraph 기반 Orchestrator 교체
- 5개 노드 구현 (semantic_query, quality, execute, interpret, escalate)
- 각 Agent fine-grained tool 구현
- stop_reason 기반 routing (사이클 포함)
- interrupt() 기반 human-in-the-loop
- QuadaState 정의

### Out of Scope
- 기존 semantic/quality/db/llm 레이어 내부 로직 변경
- dbt 연동, 클라우드 DB 지원
- 새로운 CLI 명령어 추가

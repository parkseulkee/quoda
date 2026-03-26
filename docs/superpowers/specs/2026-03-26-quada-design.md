# Quada Design Spec

> Quality · Quantitative · Query — 시맨틱 레이어 + 데이터 품질 + 자연어 쿼리를 통합한 오픈소스 데이터 에이전트

## Problem

기존 text-to-SQL 도구들은 자연어를 SQL로 변환해 실행할 뿐, 데이터의 품질을 검증하지 않는다. 데이터가 최신이 아니거나 NULL 비율이 높은 상태에서 쿼리 결과를 그대로 분석하면 잘못된 의사결정으로 이어진다.

또한 회사마다 "매출", "활성 사용자", "이탈 고객" 등 메트릭과 용어의 정의가 다른데, 이를 명시적으로 정의하고 쿼리에 반영하는 시맨틱 레이어가 필요하다.

## Solution

quada는 자연어 쿼리가 들어오면:
1. 시맨틱 레이어에서 메트릭/용어 정의를 확인하고 SQL을 생성
2. 쿼리 실행 전에 대상 데이터의 품질을 검증
3. 품질 이슈 발견 시 영향도를 분석하여 사용자에게 경고
4. 사용자 확인 후 실행, 결과를 자연어로 해석하고 시각화

## Architecture

### 3-Agent + Orchestrator

```
CLI Interface
    ↓
Orchestrator (LLM: Large Model — Opus, GPT-4o)
    ├── Semantic Query Agent (LLM: Small — Haiku, GPT-4o-mini)
    ├── Quality Agent (LLM: Small — Haiku, GPT-4o-mini)
    └── Interpret Agent (LLM: Medium — Sonnet, GPT-4o)
    ↓
Shared Tools: semantic_lookup(), check_quality(), execute_sql(), render_chart()
    ↓
YAML Config | Database | LLM Provider | dbt (optional)
```

**에이전트별 독립 LLM 설정:** Orchestrator는 복잡한 의도 파악을 위해 큰 모델, 각 에이전트는 특화된 작은 모델을 사용하여 비용을 최적화한다. 모든 에이전트는 LLM 기반이며, provider와 model을 각각 독립적으로 설정할 수 있다.

### Agents

**Orchestrator**
- LLM 기반 의도 파악 및 실행 계획 수립
- 에이전트 호출 순서 결정 및 조율
- 에러 핸들링 및 재시도 관리

**Semantic Query Agent**
- 시맨틱 레이어에서 메트릭, 엔티티, 용어 사전 조회
- 3단계 매칭: Exact Match → Fuzzy Match (LLM) → No Match
- 시맨틱 컨텍스트를 기반으로 SQL 생성 및 실행

**Quality Agent**
- 쿼리 대상 테이블의 품질 규칙 로드 및 실행
- LLM 기반 영향도 분석 (품질 이슈가 현재 쿼리에 미치는 영향 판단)
- 결과: pass / warn (사용자 확인 후 진행 가능) / fail

**Interpret Agent**
- 쿼리 결과를 자연어로 요약
- 품질 경고 컨텍스트를 반영한 인사이트 도출 (오차 범위 등)
- CLI 차트/그래프 생성
- 후속 질문 제안

## Execution Flow

```
1. User Input: quada ask "지난달 이탈 고객의 매출 보여줘"
2. Orchestrator (Large LLM): 의도 파악 → 실행 계획 수립
3. Semantic Query Agent: "이탈 고객" → glossary 조회 → "매출" → metric 조회 → SQL 생성
4. Quality Agent: 생성된 SQL의 WHERE 조건과 동일한 범위에서 품질 규칙 실행
   - pass → 바로 실행
   - warn → 영향도 분석 후 사용자 확인 (기본 차단, 오버라이드 가능)
5. Semantic Query Agent: SQL 실행
6. Interpret Agent: 결과 해석 + 품질 컨텍스트 반영 + 시각화
```

## Semantic Layer

### File Structure

```
quada-project/
├── quada.yaml              # 메인 설정 (DB 연결, LLM 설정)
├── models/                 # 엔티티 정의
│   ├── customers.yaml
│   └── orders.yaml
├── metrics/                # 메트릭 정의
│   ├── revenue.yaml
│   └── dau.yaml
├── glossary/               # 비즈니스 용어 사전
│   └── terms.yaml
└── quality/                # 데이터 품질 규칙
    └── rules.yaml
```

### Entity Definition (models/customers.yaml)

```yaml
entity:
  name: customer
  description: "서비스에 가입한 고객"
  table: public.customers

  columns:
    - name: id
      type: integer
      primary_key: true
    - name: name
      type: string
    - name: email
      type: string
    - name: created_at
      type: timestamp
      description: "가입일"
    - name: last_purchase_date
      type: timestamp
      description: "마지막 구매일"

  relationships:
    - name: orders
      type: one_to_many
      entity: order
      join: "customer.id = order.customer_id"
```

### Metric Definition (metrics/revenue.yaml)

```yaml
metric:
  name: revenue
  description: "완료된 주문의 총 매출액"
  type: sum                    # sum, count, avg, count_distinct, derived
  expression: "orders.amount"
  filter: "orders.status = 'completed'"

  entities:
    - order

  dimensions:
    - name: period
      expression: "DATE_TRUNC('month', orders.order_date)"
    - name: customer_segment
      expression: "customers.segment"

  aliases:
    - "매출"
    - "매출액"
    - "수익"
    - "revenue"
    - "sales"
```

### Derived Metric (metrics/arpu.yaml)

```yaml
metric:
  name: arpu
  description: "활성 사용자 1인당 평균 매출"
  type: derived
  expression: "revenue / dau"

  aliases:
    - "인당 매출"
    - "ARPU"
    - "객단가"
```

### Business Glossary (glossary/terms.yaml)

```yaml
glossary:
  - term: "이탈 고객"
    definition: "최근 90일간 구매 이력이 없는 고객"
    sql_condition: "customer.last_purchase_date < NOW() - INTERVAL '90 days'"
    entity: customer
    aliases:
      - "churned customer"
      - "이탈자"
      - "비활성 고객"

  - term: "신규 고객"
    definition: "최근 30일 이내 가입한 고객"
    sql_condition: "customer.created_at >= NOW() - INTERVAL '30 days'"
    entity: customer
    aliases:
      - "new customer"
      - "신규 가입자"
```

### dbt Semantic Layer Integration

```yaml
# quada.yaml
semantic_layer:
  source: dbt                # "local" (자체 YAML) 또는 "dbt"
  dbt:
    project_dir: ./dbt_project
    profiles_dir: ~/.dbt
  merge_glossary: true       # dbt 메트릭 + quada 용어 사전 혼합 사용
```

## Semantic Matching Strategy

3단계로 자연어 용어를 시맨틱 레이어에 매칭한다.

**Step 1: Exact Match** — aliases에 정확히 일치하면 바로 확정. 토큰 비용 없음.

**Step 2: Fuzzy Match (LLM)** — Exact Match 실패 시, Semantic Query Agent가 LLM으로 용어 사전에서 의미적으로 유사한 후보를 탐색. 후보를 사용자에게 제시하여 확인.
- 예: "비활성 유저" → "이탈 고객"을 말씀하시나요?

**Step 3: No Match** — 유사 후보도 없으면 사용자에게 직접 정의를 요청. 입력받은 정의를 glossary에 신규 등록.

**학습:** 사용자가 확인/정의한 매핑은 aliases에 자동 추가. 다음번에는 Exact Match로 처리되어, 사용할수록 매칭 정확도가 올라간다.

## Data Quality

### Quality Rules (quality/rules.yaml)

```yaml
quality:
  rules:
    # 최신성 검사
    - name: orders_freshness
      type: freshness
      table: orders
      column: updated_at
      threshold: "24 hours"

    # NULL 비율 검사
    - name: orders_status_not_null
      type: null_ratio
      table: orders
      column: status
      threshold: 0.01

    # 값 범위 검사
    - name: orders_amount_range
      type: value_range
      table: orders
      column: amount
      min: 0
      max: 100000000

    # 유니크 제약
    - name: customers_email_unique
      type: unique
      table: customers
      column: email

    # 커스텀 SQL 규칙
    - name: no_future_orders
      type: custom_sql
      query: >
        SELECT COUNT(*) as violations
        FROM orders
        WHERE order_date > NOW()
      threshold: 0
```

### Quality Check Approach

- **On-demand:** `quada ask` 실행 시 쿼리 대상 범위 내에서 품질 검증
- **Scoped validation:** 전체 테이블이 아닌 생성된 SQL의 WHERE 조건과 동일한 범위에서만 검증하여 성능 확보
- **독립 실행:** `quada check [table]` 명령으로 쿼리 없이 품질만 확인 가능 (이 경우 전체 테이블 대상으로 검증)
- **건너뛰기:** `--skip-quality` 플래그로 품질 검증 생략 가능
- **자체 경량 품질 엔진:** GX의 룰 기반 접근을 참고하되, YAML 정의 → SQL 생성/실행하는 경량 엔진을 자체 구현
- **병렬 실행:** 품질 규칙들은 독립적이므로 병렬로 검증하여 성능을 확보한다.
  - 합칠 수 있는 규칙(freshness, null_ratio, value_range, enum 등)은 하나의 SQL 쿼리로 합쳐서 1회 DB 라운드트립으로 처리
  - 합칠 수 없는 규칙(custom_sql)은 `asyncio.gather`로 동시 실행
  - 전략: 합칠 수 있는 건 합치고, 나머지는 병렬 실행

### Quality Failure Handling

기본적으로 품질 실패 시 차단하되, 사용자가 원하면 실행 가능 (warning 모드):
- Quality Agent가 LLM으로 영향도를 분석 (예: "status NULL 3.2%로 매출 ~3% 과소 집계 가능")
- 사용자에게 영향도와 함께 경고 표시
- 사용자 확인(Y) 시 실행, Interpret Agent가 품질 경고를 결과 해석에 반영

## Configuration (quada.yaml)

```yaml
# 데이터베이스 연결
database:
  type: postgresql
  host: localhost
  port: 5432
  name: mydb
  user: ${DB_USER}
  password: ${DB_PASSWORD}

# 시맨틱 레이어 소스
semantic_layer:
  source: local              # "local" 또는 "dbt"

# LLM 설정 — 에이전트별 독립 모델
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

## Tech Stack

| Component | Technology | Reason |
|---|---|---|
| Language | Python 3.11+ | 데이터 생태계 호환성, 오픈소스 성장 가능성 |
| Package Manager | uv | 빠른 의존성 관리 |
| CLI Framework | Typer + Rich | 깔끔한 CLI UX |
| DB Connector | SQLAlchemy | 다중 DB 지원, ORM 없이 raw SQL 실행 |
| LLM Interface | LiteLLM | 다중 LLM 통합 인터페이스 (추후 자체 구현으로 교체 가능) |
| YAML Parsing | Pydantic + PyYAML | 스키마 검증, 타입 안전성 |
| Visualization | Plotext | 터미널 차트, 외부 의존성 최소 |
| Testing | pytest | 표준 테스트 프레임워크 |

**LiteLLM 참고:** 1.82.8 버전에 공급망 공격(credential stealer) 이력 있음. 버전 고정 필수. LLM 호출을 `llm/client.py` 인터페이스 뒤에 추상화하여, 추후 자체 구현으로 교체 시 이 파일만 수정하면 되도록 설계.

**품질 엔진:** GX의 룰 기반(JSON 정의 → 검증 쿼리 실행) 접근을 참고하되, GX에 의존하지 않고 자체 경량 엔진으로 구현. YAML로 규칙을 정의하고, 규칙 타입별로 검증 SQL을 생성/실행하는 구조.

## Project Structure

```
quada/
├── pyproject.toml
├── src/
│   └── quada/
│       ├── cli/                    # CLI Layer (thin wrapper)
│       │   ├── app.py              # Typer app, 엔트리포인트
│       │   └── display.py          # Rich 기반 출력 포매팅
│       ├── core/                   # Core Library
│       │   ├── orchestrator.py     # LLM 기반 오케스트레이터
│       │   └── config.py           # quada.yaml 로드, 설정 관리
│       ├── agents/                 # Agent Layer
│       │   ├── base.py             # BaseAgent (공통 LLM 호출 로직)
│       │   ├── semantic_query.py   # Semantic Query Agent
│       │   ├── quality.py          # Quality Agent
│       │   └── interpret.py        # Interpret Agent
│       ├── semantic/               # Semantic Layer
│       │   ├── loader.py           # YAML 파싱, 시맨틱 레이어 로드
│       │   ├── models.py           # Entity, Metric, Glossary Pydantic 모델
│       │   ├── matcher.py          # Exact/Fuzzy 매칭 로직
│       │   └── dbt_adapter.py      # dbt Semantic Layer 연동
│       ├── quality/                # Data Quality Engine
│       │   ├── engine.py           # 자체 경량 검증 엔진
│       │   ├── rules.py            # Rule 타입 정의
│       │   └── executor.py          # 품질 검증 SQL 생성 및 실행
│       ├── db/                     # Database Layer
│       │   ├── connector.py        # SQLAlchemy 기반 DB 연결
│       │   └── executor.py         # SQL 실행 (read-only 트랜잭션)
│       ├── llm/                    # LLM Layer
│       │   ├── client.py           # LiteLLM 래퍼 (교체 가능 인터페이스)
│       │   └── prompts.py          # 에이전트별 시스템 프롬프트
│       └── viz/                    # Visualization
│           └── charts.py           # Plotext 기반 CLI 차트
└── tests/
    ├── test_orchestrator.py
    ├── test_semantic_query.py
    ├── test_quality.py
    ├── test_interpret.py
    ├── test_matcher.py
    └── fixtures/                   # 테스트용 YAML, mock 데이터
```

**의존성 방향 (단방향):** CLI → Core → Agents → Semantic / Quality / DB / LLM

## CLI Interface

```bash
# 자연어 쿼리
$ quada ask "지난달 이탈 고객의 매출 보여줘"

# 프로젝트 초기화
$ quada init

# 시맨틱 레이어 검증
$ quada validate

# 데이터 품질 체크 (독립 실행)
$ quada check [table]

# 설정 확인
$ quada config show

# 품질 무시하고 강제 실행
$ quada ask "지난달 매출" --skip-quality
```

## Error Handling

| 에러 유형 | 패턴 | 처리 |
|---|---|---|
| DB 연결 실패 | FATAL | 명확한 에러 메시지 + 설정 파일 경로 안내 |
| LLM API 실패 | RETRY | 자동 재시도 (최대 3회, exponential backoff) |
| 시맨틱 매칭 실패 | INTERACTIVE | Fuzzy Match 후보 제시 or 사용자에게 정의 요청 |
| 데이터 품질 실패 | WARNING | 영향도 분석 + 사용자 확인 후 실행 가능 |
| SQL 실행 오류 | RETRY | 에러 메시지를 LLM에 전달하여 SQL 재생성 (최대 2회) |
| YAML 검증 오류 | EARLY CHECK | `quada validate`로 사전 검증 + Pydantic 에러 메시지 |

## Testing Strategy

| Layer | Scope | LLM | DB |
|---|---|---|---|
| Unit | 매칭, 파싱, 규칙 로직, Pydantic 모델 | Mock | Mock |
| Integration | 에이전트↔DB 연동, 시맨틱→SQL→실행 파이프라인 | Mock | PostgreSQL (testcontainers) |
| E2E | CLI 입력→최종 출력 전체 흐름 | 실제 호출 (CI에서는 선택적) | PostgreSQL (testcontainers) |

## Security

- **SQL Injection 방지:** LLM이 생성한 SQL은 read-only 트랜잭션에서 실행. DDL/DML 차단.
- **API 키 관리:** quada.yaml에 직접 넣지 않고, 환경변수 참조 (`${DB_PASSWORD}`).
- **의존성 관리:** LiteLLM 등 외부 의존성 버전 고정 (pinning).

## Scope

### In Scope (MVP)
- CLI 도구 (`quada ask`, `quada check`, `quada init`, `quada validate`)
- 자체 YAML 시맨틱 레이어 (엔티티, 메트릭, 용어 사전)
- 3-Agent 아키텍처 (Semantic Query, Quality, Interpret)
- 에이전트별 독립 LLM 설정
- On-demand 데이터 품질 검증 (쿼리 범위 내)
- 자체 경량 품질 검증 엔진 (GX 참고, 자체 구현)
- PostgreSQL 지원
- CLI 시각화 (Plotext)
- 시맨틱 매칭 학습 (aliases 자동 추가)

### Out of Scope (Future)
- API 서버 (REST/GraphQL)
- dbt Semantic Layer 연동
- 클라우드 데이터 웨어하우스 (BigQuery, Snowflake, Redshift)
- 웹 UI
- 스케줄링/캐시

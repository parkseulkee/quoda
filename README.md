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
# 버전 확인
uv run quada --version

# 프로젝트 초기화
uv run quada init --path ./my-project

# 설정 검증
uv run quada validate --path ./my-project

# 데이터 질의 (DB 연결 필요)
uv run quada ask "이탈 고객의 매출 보여줘" --path ./my-project

# 품질 검사 (DB 연결 필요)
uv run quada check --path ./my-project

# 설정 확인
uv run quada config --path ./my-project
```

## Project Structure

```
src/quada/
  core/       config, orchestrator
  semantic/   models, loader, matcher
  db/         connector, executor
  llm/        client, prompts
  quality/    rules, engine
  agents/     base, semantic_query, quality, interpret
  cli/        app, display
  viz/        charts
```

## Configuration

`quada init`으로 생성되는 `quada.yaml`에서 DB, LLM, semantic layer를 설정합니다.
환경변수는 `${VAR_NAME}` 형식으로 사용 가능합니다.

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

`models/`, `metrics/`, `glossary/`, `quality/` 디렉토리에 YAML 파일로 정의합니다.
예시는 `tests/fixtures/` 또는 `tutorial/` 참고.

## Tutorial

`tutorial/` 디렉토리에 SQLite 기반 샘플 프로젝트가 포함되어 있습니다.
고객 10명, 주문 25건의 소규모 데이터셋으로 전체 기능을 체험할 수 있습니다.

### 1. 셋업

```bash
uv sync
uv run python tutorial/setup_db.py
```

### 2. 설정 검증

```bash
uv run quada validate --path tutorial/
```

예상 출력:
```
✓ quada.yaml is valid
  Entities: 2
  Metrics: 1
  Glossary terms: 3
  Quality rules: 3
✓ Semantic layer is valid
```

### 3. 품질 검사

```bash
uv run quada check --path tutorial/
```

예상 출력:
```
  PASS orders_freshness: Data is fresh
  WARN orders_status_not_null: status null ratio 8.0% exceeds threshold 5.0%
  PASS orders_amount_range: amount values within range

Overall: WARN
```

orders 테이블에 status가 NULL인 행이 2건 있어 경고가 발생합니다.

### 4. 자연어 질의 (LLM API 키 필요)

```bash
export ANTHROPIC_API_KEY=sk-ant-...

uv run quada ask "이탈 고객의 매출 보여줘" --path tutorial/ --show-sql
uv run quada ask "신규 고객 수" --path tutorial/
uv run quada ask "이번달 총 매출" --path tutorial/ --skip-quality
```

### 샘플 데이터 요약

| 테이블 | 건수 | 비고 |
|--------|------|------|
| customers | 10 | 이탈 2명, 신규 4명, 활성 4명 |
| orders | 25 | completed 20, cancelled 1, pending 1, refunded 1, NULL status 2 |

### Semantic Layer 구성

- **models/**: `customers`, `orders` 엔티티 정의
- **metrics/**: `revenue` (완료 주문 매출 합계)
- **glossary/**: `이탈 고객`, `신규 고객`, `활성 고객` 비즈니스 용어
- **quality/**: freshness, null ratio, value range 규칙

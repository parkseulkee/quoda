# 📊 quada
> **Natural language data queries, with quality you can trust.**

quada는 "빠른 답변"과 "데이터 신뢰" 사이의 간극을 메웁니다. 단순한 SQL 생성을 넘어, 비즈니스 컨텍스트(Semantic Layer)를 이해하고 답변 전 데이터 품질(Quality Check)을 스스로 검증합니다.


## ✨ Key Features

* **Semantic Layer:** YAML로 비즈니스 용어(예: "이탈 고객")를 정의하여 LLM의 추측이 아닌 실제 정의를 바탕으로 쿼리합니다.
* **Quality-First:** 답변 전 데이터의 신선도(Freshness), NULL 비율, 값 범위를 자동 체크합니다.
* **Human-in-the-loop:** 모호한 질문이나 품질 이슈 발견 시 독단적으로 판단하지 않고 사용자에게 질문합니다.
* **Multi-model Routing:** 작업별로 최적의 LLM(Claude, GPT 등)을 다르게 배치하여 비용과 성능을 최적화합니다.
* **CLI-Native:** 터미널에서 즉시 실행하며, ASCII 차트로 시각화 결과를 제공합니다.


## 🛠 How It Works

quada는 **Multi-agent Pipeline**을 통해 동작하며, 각 단계는 독립적으로 자기 수정을 수행합니다.

1.  **Semantic Query:** 비즈니스 용어집에서 정의를 찾아 SQL 생성.
2.  **Quality Check:** 타겟 테이블의 데이터 품질 검증 (결함 발견 시 경고).
3.  **Execute:** SQL 실행 (Read-only 보장).
4.  **Interpret:** 결과를 자연어로 요약하고 차트 렌더링.


## 🚀 Quick Start

```bash
# 1. 설치 및 프로젝트 초기화
uv sync
uv run quada init --path ./my-project

# 2. 메타데이터 인덱스 빌드
uv run quada index --path ./my-project

# 3. 자연어로 질문하기
export ANTHROPIC_API_KEY=sk-ant-...
uv run quada ask "지난달 이탈 고객의 매출을 보여줘" --path ./my-project
```


## ⚙️ Configuration (`quada.yaml`)

각 에이전트별로 모델을 자유롭게 할당할 수 있습니다.

```yaml
llm:
  orchestrator: { provider: anthropic, model: claude-3-5-sonnet }
  agents:
    semantic_query: { provider: anthropic, model: claude-3-haiku } # 빠르고 저렴하게
    quality: { provider: openai, model: gpt-4o-mini }             # 효율적인 검증
    interpret: { provider: anthropic, model: claude-3-5-sonnet }  # 정교한 요약
```

## ✅ Quality Rules

`quality/rules.yaml`에 데이터 신뢰 규격 정의 시, 쿼리 전 자동으로 검사합니다.

| 유형 | 설명 | 주요 파라미터 |
| :--- | :--- | :--- |
| `freshness` | 데이터 최신성 확인 | `column`, `threshold` (예: "24 hours") |
| `null_ratio` | NULL 허용 범위 체크 | `column`, `threshold` (0.0~1.0) |
| `value_range` | 수치 데이터 범위 검증 | `column`, `min`, `max` |
| `unique` | 중복 데이터 존재 여부 | `column` |
| `custom_sql` | 사용자 정의 SQL 검증 | `query`, `threshold` |


## 💻 CLI Reference

| Command | Description |
| :--- | :--- |
| `quada init` | 새 프로젝트 템플릿 생성 |
| `quada index` | 시맨틱 레이어 기반 메타데이터 인덱싱 |
| `quada check` | 모든 품질 규칙(Quality Rules) 실행 및 보고 |
| `quada ask "<q>"` | 자연어 기반 데이터 질의 |
| `quada validate` | 설정 파일 및 시맨틱 정의 유효성 검사 |


## 🏗 Architecture

**LangGraph** 기반의 상태 머신 구조로 설계되어 유연한 워크플로우를 제공합니다.

* **Framework:** LangGraph, LiteLLM, SQLAlchemy, Pydantic
* **Interface:** Typer (CLI), Rich (Display), Plotext (Charts)


## 📖 Tutorial

SQLite 기반 샘플 프로젝트(고객 10명, 주문 25건)로 전체 기능을 체험할 수 있습니다.

→ **[튜토리얼 바로가기](tutorial/TUTORIAL.md)**

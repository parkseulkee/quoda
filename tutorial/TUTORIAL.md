# quada Tutorial

SQLite 기반 샘플 데이터셋으로 quada의 전체 기능을 단계별로 체험합니다.

---

## 샘플 데이터 구조

| 테이블 | 행 수 | 내용 |
| :--- | :--- | :--- |
| `customers` | 10 | 이탈 2명, 신규 4명, 활성 4명 |
| `orders` | 25 | completed 20, cancelled 1, pending 1, refunded 1, NULL status 2 |

### 비즈니스 용어 정의 (Glossary)

| 용어 | 정의 |
| :--- | :--- |
| 이탈 고객 | 최근 90일간 구매 이력이 없는 고객 |
| 신규 고객 | 최근 30일 이내 가입한 고객 |
| 활성 고객 | 최근 30일 이내 구매한 고객 |

### 시맨틱 레이어 구성

```
tutorial/
  models/
    customers.yaml   # customers 테이블 엔티티 정의
    orders.yaml      # orders 테이블 엔티티 정의
  metrics/
    revenue.yaml     # 완료 주문 매출 합계
  glossary/
    terms.yaml       # 이탈/신규/활성 고객 비즈니스 용어
  quality/
    rules.yaml       # freshness, null_ratio, value_range 규칙
```

---

## Step 1. 설치

```bash
uv sync
```

---

## Step 2. 샘플 DB 생성

```bash
uv run python tutorial/setup_db.py
```

```
DB 생성 완료: tutorial/tutorial.db
  customers: 10명 (이탈 2명, 신규 4명)
  orders: 25건 (completed 20, cancelled 1, pending 1, refunded 1, NULL 2)
```

---

## Step 3. 설정 검증

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

---

## Step 4. 메타데이터 인덱스 빌드

`quada ask` 실행 전 반드시 수행해야 합니다. 시맨틱 레이어를 읽어 `.quada/metadata_index.json`을 생성합니다.

```bash
uv run quada index --path tutorial/
```

예상 출력:
```
✓ metadata_index.json saved to tutorial/.quada
  Entities: 2
  Metrics:  1
  Glossary: 3
```

> 시맨틱 레이어(YAML)를 수정한 경우 반드시 재실행하세요.

---

## Step 5. 품질 검사

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

`orders` 테이블에 `status`가 NULL인 행이 2건 있어 경고가 발생합니다. `quada ask` 실행 시 이 경고를 확인하고 계속할지 물어봅니다.

---

## Step 6. 자연어 질의

LLM API 키가 필요합니다.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### 예시 1 — 이탈 고객 매출

```bash
uv run quada ask "이탈 고객의 매출을 보여줘" --path tutorial/
```

내부 동작:
1. `"이탈 고객"` → glossary에서 SQL 조건 조회: `last_purchase_date < datetime('now', '-90 days')`
2. `orders` 테이블 품질 검사 → WARN 발생 → 계속할지 확인
3. SQL 생성 및 실행
4. 결과 자연어 요약 + 차트 렌더링

### 예시 2 — 신규 고객 수

```bash
uv run quada ask "신규 고객이 몇 명이야?" --path tutorial/
```

### 예시 3 — 이번달 총 매출

```bash
uv run quada ask "이번달 총 매출" --path tutorial/
```

`revenue` 메트릭 정의(`status = 'completed'` 필터)를 참조해 SQL을 생성합니다.

---

## Human-in-the-loop 동작 확인

quada는 두 가지 상황에서 실행을 멈추고 사용자에게 질문합니다.

**1. 품질 경고 발생 시**
```
⚠ Quality warnings detected:
  - orders_status_not_null: WARN (null ratio 8.0%)

Continue anyway? [y/N]
```

**2. 용어를 찾지 못한 경우**
```
? Term not found: "휴면 고객"
  Please provide a definition or SQL condition:
```

직접 정의를 입력하면 해당 질의에 한해 사용됩니다. 자주 쓰는 용어는 `glossary/terms.yaml`에 추가하세요.

---

## 시맨틱 레이어 직접 수정해보기

### 새 용어 추가

`tutorial/glossary/terms.yaml`에 추가:

```yaml
  - term: "VIP 고객"
    definition: "총 구매액이 100,000원 이상인 고객"
    sql_condition: >
      customers.id IN (
        SELECT customer_id FROM orders
        WHERE status = 'completed'
        GROUP BY customer_id
        HAVING SUM(amount) >= 100000
      )
    entity: customer
    aliases:
      - "vip"
      - "고가치 고객"
```

인덱스를 재빌드한 후 질의:

```bash
uv run quada index --path tutorial/
uv run quada ask "VIP 고객의 주문 건수" --path tutorial/
```

### 새 품질 규칙 추가

`tutorial/quality/rules.yaml`에 추가:

```yaml
    - name: customers_email_unique
      type: unique
      table: customers
      column: email
```

```bash
uv run quada check --path tutorial/
```

---

## 설정 확인

현재 적용된 설정을 출력합니다.

```bash
uv run quada config --path tutorial/
```

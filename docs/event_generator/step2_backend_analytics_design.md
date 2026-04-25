# Step 2/3 backend analytics design

작성일: 2026-04-25  
브랜치: `fect/step2-event-storage-analytics`

## 1. 이번 브랜치의 목적

`fect/event-generator` 브랜치에서 이미 아래 흐름은 동작하도록 만들었다.

```text
event_generator --sink redis
  -> Redis Streams web.events.raw.v1
  -> FastAPI lifespan consumer
  -> PostgreSQL events table
```

이번 Step2 backend 브랜치에서는 과제의 “필드를 구분하여 저장” 요구사항을 README/API 수준에서 더 명확히 만들고, 바로 Step3 분석으로 이어질 수 있게 **generated view + 안전한 SQL 실행 API**를 추가한다.

## 2. 저장소 선택

최종 저장소는 PostgreSQL이다.

Redis Streams는 MQ/transport로만 사용한다. Redis Stream에 남은 payload는 raw event message이고, 분석 기준 데이터는 PostgreSQL `events` table이다.

PostgreSQL을 선택한 이유는 다음과 같다.

- event payload를 JSON blob 하나로 저장하지 않고 컬럼으로 분리할 수 있다.
- 이벤트 타입별, 유저별, 시간대별 집계를 SQL로 바로 표현할 수 있다.
- `event_id` primary key와 `ON CONFLICT DO NOTHING`으로 retry/중복 전달에 대응할 수 있다.
- Docker Compose에서 app + DB 구조를 과제 요구사항과 맞게 설명하기 쉽다.

## 3. base table schema

Alembic migration으로 `events` table을 만든다.

```sql
CREATE TABLE events (
  event_id TEXT PRIMARY KEY,
  schema_version TEXT NOT NULL,
  event_type TEXT NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL,
  user_id TEXT NOT NULL,
  traffic_phase TEXT NOT NULL,
  producer_id TEXT NOT NULL,
  page_path TEXT NULL,
  category_id TEXT NULL,
  product_id TEXT NULL,
  amount NUMERIC(12, 2) NULL,
  currency TEXT NULL,
  error_code TEXT NULL,
  error_message TEXT NULL,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Indexes:

```sql
CREATE INDEX idx_events_occurred_at ON events (occurred_at);
CREATE INDEX idx_events_event_type ON events (event_type);
CREATE INDEX idx_events_user_id ON events (user_id);
CREATE INDEX idx_events_product_id ON events (product_id);
```

## 4. generated views

SQL UI가 raw `events` table을 직접 보게 하지 않고, allowlist에 등록된 generated view만 조회하도록 했다.

현재 view 목록:

| view | 목적 |
|---|---|
| `event_type_counts` | 이벤트 타입별 발생 횟수 |
| `user_event_counts` | 유저별 총 이벤트 수 |
| `hourly_event_counts` | 시간대 + 이벤트 타입별 추이 |
| `error_event_ratio` | 전체 이벤트 중 checkout_error 비율 |
| `commerce_funnel_counts` | page_view → purchase/error funnel 단계별 count |
| `product_event_counts` | 상품별 이벤트 count |

이렇게 나눈 이유는 프론트 SQL editor에서 “직접 테이블 선택” 느낌은 주되, raw table 전체를 열어두는 위험은 줄이기 위해서다.

## 5. SQL execution policy

Manual SQL endpoint는 아래 정책을 서버에서 강제한다.

핵심 전제는 이 기능이 **ORM/Query Builder 기반 안전 쿼리 생성기**가 아니라는 점이다.
사용자가 입력한 SQL 문자열을 `sqlglot`으로 검증한 뒤 SQLAlchemy `text()`로 실행하므로,
보안은 SQLAlchemy 자체가 아니라 **allowlist 정책 + DB runtime guardrail**에 달려 있다.

- PostgreSQL dialect로 parse 가능한 SQL만 허용한다.
- parser-side DoS를 줄이기 위해 SQL text는 4,000자 이하만 허용한다.
- 한 번에 statement 하나만 허용한다.
- root statement는 `SELECT`만 허용한다.
- `WITH x AS (DELETE ...) SELECT ...` 같은 data-modifying CTE를 거부한다.
- read-only CTE, subquery, join, `WHERE`, `GROUP BY`, `ORDER BY`, `DISTINCT`,
  `OFFSET`은 허용한다. Superset SQL Lab처럼 생 SQL을 쓰되, 참조 relation을
  generated view allowlist 안에 가둔다.
- 함수는 좁은 allowlist만 허용한다. 현재 허용 함수는 `COUNT`, `SUM`, `AVG`,
  `MIN`, `MAX`, `ROUND`, `DATE_TRUNC` 계열이다.
- `pg_sleep`, `pg_advisory_lock`, `set_config`, `version`, `generate_series`처럼
  allowlist 밖의 함수는 거부한다.
- `SELECT INTO`를 거부한다.
- `FOR UPDATE` 같은 locking read를 거부한다.
- `TABLESAMPLE`은 현재 SQL Lab 목적과 맞지 않아 거부한다.
- `information_schema`, `pg_catalog` 같은 system catalog/schema relation을 거부한다.
- schema/catalog qualified relation을 거부한다. 예: `public.event_type_counts`
- relation은 generated view allowlist에 있어야 한다.
- raw `events` table은 manual SQL에서 거부한다.
- 결과 row는 최대 500개로 cap한다.
- repository 실행 시 outer query로 한 번 더 `LIMIT :row_limit`을 적용한다.
- PostgreSQL transaction은 `SET TRANSACTION READ ONLY`로 실행한다.
- PostgreSQL `search_path`는 `public, pg_catalog`로 고정한다.
- PostgreSQL transaction 안에서 `SET LOCAL statement_timeout`, `lock_timeout`,
  `idle_in_transaction_session_timeout`을 적용한다.
- accepted/rejected/completed SQL Lab 실행은 raw SQL 전문 대신 SHA-256 hash,
  relation, row count, rejection reason 중심으로 audit log를 남긴다.

허용 예시는 아래처럼 **allowlisted generated view를 대상으로 column 선택,
filter, join, group, order, limit을 수행하는 형태**다.

```sql
SELECT event_type, event_count
FROM event_type_counts
WHERE event_count > 0
ORDER BY event_count DESC, event_type
LIMIT 20;

SELECT e.event_type, SUM(p.event_count) AS product_events
FROM event_type_counts AS e
JOIN product_event_counts AS p
  ON e.event_type = p.event_type
GROUP BY e.event_type
ORDER BY product_events DESC;

WITH high_events AS (
  SELECT event_type, event_count
  FROM event_type_counts
  WHERE event_count > (
    SELECT AVG(event_count)
    FROM event_type_counts
  )
)
SELECT event_type, event_count
FROM high_events
ORDER BY event_count DESC;
```

거부 예시는 아래와 같다.

```sql
SELECT pg_sleep(10), event_count FROM event_type_counts;
SELECT version() FROM event_type_counts;
SELECT * FROM information_schema.tables;
SELECT * FROM pg_catalog.pg_user;
SELECT * INTO temp_event_counts FROM event_type_counts;
SELECT * FROM event_type_counts FOR UPDATE;
SELECT * FROM event_type_counts TABLESAMPLE SYSTEM (100);
SELECT * FROM events;
```

### 5.1 보안 판단 기준과 남은 한계

- SQLAlchemy `text()`는 bind parameter를 지원하지만, SQL 문자열 자체를 안전하게
  만들어주지는 않는다. 현재 코드에서 bind parameter로 안전한 것은 outer
  `row_limit` 값이다.
- OWASP 기준으로 구조적 SQL 요소(table/column/order 등)를 사용자 입력으로 받을 때는
  allowlist 또는 query redesign이 필요하다. 그래서 raw `events`가 아니라 generated
  view allowlist만 노출한다.
- `SET TRANSACTION READ ONLY`는 DML/DDL을 줄이는 방어선이지만, read-only 함수 호출,
  무거운 join/subquery, catalog 조회 같은 위험을 전부 막지는 못한다. 그래서
  validator에서 system catalog와 위험 함수 surface를 차단하고 timeout을 적용한다.
- production 수준으로 끌어올릴 경우 dedicated read-only DB role, schema 권한 분리,
  statement cost 제한, 사용자별 query cancel endpoint를 추가로 검토해야 한다.
- Explore 화면은 raw SQL 문자열 조립 대신 `/analytics/explore-query` structured API를
  사용한다. 이 endpoint는 dataset/columns/order/limit만 입력으로 받고, backend에서
  SQLAlchemy Core `select()`로 SQL을 생성한다. SQL Lab의 manual SQL 경로는 고급 확인용으로
  남겨두되, 기본 chart 생성은 structured endpoint를 우선 사용한다.

### 5.2 다른 DB 지원 가능성

현재 구현은 PostgreSQL을 1차 지원 대상으로 고정한다. 다만 구조적으로는 두 층에서 확장 가능성이 있다.

- Chart Builder: raw SQL이 아니라 `dataset`, `columns`, `order_by`, `row_limit` 같은 structured contract를 받으므로 DB별 repository adapter로 옮기기 쉽다.
- SQL Lab: `sqlglot` AST validation을 사용하므로 dialect parameter를 바꿀 수는 있지만, DB별 function/catalog/identifier/timeout/read-only 정책을 다시 검증해야 한다.

따라서 multi DB는 “DB URL만 바꾸는 기능”이 아니라 아래 adapter 책임을 분리해야 가능한 기능이다.

```text
AnalyticsDatabaseDialect
  - sqlglot read dialect
  - SQLAlchemy driver URL policy
  - generated relation allowlist
  - runtime read-only guard SQL
  - statement/lock timeout strategy
  - health check SQL
  - value serialization policy
```

과제 v1에서는 이 추상화를 코드에 넣지 않는다. 실제 지원 DB가 PostgreSQL 하나뿐인 상태에서 adapter 계층을 먼저 만들면 범위가 과해지고, 검증 matrix도 불필요하게 커진다. 대신 확장 검토는 `docs/event_generator/database_support_extension.md`에 별도 문서로 남긴다.

## 6. Backend API

```text
GET  /analytics/datasets
GET  /analytics/presets
POST /analytics/query
POST /analytics/explore-query
```

### `GET /analytics/datasets`

프론트의 dataset/view selector에 보여줄 allowlisted generated views를 반환한다.

각 dataset은 Superset-style Explore control이 사용할 수 있도록 column metadata도 함께
반환한다.

```json
{
  "name": "event_type_counts",
  "label": "Event type counts",
  "description": "이벤트 타입별 발생 횟수를 집계한 generated view입니다.",
  "columns": [
    {"name": "event_type", "label": "Event type", "kind": "dimension"},
    {"name": "event_count", "label": "Event count", "kind": "metric"}
  ]
}
```

`kind`는 frontend가 기본 projection과 chart control을 잡기 위한 semantic hint다.

| kind | 의미 |
|---|---|
| `dimension` | category / label 축 후보 |
| `metric` | numeric measure / sort 후보 |
| `temporal` | time-series x-axis 후보 |

### `GET /analytics/presets`

과제 Step3 예시와 커머스 funnel에 바로 연결되는 preset SQL을 반환한다.

현재 preset:

- commerce funnel
- event type counts
- hourly event trend
- top users
- checkout error ratio

### `POST /analytics/query`

요청:

```json
{
  "sql": "SELECT event_type, event_count FROM event_type_counts",
  "row_limit": 500
}
```

응답:

```json
{
  "columns": ["event_type", "event_count"],
  "rows": [{"event_type": "page_view", "event_count": 10}],
  "chart": {
    "chart_kind": "bar",
    "x_axis": "event_type",
    "y_axis": "event_count",
    "series_axis": null
  }
}
```

정책 위반 응답:

```json
{
  "error_code": "sql_policy_violation",
  "message": "analytics SQL은 SELECT 문만 허용합니다.",
  "rejected_reason": "non_select_statement"
}
```

### `POST /analytics/explore-query`

Superset-style Explore control에서 선택한 dataset/columns/order/limit을 실행한다.
사용자 SQL 문자열을 받지 않고, backend가 catalog allowlist를 검증한 뒤 SQLAlchemy Core로
SELECT statement를 생성한다.

요청:

```json
{
  "dataset": "event_type_counts",
  "columns": ["event_type", "event_count"],
  "order_by": "event_count",
  "order_direction": "desc",
  "row_limit": 100
}
```

응답 shape는 `/analytics/query`와 동일하다.

정책:

- dataset은 `/analytics/datasets`에 노출된 generated view만 허용한다.
- columns와 order_by는 해당 dataset의 column metadata에 있는 이름만 허용한다.
- 중복 column은 거부한다.
- row_limit은 최대 500개로 cap한다.
- repository는 manual SQL과 동일하게 PostgreSQL read-only transaction / timeout guard를 적용한다.

## 7. Frontend 연결 의도

frontend는 이 API만 바라본다.

- `/analytics/datasets`로 table/view selector와 Explore column controls 구성
- `/analytics/presets`로 preset 버튼 구성
- `/analytics/explore-query`로 Explore control 기반 chart/table 실행
- `/analytics/query`로 SQL Lab 입력 결과 table 확인

Superset처럼 복잡한 dashboard 저장/권한/drag-and-drop builder까지 만들지는 않는다. 대신
Superset의 핵심 사용감인 “dataset 선택 → chart control 조정 → 결과/차트 확인” 흐름을
가볍게 구현해 과제의 핵심인 SQL 집계 결과 확인과 시각화에 집중한다.

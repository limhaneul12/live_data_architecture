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

- PostgreSQL dialect로 parse 가능한 SQL만 허용한다.
- 한 번에 statement 하나만 허용한다.
- root statement는 `SELECT`만 허용한다.
- `WITH x AS (DELETE ...) SELECT ...` 같은 data-modifying CTE를 거부한다.
- schema/catalog qualified relation을 거부한다. 예: `public.event_type_counts`
- relation은 generated view allowlist에 있어야 한다.
- raw `events` table은 manual SQL에서 거부한다.
- 결과 row는 최대 500개로 cap한다.
- repository 실행 시 outer query로 한 번 더 `LIMIT :row_limit`을 적용한다.
- PostgreSQL transaction은 `SET TRANSACTION READ ONLY`로 실행한다.

## 6. Backend API

```text
GET  /analytics/datasets
GET  /analytics/presets
POST /analytics/query
```

### `GET /analytics/datasets`

프론트의 dataset/view selector에 보여줄 allowlisted generated views를 반환한다.

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

## 7. Frontend 연결 의도

다음 frontend branch는 이 API만 바라보면 된다.

- `/analytics/datasets`로 table/view selector 구성
- `/analytics/presets`로 preset 버튼 구성
- `/analytics/query`로 SQL 실행 결과/차트 preview 구성

Superset처럼 복잡한 dashboard builder를 만들기보다, 과제의 핵심인 SQL 집계 결과 확인과 간단한 시각화에 집중한다.

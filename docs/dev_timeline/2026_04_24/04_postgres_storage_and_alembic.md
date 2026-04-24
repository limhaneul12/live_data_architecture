# 04. PostgreSQL 저장소와 Alembic migration

## 무엇을 했는지

과제 Step 2 요구사항에 맞춰 Redis Stream에서 읽은 이벤트를 PostgreSQL `events` table에 필드별 컬럼으로 저장하도록 구현했습니다.

추가한 주요 구성은 아래와 같습니다.

```text
backend/app/event_analytics/
  domain/events.py
  domain/repositories/event_repository.py
  application/ingest_events_usecase.py
  infrastructure/repositories/postgres_event_repository.py
  infrastructure/streams/redis_client_factory.py
  infrastructure/streams/redis_stream_consumer.py
  interface/schemas.py
  interface/consumer_lifespan.py
```

DB schema는 runtime `CREATE TABLE`이 아니라 Alembic migration으로 관리합니다.

```text
backend/alembic.ini
backend/alembic/env.py
backend/alembic/versions/20260424_0001_create_events_table.py
```

## 개발 규칙 반영

backend architecture rule에 맞춰 아래 원칙을 적용했습니다.

- bounded context 이름은 `event_analytics`
- 계층은 `domain / application / infrastructure / interface`
- 내부 모델은 dataclass
- Redis payload boundary는 Pydantic schema
- repository port는 `ABC` 사용, `Protocol` 사용 금지
- DB 저장은 SQLAlchemy ORM mapped table 사용
- 한 건씩 insert하지 않고 batch insert
- 중복 `event_id`는 `ON CONFLICT (event_id) DO NOTHING`
- migration은 Alembic으로 관리

## 스키마 요약

최종 저장소는 PostgreSQL이고 Redis Streams는 transport layer입니다.
`events` table은 raw JSON을 통째로 넣지 않고 아래 컬럼으로 분리합니다.

```text
event_id PK
schema_version
event_type
occurred_at
user_id
traffic_phase
producer_id
page_path
category_id
product_id
amount
currency
error_code
error_message
ingested_at
```

분석 쿼리를 고려해 `occurred_at`, `event_type`, `user_id`, `product_id` index를 추가했습니다.

## 현재 기준

- 최종 저장소: PostgreSQL
- transport: Redis Streams
- DB 적재: SQLAlchemy ORM repository batch insert
- schema 변경: Alembic migration
- idempotency: `event_id` primary key + conflict ignore
- 관련 문서: `docs/event_generator/step2_log_storage_plan.md`

# Step 2 plan — log storage

작성일: 2026-04-25
범위: 과제 Step 2 — 생성한 이벤트 로그 저장

## 1. 과제 요구사항

Step 2 요구사항은 아래다.

```text
생성한 이벤트를 본인이 적합하다고 생각하는 저장소에 자유롭게 저장하세요.

요구사항:
- 단순히 JSON을 통째로 저장하지 말고, 필드를 구분하여 저장
- 사용한 저장소의 스키마 또는 데이터 구조를 README에 포함
- README에 해당 저장소를 선택한 이유를 반드시 작성
```

## 2. 저장소 선택

선택 저장소:

```text
PostgreSQL
```

Redis Streams는 저장소가 아니라 MQ/transport layer로 둔다.

```text
event_generator
  -> Redis Streams
  -> FastAPI lifespan consumer
  -> PostgreSQL events table
```

## 3. PostgreSQL을 선택하는 이유

PostgreSQL을 선택하는 이유는 과제 요구사항과 이후 Step 3/Step 5가 자연스럽게
이어지기 때문이다.

- 이벤트를 JSON 통째로 저장하지 않고 컬럼으로 분리 저장하기 쉽다.
- SQL 집계 분석을 바로 수행할 수 있다.
- `event_id` primary key로 중복 저장을 막을 수 있다.
- 시간대별, 이벤트 타입별, 유저별, 상품별 index를 추가하기 쉽다.
- Docker Compose에서 app + DB 구성이 명확하다.

Redis Streams는 이벤트를 잠시 전달하고 consumer group/ack를 보여주는 역할이다.
최종 분석 기준 데이터는 PostgreSQL `events` table이다.

## 4. 저장 스키마

현재 계획하는 table은 `events`다.

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

스키마는 Alembic migration으로 관리한다.

```text
backend/alembic/versions/20260424_0001_create_events_table.py
```

## 5. 저장 방식

저장 흐름:

1. event generator가 `web_event.v1` payload를 생성한다.
2. `--sink redis` 모드에서는 Redis Stream `web.events.raw.v1`에 publish한다.
3. FastAPI lifespan background consumer가 Redis Stream을 batch로 읽는다.
4. Pydantic boundary schema로 payload를 검증한다.
5. 내부에서는 dataclass `WebEvent`로 다룬다.
6. SQLAlchemy ORM repository가 PostgreSQL에 batch insert한다.
7. DB commit 성공 후 Redis message를 ack한다.

중요한 정책:

- 한 건씩 DB insert하지 않고 batch insert한다.
- `event_id` 중복은 `ON CONFLICT (event_id) DO NOTHING`으로 무시한다.
- DB 저장 실패 시 valid message는 ack하지 않는다.
- invalid payload는 현재 v1에서 ack 후 drop한다.

## 6. 구현 위치

Backend bounded context:

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

Config:

```text
backend/app/platform/config/stream_config.py
backend/app/platform/config/app_config.py
```

Docker:

```text
docker-compose.yml
backend/Dockerfile
```

## 7. README에 추가해야 할 내용

Step 2 완료 전 README에는 아래를 명확히 넣는다.

1. 저장소 선택: PostgreSQL
2. 선택 이유
3. Redis Streams는 MQ이고 최종 저장소가 아니라는 점
4. `events` table schema
5. JSON 통째 저장이 아니라 필드별 컬럼 저장이라는 점
6. 실행 방법
7. 간단한 확인 쿼리

예상 확인 쿼리:

```sql
SELECT count(*) FROM events;

SELECT event_type, count(*)
FROM events
GROUP BY event_type
ORDER BY event_type;
```

## 8. Acceptance criteria

Step 2 완료 조건:

- `docker compose up` 후 app, Redis, PostgreSQL이 같이 실행된다.
- event generator가 Redis Stream에 event payload를 publish한다.
- backend consumer가 Redis Stream에서 batch read한다.
- PostgreSQL `events` table이 Alembic migration으로 생성된다.
- 이벤트가 JSON blob이 아니라 컬럼별로 저장된다.
- `event_id` primary key로 중복 저장을 방지한다.
- DB 저장 성공 후 Redis message를 ack한다.
- `/health/ready`에서 app, Redis, database가 `ok`로 보인다.
- README에 저장소 선택 이유와 schema가 정리된다.

## 9. Verification plan

Unit/behavior tests:

```text
backend/tests/event_analytics/test_web_event_validation.py
backend/tests/event_analytics/test_ingest_events_usecase.py
backend/tests/event_analytics/test_postgres_event_repository.py
backend/tests/event_analytics/test_redis_stream_consumer.py
backend/tests/event_analytics/test_event_stream_ingestion_loop.py
backend/tests/event_analytics/test_alembic_migration.py
```

Quality gate:

```bash
make ci
```

E2E smoke:

```bash
APP_PORT=18000 POSTGRES_PORT=15432 REDIS_PORT=16379 \
  docker compose -p lda_e2e up -d db redis app

curl -sS http://localhost:18000/health/ready

APP_PORT=18000 POSTGRES_PORT=15432 REDIS_PORT=16379 \
  docker compose -p lda_e2e run --rm event-generator \
  .venv/bin/python -m event_generator \
  --sink redis --producer-id producer_e2e \
  --max-events 10 --seed 20260425 --no-sleep

docker exec lda-redis redis-cli XLEN web.events.raw.v1
docker exec lda-redis redis-cli XPENDING web.events.raw.v1 event_analytics_writer
docker exec lda-db psql -U live_data -d live_data -tAc "SELECT count(*) FROM events;"
```

기대 결과:

```text
/health/ready -> app/redis/database 모두 ok
Redis XLEN -> 생성한 이벤트 수
Redis XPENDING -> 0
PostgreSQL count(*) -> 생성한 이벤트 수
```

## 10. Redis Stream consumer 안전 정책

2026-04-25 Codex CLI review에서 Redis consumer의 data-loss 가능성을 점검했고,
Step 2 v1 범위 안에서 아래 정책은 구현 대상으로 올렸다.

- consumer group은 `0-0`부터 생성한다. producer가 app보다 먼저 Redis에 이벤트를
  썼더라도 group 생성 전 이벤트를 건너뛰지 않기 위해서다.
- read는 같은 consumer의 pending entry를 먼저 확인한 뒤, pending이 없을 때만
  `>`로 새 이벤트를 읽는다. DB 장애 때문에 ack하지 못한 이벤트가 다음 poll에서
  다시 저장 시도되도록 하기 위해서다.
- `payload`가 malformed JSON이거나 UTF-8 decode에 실패하면 invalid payload로
  분류하고, 기존 invalid 처리 흐름처럼 ack/drop한다. 한 건의 잘못된 메시지가
  background consumer task를 종료시키지 않기 위해서다.

## 11. Step 2에서 아직 하지 않을 것

아래는 운영 확장 후보로 남긴다.

- 다른 consumer가 소유한 stale pending reclaim (`XAUTOCLAIM`)
- poison message quarantine
- DLQ stream
- redrive tooling
- multi-consumer scale-out strategy
- event storage partitioning
- retention policy

이 항목들은 중요하지만 Step 2의 핵심인 “필드별 저장소 적재”보다 뒤에 두는 것이
범위를 단단하게 유지하는 데 유리하다.

## 11. 다음 단계

Step 2 계획 기준 다음 작업 순서:

1. README에 Step 2 저장소 선택 이유와 schema를 보강한다.
2. 현재 구현과 계획의 차이를 점검한다.
3. Docker Compose E2E를 다시 실행해 Redis publish와 DB 적재를 확인한다.
4. 결과를 `docs/event_generator/step2_log_storage_result.md`로 정리한다.
5. Step 3 SQL 집계 분석 계획으로 넘어간다.

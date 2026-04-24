# Redis Streams pipeline implementation plan

작성일: 2026-04-24
브랜치: `fect/event-generator`
범위: event generator Redis publish + FastAPI/backend 내부 consumer + PostgreSQL batch 저장

## 1. 구현 의도

이번 단계의 목적은 Step 1에서 만든 `web_event.v1` JSON payload를 실제 MQ에 흘려보내고, backend가 이를 batch로 읽어 PostgreSQL에 필드별 컬럼으로 저장하는 것이다.

최종 목표 흐름은 아래다.

```text
event_generator
  -> Redis Streams (`web.events.raw.v1`)
  -> FastAPI/backend lifecycle consumer
  -> event_analytics application service
  -> PostgreSQL batch insert
```

중요한 점은 consumer가 HTTP route를 다시 호출하지 않는다는 것이다. consumer는 backend 코드베이스 안에서 FastAPI가 사용하는 service/repository 로직을 직접 호출한다.

## 2. 개발 규칙 반영

이번 구현은 아래 규칙을 따른다.

- backend feature logic은 `backend/app/` 루트에 직접 두지 않고 bounded context로 둔다.
- 새 bounded context 이름은 `event_analytics`로 한다.
- backend 계층은 `domain / application / infrastructure / interface`로 나눈다.
- repository contract는 `domain/repositories/`, 구현체는 `infrastructure/repositories/`에 둔다.
- domain/application 내부 모델은 dataclass를 사용하고, Redis message IO boundary validation은 Pydantic schema에서 수행한다.
- repository port는 ABC로 표현하고, 사용자가 금지한 `Protocol`은 사용하지 않는다.
- Redis Stream adapter와 PostgreSQL repository는 infrastructure side effect 소유가 드러나는 이름을 사용한다.
- 테스트는 `backend/tests/event_analytics/` 아래에 둔다.
- 신규 infrastructure adapter는 success/failure behavior test를 둔다.
- 완료 전 `make ci`를 실행한다.

## 3. 참고 Redis Stream runtime

사용자가 제공한 참고 경로:

```text
/Users/imhaneul/Documents/sky_document/project/trandai-informat-fommo/backend/app/shared/infrastructure/stream_runtime
```

여기서 참고할 개념:

- Redis Stream entry의 `payload` field에 JSON payload를 encode하는 방식
- `XADD` publish abstraction
- `XGROUP CREATE ... MKSTREAM` consumer group bootstrap
- `XREADGROUP COUNT/BLOCK` batch read
- `XACK` ack
- `batch_size`, `block_ms` 설정
- `event_id` 기반 idempotency 관점
- single/cluster Redis mode 구분

v1에서 의도적으로 가져오지 않는 것:

- DLQ
- quarantine
- redrive
- stale pending reclaim
- Redis Cluster 전용 runtime 전체 구조
- 복잡한 observer/metric surface

이 프로젝트에서는 과제 범위에 맞게 작은 Redis Stream adapter를 새로 작성한다.

## 4. 선택 결정

### 4.1 MQ

선택:

```text
Redis Streams
```

이유:

- Docker Compose에 붙이기 쉽다.
- consumer group, pending, ack 개념을 보여줄 수 있다.
- `COUNT` 기반 batch read가 가능하다.
- Kafka/Kafka Connect보다 과제 범위를 덜 키운다.
- RabbitMQ Streams보다 현재 프로젝트에서 설명/구현 비용이 낮다.

### 4.2 Consumer 실행 위치

선택:

```text
FastAPI/backend 코드베이스 내부 lifespan background consumer
```

이유:

- 사용자가 지적한 것처럼 저장 로직은 결국 FastAPI/backend가 사용하는 DB/service/repository 로직을 탄다.
- 별도 worker service를 먼저 만들면 “같은 DB를 쓰는데 왜 분리하나”라는 설명 비용이 생긴다.
- 과제 v1에서는 app service 하나에서 API lifecycle과 consumer lifecycle을 같이 보여주는 편이 직관적이다.

주의:

- 운영형 확장에서는 consumer를 같은 backend image의 별도 command로 분리할 수 있다.
- v1에서는 `SERVICE_EVENT_CONSUMER_ENABLED=true`일 때만 lifespan에서 background task를 시작한다.
- Docker 실행에서는 uvicorn worker를 1개로 둔다.

### 4.3 DB 저장 방식

선택:

```text
Redis batch read -> PostgreSQL batch insert -> commit 성공 후 XACK
```

금지:

```python
for event in events:
    insert_one(event)
```

v1 batch 기본값:

```text
read_count = 100
block_ms = 1000
```

DB 저장은 SQLAlchemy ORM mapped table을 사용하고, PostgreSQL dialect의 `INSERT ... ON CONFLICT (event_id) DO NOTHING`을 batch statement로 실행한다.
테이블 생성은 runtime `CREATE TABLE`이 아니라 Alembic migration으로 관리한다.

## 5. 구현 파일 계획

### 5.1 event_generator

```text
event_generator/
  sinks.py                 # stdout/redis sink abstraction
  constants.py             # stream key/maxlen과 Redis env 이름 상수
  cli.py                   # --sink 옵션만 노출
```

CLI 방향:

```bash
python -m event_generator --sink stdout
STREAM_REDIS_URL=redis://redis:6379/0 python -m event_generator --sink redis
```

Redis publish 형태:

```text
XADD web.events.raw.v1 * payload '<web_event.v1 JSON>'
```

### 5.2 backend bounded context

```text
backend/app/event_analytics/
  __init__.py
  domain/
    __init__.py
    events.py
    repositories/
      __init__.py
      event_repository.py
  application/
    __init__.py
    ingest_events_usecase.py
  infrastructure/
    __init__.py
    repositories/
      __init__.py
      postgres_event_repository.py
    streams/
      __init__.py
      redis_client_factory.py
      redis_stream_consumer.py
  interface/
    __init__.py
    consumer_lifespan.py
```

역할:

- `domain/events.py`: 내부 dataclass event model.
- `domain/repositories/event_repository.py`: batch 저장 port.
- `application/ingest_events_usecase.py`: payload validation 후 repository에 batch 저장.
- `infrastructure/repositories/postgres_event_repository.py`: SQLAlchemy ORM table mapping + batch insert.
- `infrastructure/streams/redis_client_factory.py`: single/cluster Redis async client 생성.
- `infrastructure/streams/redis_stream_consumer.py`: Redis Streams batch read/ack adapter.
- `interface/consumer_lifespan.py`: FastAPI lifespan에서 background consumer task 시작/종료.

### 5.3 Alembic

```text
backend/alembic.ini
backend/alembic/env.py
backend/alembic/versions/20260424_0001_create_events_table.py
```

Docker image는 app 시작 전 `alembic upgrade head`를 실행해서 `events` table과 indexes를 생성한다.

### 5.4 config

추가 설정:

```text
SERVICE_EVENT_CONSUMER_ENABLED=false
STREAM_REDIS_URL=redis://localhost:6379/0
STREAM_REDIS_MODE=single
STREAM_BATCH_SIZE=100
STREAM_BLOCK_MS=1000
```

`SERVICE_EVENT_CONSUMER_ENABLED`는 app 설정에 둔다. Stream key, consumer group, consumer name은 배포 변수가 아니라 event analytics 계약 상수로 둔다. `StreamConfig`는 Redis URL, Redis mode, batch size, block ms만 읽는다.
`STREAM_REDIS_URL`은 single mode에서는 하나의 URL, cluster mode에서는 콤마로 구분된 startup node URL 목록이다.

### 5.5 health / drain

`/health/ready`와 `/health/heartbeat`에는 Redis와 PostgreSQL dependency status를 포함한다.

```json
{
  "status": "ok",
  "checks": {"app": "ok", "redis": "ok", "database": "ok"},
  "reason": null
}
```

consumer가 비활성화된 기본 로컬 실행은 `redis=disabled`, `database=disabled`로 표시한다. consumer가 활성화된 Docker Compose 실행은 Redis `PING`, consumer group 생성, PostgreSQL `SELECT 1`이 성공해야 dependency status가 `ok`가 된다. app drain 전환 시 Redis와 database status도 `draining`으로 같이 표시한다.

## 6. PostgreSQL table contract

```sql
CREATE TABLE IF NOT EXISTS events (
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

CREATE INDEX IF NOT EXISTS idx_events_occurred_at ON events (occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_user_id ON events (user_id);
CREATE INDEX IF NOT EXISTS idx_events_product_id ON events (product_id);
```

`event_id`는 application-level idempotency key다. Redis message가 재전달되어도 `ON CONFLICT (event_id) DO NOTHING`으로 중복 저장을 막는다.

## 7. 실패/ack 정책

v1 정책:

1. Redis에서 batch read.
2. payload decode/validation.
3. invalid payload는 v1에서는 ack하고 drop한다.
4. valid payload만 DB transaction으로 batch insert.
5. DB commit 성공 후 해당 Redis message id를 ack한다.
6. DB 저장 실패 시 ack하지 않는다.
7. consumer group은 `0-0`부터 생성해서 app 시작 전 stream에 쌓인 이벤트도 읽는다.
8. 다음 poll에서는 같은 consumer의 pending entry를 먼저 읽고, pending이 없을 때만
   `>`로 새 이벤트를 읽는다. transient DB 실패 뒤 ack되지 않은 message를 재시도하기 위해서다.
9. malformed JSON/UTF-8 payload는 invalid payload로 분류해서 consumer task가
   죽지 않도록 한다.

v2 후보:

- DLQ stream
- 다른 consumer가 소유한 stale pending reclaim (`XAUTOCLAIM`)
- poison message quarantine
- 별도 worker process scale-out

## 8. 테스트 계획

테스트 위치:

```text
backend/tests/event_analytics/
event_generator/tests/
```

테스트 항목:

- producer Redis sink가 `payload` field에 JSON을 publish한다.
- event domain validation이 `schema_version=web_event.v1`만 허용한다.
- application usecase가 valid payload만 repository batch save로 넘긴다.
- PostgreSQL repository가 batch insert SQL을 한 번에 실행하고 duplicate는 conflict ignore한다.
- Redis consumer가 DB 성공 후 ack한다.
- Redis consumer가 DB 실패 시 ack하지 않는다.
- FastAPI app은 설정이 꺼져 있으면 consumer를 시작하지 않는다.
- Redis health status가 ready/heartbeat 응답에 포함된다.
- 실제 Docker Compose e2e에서 Redis stream publish와 PostgreSQL 적재를 확인한다.

## 9. 수용 기준

완료 조건:

- `python -m event_generator --sink stdout --max-events 3 --no-sleep`가 기존처럼 동작한다.
- Redis sink 옵션이 추가된다.
- backend app에서 consumer enabled일 때 Redis Stream batch를 읽어 DB batch insert usecase로 전달하는 코드가 있다.
- DB 저장은 한 건씩 insert하지 않고 batch insert로 구현한다.
- DB schema는 Alembic migration으로 생성한다.
- `event_id` unique conflict를 무시한다.
- consumer ack는 DB 저장 성공 이후에만 수행한다.
- Redis single/cluster client factory가 있고 URL/mode/batch/block만 env로 조정한다.
- `/health/ready`와 `/health/heartbeat`에서 Redis status가 보인다.
- 관련 behavior test가 있다.
- Docker Compose e2e로 Redis XADD/XREADGROUP/DB insert 동작을 검증한다.
- `make ci`가 통과한다.

## 10. 구현 순서

1. 문서 저장.
2. TDD: producer Redis sink 테스트 추가.
3. producer sink 구현.
4. TDD: event_analytics domain/application/repository/consumer tests 추가.
5. backend bounded context 구현.
6. FastAPI lifespan wiring 추가.
7. docker-compose에 Redis 추가, app 환경값 보정.
8. sample 실행과 `make ci` 검증.

## 11. E2E 검증 기록

2026-04-25에 Docker Compose로 실제 Redis publish와 PostgreSQL 적재를 다시 검증했다.

검증은 기존 로컬 5432 포트 충돌을 피하기 위해 override port를 사용했다.

```bash
APP_PORT=18000 POSTGRES_PORT=15432 REDIS_PORT=16379 \
  docker compose -p lda_e2e up -d db redis app

curl -sS http://localhost:18000/health/ready

APP_PORT=18000 POSTGRES_PORT=15432 REDIS_PORT=16379 \
  docker compose -p lda_e2e run --rm event-generator \
  .venv/bin/python -m event_generator \
  --sink redis --producer-id producer_e2e \
  --max-events 10 --seed 20260425 --no-sleep
```

확인 결과:

```text
/health/ready -> {"status":"ok","checks":{"app":"ok","redis":"ok","database":"ok"},"reason":null}
/health/heartbeat -> {"heartbeat":{"app":"ok","redis":"ok","database":"ok",...}}
Redis XLEN web.events.raw.v1 -> 10
Redis XPENDING web.events.raw.v1 event_analytics_writer -> 0
PostgreSQL SELECT count(*) FROM events -> 10
```

즉 event generator가 Redis Stream에 10건을 publish했고, FastAPI lifespan consumer가 같은 10건을 PostgreSQL `events` table에 batch 저장한 뒤 ack까지 완료했다. readiness/heartbeat는 Redis `PING`과 PostgreSQL `SELECT 1` probe 결과를 함께 반영했다.

# live_data_architecture

## 스키마 설명

이번 단계에서 먼저 정리한 것은 데이터베이스 스키마가 아니라 **로깅 스키마와 health 응답 스키마**입니다.
이렇게 한 이유는 애플리케이션의 모든 모듈에서 **같은 JSON logging format**을 사용하게 만들고, 로그를 사람이 읽기 쉽게 유지하면서도 모니터링할 때 같은 필드 기준으로 검색·집계할 수 있게 하려는 목적이 있었기 때문입니다.

제가 중요하게 본 것은 "무슨 정보를 남길까"보다 먼저 **"로그 한 줄을 읽을 때 사람이 어떤 순서로 이해할까"**였습니다.
그래서 포맷은 아래 순서가 보이도록 맞췄습니다.

1. `level`, `event`, `msg`로 먼저 사건의 종류를 파악할 수 있게 한다.
2. `request_id`, `trace_id`, `path`, `status_code`로 어떤 요청인지 바로 이어서 볼 수 있게 한다.
3. `error.type`, `error.message`, `error.stack`은 실패 원인을 마지막에 자세히 보게 한다.

즉, 이 설계의 목적은 **가독성이 좋은 구조화 로그를 만들고**, **모든 모듈에서 같은 형식으로 로그를 남기게 하며**, **에러가 발생했을 때도 같은 JSON 구조 안에서 바로 원인을 추적할 수 있게 하는 것**입니다.

자세한 설명과 예시는 아래 문서를 참고해 주시기 바랍니다.

- `docs/dev_timeline/2026_04_23/02_logging_foundation.md`
- `docs/logging_structure/logging_refactoring_plan.md`
- `docs/logging_structure/logging_trace_context_policy.md`
- `docs/logging_structure/logging_error_stack_policy.md`
- `docs/drain/drain_policy.md`

## 구현하면서 고민한 점

이번 작업에서 가장 많이 고민한 부분은 **운영 기반을 어디까지 먼저 만들 것인지**였습니다.
초기에는 drain, lifecycle, OpenTelemetry, dependency health를 더 많이 넣을 수도 있었지만, 아직 실제 서비스 로직이 없는 단계에서 과하게 앞서가는 것은 오히려 유지보수 부담이 된다고 판단했습니다.

그래서 현재는 다음 원칙으로 정리했습니다.

- logging은 JSON formatter와 request/trace 상관관계까지만 유지합니다.
- drain은 app 기준 상태 표현까지만 두고, 자동 drain은 제거했습니다.
- Redis와 PostgreSQL은 이벤트 수집 경로에 포함되었으므로 health 응답의 dependency status로 노출합니다.
- readiness/heartbeat 요청 시 Redis는 `PING`, PostgreSQL은 `SELECT 1`로 가벼운 ping-pong health check를 수행합니다.
- `shared`에는 공용 타입/직렬화만 남기고, runtime 성격의 코드는 `platform`으로 옮겼습니다.

상세한 설계 배경과 단계별 변경 내역은 아래 문서를 참고해 주시면 감사하겠습니다.

- `docs/dev_timeline/2026_04_23/01_environment_bootstrap.md`
- `docs/dev_timeline/2026_04_23/02_logging_foundation.md`
- `docs/dev_timeline/2026_04_23/03_health_and_app_drain.md`
- `docs/dev_timeline/2026_04_23/04_platform_and_shared_split.md`
- `docs/dev_timeline/2026_04_23/05_config_and_docs_cleanup.md`
- `docs/dev_timeline/2026_04_24/01_event_generator_step1.md`
- `docs/dev_timeline/2026_04_24/02_event_payload_contract.md`
- `docs/dev_timeline/2026_04_24/03_redis_stream_pipeline.md`
- `docs/dev_timeline/2026_04_24/04_postgres_storage_and_alembic.md`
- `docs/dev_timeline/2026_04_24/05_health_drain_docker_and_review.md`
- `docs/remaining_work.md`

## Step 1 이벤트 생성기

과제의 첫 단계로 커머스 웹 서비스 이벤트를 랜덤하게 생성하는 독립 producer를 추가했습니다.

```bash
python -m event_generator --max-events 10 --seed 20260424 --no-sleep
```

로컬에서 `python`이 3.12 환경을 가리키지 않는 경우에는 기존 backend uv 환경으로 실행할 수 있습니다.

```bash
UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend python -m event_generator --max-events 10 --seed 20260424 --no-sleep
```

이 생성기는 `page_view`, `product_click`, `add_to_cart`, `purchase`, `checkout_error` 이벤트를 stdout JSON Lines로 출력합니다. stdout은 이벤트 데이터만 담고, 시작/종료 요약은 stderr로 분리했습니다. JSON line 한 줄은 `schema_version=web_event.v1`을 포함하며 이후 MQ message body로 그대로 사용할 수 있는 raw event payload입니다.

Redis Streams pipeline은 아래 흐름으로 구성했습니다.

```text
event_generator --sink redis
  -> Redis Streams web.events.raw.v1
  -> FastAPI lifespan background consumer
  -> PostgreSQL events table batch insert
```

consumer는 HTTP route를 다시 호출하지 않고 backend 내부 `event_analytics` service/repository 로직을 직접 호출합니다. DB 저장은 한 건씩 insert하지 않고 batch insert 후 commit 성공 시 Redis message를 ack합니다.

health 응답에는 Redis와 PostgreSQL dependency status도 포함합니다.

```json
{
  "status": "ok",
  "checks": {"app": "ok", "redis": "ok", "database": "ok"},
  "reason": null
}
```

Redis stream consumer가 비활성화된 로컬 기본 상태에서는 `redis=disabled`, `database=disabled`로 표시합니다. consumer가 활성화된 Docker Compose 실행에서는 Redis `PING`, consumer group 생성, PostgreSQL `SELECT 1`이 성공해야 각각 `ok`가 됩니다. drain 전환 시에는 Redis와 database status도 `draining`으로 함께 내려가도록 맞췄습니다.

이벤트 타입, 필드 구성, 설계 이유, 실행 옵션은 아래 문서를 기준으로 합니다.

- `event_generator/README.md`
- `docs/event_generator/step1_summary.md`
- `docs/event_generator/step2_log_storage_plan.md`
- `docs/event_generator/mq_event_payload_contract.md`
- `docs/event_generator/redis_streams_pipeline_implementation_plan.md`
- `docs/event_generator/event_generator_design.md`
- `docs/event_generator/event_generator_implementation_plan.md`

## Step 2 저장소와 스키마

생성된 이벤트는 최종적으로 PostgreSQL `events` table에 저장합니다. Redis Streams는 저장소가 아니라 producer와 backend consumer 사이의 MQ 역할만 합니다.

```text
event_generator --sink redis
  -> Redis Streams web.events.raw.v1
  -> FastAPI lifespan background consumer
  -> PostgreSQL events table
```

PostgreSQL을 선택한 이유는 과제 요구사항과 Step3 분석 흐름이 가장 자연스럽게 연결되기 때문입니다.

- JSON payload를 통째로 저장하지 않고 컬럼으로 분리 저장할 수 있습니다.
- 이벤트 타입별/유저별/시간대별 집계를 SQL로 바로 실행할 수 있습니다.
- `event_id` primary key와 batch insert conflict-ignore로 중복 전달에 대응할 수 있습니다.
- Docker Compose에서 app + DB 구성이 명확합니다.

현재 저장 스키마는 아래와 같습니다.

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

분석/SQL UI에서 직접 조회할 대상은 raw `events` table이 아니라 아래 generated view allowlist입니다.

- `event_type_counts`
- `user_event_counts`
- `hourly_event_counts`
- `error_event_ratio`
- `commerce_funnel_counts`
- `product_event_counts`

## Step 3 집계 분석 API

Backend는 SQL 집계 결과를 프론트에서 사용할 수 있도록 아래 API를 제공합니다.

```text
GET  /analytics/datasets
GET  /analytics/presets
POST /analytics/query
```

예시 SQL:

```sql
SELECT event_type, event_count
FROM event_type_counts
ORDER BY event_count DESC, event_type;

SELECT event_hour, event_type, event_count
FROM hourly_event_counts
ORDER BY event_hour, event_type;
```

Manual SQL 실행은 서버에서 parser 기반으로 제한합니다.

- `SELECT`만 허용합니다.
- 한 번에 statement 하나만 허용합니다.
- raw `events` table 직접 조회는 거부합니다.
- allowlisted generated view만 조회할 수 있습니다.
- 결과 row는 최대 500개로 제한합니다.
- PostgreSQL read-only transaction으로 실행합니다.

자세한 설계는 `docs/event_generator/step2_backend_analytics_design.md`를 참고하면 됩니다.

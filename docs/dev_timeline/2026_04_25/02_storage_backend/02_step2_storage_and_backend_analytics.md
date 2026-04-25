# 2026-04-25 — Step2 storage and backend analytics branch

브랜치: `fect/step2-event-storage-analytics`  
기준 브랜치: `fect/event-generator`

## 1. 진행 배경

이전 브랜치에서 `event_generator -> Redis Streams -> FastAPI consumer -> PostgreSQL events table` 흐름을 구현하고 push했다.

이번 브랜치는 과제 Step2의 저장소/스키마 설명을 더 명확하게 하고, Step3/Step5로 이어질 backend API 기반을 만든다.

## 2. 구현한 내용

### 2.1 generated views migration

두 번째 Alembic migration을 추가했다.

```text
backend/alembic/versions/20260425_0002_create_event_analytics_views.py
```

생성 view:

- `event_type_counts`
- `user_event_counts`
- `hourly_event_counts`
- `error_event_ratio`
- `commerce_funnel_counts`
- `product_event_counts`

### 2.2 SQL policy

`sqlglot`을 추가하고 parser 기반 SQL validation을 구현했다.

```text
backend/app/event_analytics/application/query_policy.py
```

서버 정책:

- 단일 statement만 허용
- `SELECT`만 허용
- mutation / DDL 거부
- data-modifying CTE 거부
- raw `events` table 거부
- allowlisted generated view만 허용
- row limit 500 cap

### 2.3 Analytics API

추가 endpoint:

```text
GET  /analytics/datasets
GET  /analytics/presets
POST /analytics/query
```

구현 위치:

```text
backend/app/event_analytics/interface/router/analytics_router.py
backend/app/event_analytics/interface/schemas/analytics.py
backend/app/event_analytics/application/sql_query_service.py
backend/app/event_analytics/infrastructure/repositories/postgres_analytics_query_repository.py
```

### 2.4 Chart suggestion

SQL result shape를 보고 프론트가 바로 preview할 수 있게 작은 chart suggestion을 붙였다.

- label + numeric → `bar`
- temporal + numeric → `line`
- numeric-only → `metric`
- 그 외 → `table`

## 3. 설계 결정

- raw `events` table은 저장 기준 table로만 둔다.
- SQL UI는 generated view만 조회한다.
- query endpoint는 read-only transaction으로 실행한다.
- API는 frontend가 바로 붙을 수 있는 최소 단위로 제한한다.
- 복잡한 dashboard persistence, auth, chart builder는 이번 범위에서 제외한다.

## 4. 검증

부분 테스트:

```bash
UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend python -m pytest \
  backend/tests/event_analytics/test_query_policy.py \
  backend/tests/event_analytics/test_analytics_catalog.py \
  backend/tests/event_analytics/test_chart_suggestion.py \
  backend/tests/event_analytics/test_analytics_router.py \
  backend/tests/event_analytics/test_postgres_analytics_query_repository.py \
  backend/tests/event_analytics/test_alembic_views_migration.py
```

결과:

```text
28 passed
```

전체 `make ci`와 compose smoke는 문서 작성 후 실행한다.

## 5. 최종 검증 결과

전체 backend quality gate:

```bash
make ci
```

결과:

```text
ruff format/check passed
pyrefly: 0 errors
all guardrails passed
111 passed
```

Compose smoke:

```bash
DOCKER_BUILDKIT=0 APP_PORT=18001 POSTGRES_PORT=15433 REDIS_PORT=16380 \
  docker compose -p lda_step2 build app event-generator

APP_PORT=18001 POSTGRES_PORT=15433 REDIS_PORT=16380 \
  docker compose -p lda_step2 up -d db redis app

curl http://localhost:18001/health/ready

APP_PORT=18001 POSTGRES_PORT=15433 REDIS_PORT=16380 \
  docker compose -p lda_step2 run --rm event-generator \
  .venv/bin/python -m event_generator \
  --sink redis --producer-id producer_step2_e2e \
  --max-events 25 --seed 20260425 --no-sleep
```

확인 결과:

```text
/health/ready -> {"status":"ok","checks":{"app":"ok","redis":"ok","database":"ok"},"reason":null}
Redis XLEN web.events.raw.v1 -> 25
Redis XPENDING web.events.raw.v1 event_analytics_writer -> 0
PostgreSQL SELECT count(*) FROM events -> 25
created analytics views -> 6
GET /analytics/datasets -> 6 generated views, raw events table 없음
GET /analytics/presets -> preset SQL 5개
POST /analytics/query event_type_counts -> rows + bar chart suggestion 반환
POST /analytics/query DROP TABLE events -> 400 sql_policy_violation
```

Smoke 이후 stack은 `docker compose -p lda_step2 down -v`로 정리했다.

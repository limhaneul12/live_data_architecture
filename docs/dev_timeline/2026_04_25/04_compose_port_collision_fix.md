# 2026-04-25 — Compose host port collision fix

## 1. 문제

`docker compose up --build` 실행 중 PostgreSQL container가 시작되지 않았다.

```text
Bind for 0.0.0.0:5432 failed: port is already allocated
```

로컬 Docker에는 이미 다른 프로젝트의 `trandai-db`가 host port `5432`를 사용하고 있었다.

## 2. 결정

컨테이너 내부 통신은 그대로 둔다.

```text
app -> db:5432
app -> redis:6379
frontend -> app:8000
```

대신 host로 노출하는 기본 포트만 충돌 가능성이 낮은 값으로 변경한다.

```text
PostgreSQL host port: 15432 -> container 5432
Redis host port:      16379 -> container 6379
```

## 3. 변경

- `docker-compose.yml`
  - `POSTGRES_PORT` fallback: `15432`
  - `REDIS_PORT` fallback: `16379`
- `.env.example`
  - `DATABASE_DB_ADDRESS=postgresql://live_data:live_data@localhost:15432/live_data`
  - `STREAM_REDIS_URL=redis://localhost:16379/0`
  - `POSTGRES_PORT=15432`
  - `REDIS_PORT=16379`
- local `.env`
  - 동일 포트로 갱신했다. `.env`는 git에 포함하지 않는다.

## 4. 검증

```text
docker compose config -> passed
docker compose up -d db redis app frontend -> db/redis healthy, app/frontend started
GET http://localhost:8000/health/ready -> app/redis/database ok
GET http://localhost:3000/api/analytics/datasets -> 6 generated views
finite event_generator 5 events -> Redis delta +5, PostgreSQL events delta +5
```

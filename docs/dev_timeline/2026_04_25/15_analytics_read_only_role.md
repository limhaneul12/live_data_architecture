# 15. Analytics read-only role and grants

## 배경

SQL Lab은 validator와 runtime guardrail을 적용해도 최종적으로 raw SQL을 실행하는
표면이 남는다. 따라서 DB 권한 경계가 필요하다.

## 구현 내용

### 1. Alembic role/grant migration

`backend/alembic/versions/20260425_0003_create_analytics_reader_grants.py`를 추가했다.

`ANALYTICS_DATABASE_DB_ADDRESS`가 설정된 경우 해당 DSN의 username/password를 읽어
analytics reader role을 만든다. 설정이 없으면 migration은 role/grant 작업을 건너뛰므로
기존 local 개발 DB 흐름은 깨지지 않는다.

적용되는 권한:

- analytics role 생성 또는 기존 role hardening
  - `LOGIN`
  - `NOSUPERUSER`
  - `NOCREATEDB`
  - `NOCREATEROLE`
  - `NOREPLICATION`
- role 기본 설정
  - `default_transaction_read_only = on`
  - `statement_timeout = '3s'`
  - `idle_in_transaction_session_timeout = '5s'`
- `public` schema usage grant
- raw `events` table 권한 revoke
- generated analytics views에만 `SELECT` grant

### 2. Compose 자동 적용

`docker-compose.yml`의 app service에 아래 값을 추가했다.

```yaml
ANALYTICS_DATABASE_DB_ADDRESS: postgresql://analytics_reader:analytics_reader@db:5432/live_data
```

app container 시작 시 `DATABASE_DB_ADDRESS`로 Alembic migration을 먼저 실행하고, migration이
analytics role과 grant를 구성한다. 이후 FastAPI runtime은 `ANALYTICS_DATABASE_DB_ADDRESS`를
읽어 SQL Lab/Explore query에 read-only role을 사용한다.

## 보안 효과

이제 compose 기준으로는 SQL Lab validator가 뚫리더라도 analytics DB connection 자체가
writer 권한을 갖지 않는다.

단, SQL Lab raw SQL wrapper는 구조적으로 남아 있으므로 Bandit B608은 계속 지적한다.
이 지적은 `text(raw_sql)` 자체에 대한 정적 분석 경고이며, DB 권한 경계로 blast radius를
줄이는 방향으로 보강했다.

## 검증

- migration metadata/unit test
- `make ci`
- frontend typecheck/lint/build
- fresh compose DB에서 migration 후 `analytics_reader`로 generated view SELECT 성공
- 같은 role로 raw `events` table SELECT 실패

실행 결과:

```bash
DATABASE_DB_ADDRESS=postgresql://live_data:live_data@localhost:15432/live_data \
ANALYTICS_DATABASE_DB_ADDRESS=postgresql://analytics_reader:analytics_reader@localhost:15432/live_data \
UV_PROJECT_ENVIRONMENT=../.venv \
uv run --project backend alembic -c backend/alembic.ini upgrade head
```

```text
Running upgrade 20260425_0002 -> 20260425_0003
```

`analytics_reader` 연결 검증:

```text
view_select_ok=5
events_select_blocked=InsufficientPrivilegeError
default_transaction_read_only=on
statement_timeout=3s
```

전체 gate:

```text
make ci -> 160 passed
npm run typecheck && npm run lint && npm run build -> passed
docker compose config --quiet -> passed
```

Bandit:

```text
B608: SQL Lab raw SQL wrapper remains flagged
B311: deterministic event generator random remains flagged
```

B608은 SQL Lab의 manual SQL 목적 때문에 남는 정적 분석 경고다. 이번 변경으로 compose
runtime에서는 DB role 권한 경계를 추가했다.

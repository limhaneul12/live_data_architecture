# 2026-04-25 — Analytics SQL security hardening

브랜치: `fix/analytics-sql-security-hardening`  
기준 브랜치: `fect/frontend-event-analytics`

## 1. 진행 배경

`/analytics/query`는 사용자가 입력한 SQL을 실행하는 UI 요구사항 때문에 raw SQL
실행 경로를 갖는다.

검토 결과 이 경로는 “SQLAlchemy를 쓰므로 안전한 ORM 코드”가 아니라,
`sqlglot` validator를 통과한 문자열을 SQLAlchemy `text()`로 실행하는 구조였다.
따라서 SQL injection과 read-only DoS 방어를 SQLAlchemy에 맡기면 안 되고,
정책 validator와 PostgreSQL runtime guardrail을 명확히 강화해야 했다.

## 2. 협업 검증 결과

아래 검증을 병렬로 진행했다.

- Codex native `security-reviewer`
- Codex native `architect`
- Codex native `gpt-5.4 xhigh`
- local `codex exec -m gpt-5.4 -c model_reasoning_effort="xhigh"`

공통 결론:

- `text(raw_sql)`은 raw SQL 실행이다.
- bind parameter로 안전한 부분은 outer `row_limit`뿐이다.
- 기존 validator는 destructive statement와 raw table 접근은 막았지만,
  `pg_sleep`, `pg_advisory_lock`, `set_config`, join/subquery 기반 비용 공격은
  통과시킬 수 있었다.
- `SET TRANSACTION READ ONLY`는 DML/DDL 방어에는 의미가 있지만 read-only 정보 노출,
  function call, heavy query DoS 방어에는 부족하다.
- 정책 차단 테스트와 PostgreSQL timeout이 필요하다.

## 3. 구현 변경

### 3.1 SQL policy 강화

`backend/app/event_analytics/application/query_policy.py`

추가 거부 사유:

- `query_too_long`
- `disallowed_cte`
- `disallowed_subquery`
- `disallowed_join`
- `disallowed_function`
- `disallowed_select_into`
- `disallowed_locking_read`
- `disallowed_offset`
- `disallowed_distinct`
- `disallowed_table_sample`
- `disallowed_grouping`
- `disallowed_ordinal_order`

v1 manual SQL은 아래 형태만 허용한다.

```sql
SELECT <columns>
FROM <allowlisted_generated_view>
WHERE ...
ORDER BY ...
LIMIT ...
```

반대로 아래는 모두 거부한다.

```sql
SELECT pg_sleep(10), event_count FROM event_type_counts;
SELECT pg_advisory_lock(1), event_count FROM event_type_counts;
SELECT set_config('search_path', 'public', false) FROM event_type_counts;
SELECT * FROM event_type_counts CROSS JOIN user_event_counts;
SELECT * FROM event_type_counts CROSS JOIN LATERAL (SELECT pg_sleep(1)) s;
SELECT * FROM event_type_counts WHERE event_count = ALL(SELECT 1);
SELECT * FROM event_type_counts WHERE event_count = SOME(SELECT 1);
WITH ranked AS (SELECT * FROM event_type_counts) SELECT * FROM ranked;
SELECT * FROM (SELECT * FROM event_type_counts) AS nested_events;
SELECT * INTO temp_event_counts FROM event_type_counts;
SELECT * FROM event_type_counts FOR UPDATE;
SELECT event_type FROM event_type_counts OFFSET 1000000;
SELECT DISTINCT event_type FROM event_type_counts;
SELECT * FROM event_type_counts TABLESAMPLE SYSTEM (100);
SELECT event_type, event_count FROM event_type_counts GROUP BY event_type, event_count;
SELECT event_type, event_count FROM event_type_counts ORDER BY 2 DESC;
```

추가 리뷰에서 `ALL(SELECT ...)` / `SOME(SELECT ...)`가 `sqlglot` AST에서
`exp.Subquery`만으로는 잡히지 않는다는 지적이 있었다. 그래서 root SELECT 외의 모든
nested `exp.Select`도 함께 거부한다.

또한 DB 실행 전 parser가 먼저 동작하므로, oversized SQL로 인한 app-side parse DoS를
줄이기 위해 SQL text 길이를 4,000자로 제한했다. 같은 제한은 API Pydantic schema에도
적용했다.

재검토에서 `OFFSET`, `TABLESAMPLE`, `DISTINCT`, ordinal `ORDER BY` 같은 비용 증폭
read-only shape가 non-blocking 잔여 위험으로 지적됐다. v1의 목적은 generated view에
대한 단순 조회이므로 이들도 정책에서 차단했다.

### 3.2 PostgreSQL runtime guardrail 추가

`backend/app/event_analytics/infrastructure/repositories/postgres_analytics_query_repository.py`

실행 직전 transaction 안에서 아래 guard SQL을 적용한다.

```sql
SET TRANSACTION READ ONLY;
SET LOCAL search_path = public, pg_catalog;
SET LOCAL statement_timeout = '3000ms';
SET LOCAL lock_timeout = '500ms';
SET LOCAL idle_in_transaction_session_timeout = '5000ms';
```

의도:

- `READ ONLY`: mutation/DDL이 repository 실행 단계까지 도달해도 차단
- `search_path`: allowlisted unqualified view 해석 범위를 고정
- `statement_timeout`: long-running read query 방어
- `lock_timeout`: lock wait 장기화 방어
- `idle_in_transaction_session_timeout`: transaction idle 누수 방어

### 3.3 테스트 추가

추가/수정한 테스트:

- `backend/tests/event_analytics/test_query_policy.py`
- function/join/subquery/CTE 공격 surface 거부
- `ALL(SELECT ...)`, `SOME(SELECT ...)`, `SELECT INTO`, `FOR UPDATE` 우회 거부
- `OFFSET`, `DISTINCT`, `TABLESAMPLE`, `GROUP BY`, ordinal `ORDER BY` 비용 증폭 shape 거부
- oversized SQL parse 전 거부
- 단일 generated view에 대한 filter/order 허용
- `backend/tests/event_analytics/test_analytics_router.py`
  - `pg_sleep` query가 HTTP 400 `disallowed_function`으로 매핑되는지 확인
- `backend/tests/event_analytics/test_postgres_analytics_query_repository.py`
  - runtime guard SQL 생성
  - guard SQL이 실제 query보다 먼저 실행되는 순서 확인

## 4. 공식 문서 기준

- SQLAlchemy `text()`는 literal SQL fragment 또는 standalone textual statement를
  실행하는 도구이고, 안전한 값 주입은 bind parameter를 통해 이뤄진다.
- PostgreSQL `statement_timeout`, `lock_timeout`,
  `idle_in_transaction_session_timeout`은 session/transaction 단위 query 실행시간,
  lock wait, idle transaction을 제한하는 방어선이다.
- OWASP는 parameterized query를 1차 방어로 권장하고, bind variable로 처리할 수 없는
  구조적 SQL 요소에는 allowlist validation 또는 query redesign이 필요하다고 설명한다.

## 5. 현재 한계와 다음 판단

이번 브랜치는 “사용자가 SQL을 입력하면 결과를 시각화한다”는 과제 요구사항을 유지하면서
위험한 read-only SQL shape를 줄이는 보수적 패치다.

아직 production-grade SQL sandbox라고 말하면 안 된다.

남은 보강 후보:

1. analytics 전용 read-only DB role과 schema 권한 분리
2. SQL editor 일반 사용자 노출 대신 preset/DSL/query builder 중심 UX
3. 허용 함수가 정말 필요해질 때만 매우 좁은 allowlist 추가
4. statement cost / rate limit / audit log

## 6. 현재 검증 결과

부분 테스트:

```bash
UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend python -m pytest \
  backend/tests/event_analytics/test_query_policy.py \
  backend/tests/event_analytics/test_analytics_router.py \
  backend/tests/event_analytics/test_postgres_analytics_query_repository.py
```

결과:

```text
46 passed
```

Preset policy test:

```bash
UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend python -m pytest \
  backend/tests/event_analytics/test_analytics_catalog.py
```

결과:

```text
2 passed
```

전체 quality gate:

```bash
make ci
```

결과:

```text
ruff format/check passed
pyrefly: 0 errors
all guardrails passed
136 passed
```

Docker/API smoke:

```bash
docker compose config

DOCKER_BUILDKIT=0 APP_PORT=18002 POSTGRES_PORT=15434 REDIS_PORT=16381 \
  docker compose -p lda_sqlsec build app

DOCKER_BUILDKIT=0 APP_PORT=18002 POSTGRES_PORT=15434 REDIS_PORT=16381 \
  docker compose -p lda_sqlsec up -d db redis app

curl http://localhost:18002/health/ready

curl -X POST http://localhost:18002/analytics/query \
  -H 'content-type: application/json' \
  -d '{"sql":"SELECT event_type, event_count FROM event_type_counts ORDER BY event_count DESC","row_limit":5}'

curl -i -X POST http://localhost:18002/analytics/query \
  -H 'content-type: application/json' \
  -d '{"sql":"SELECT pg_sleep(10), event_count FROM event_type_counts","row_limit":5}'

curl -i -X POST http://localhost:18002/analytics/query \
  -H 'content-type: application/json' \
  -d '{"sql":"SELECT * FROM event_type_counts CROSS JOIN user_event_counts","row_limit":5}'

curl -i -X POST http://localhost:18002/analytics/query \
  -H 'content-type: application/json' \
  -d '{"sql":"SELECT * FROM event_type_counts WHERE event_count = ALL(SELECT 1)","row_limit":5}'

curl -i -X POST http://localhost:18002/analytics/query \
  -H 'content-type: application/json' \
  -d '{"sql":"SELECT * FROM event_type_counts FOR UPDATE","row_limit":5}'

curl -i -X POST http://localhost:18002/analytics/query \
  -H 'content-type: application/json' \
  -d '{"sql":"SELECT event_type FROM event_type_counts OFFSET 1000000","row_limit":5}'

curl -i -X POST http://localhost:18002/analytics/query \
  -H 'content-type: application/json' \
  -d '{"sql":"SELECT DISTINCT event_type FROM event_type_counts","row_limit":5}'

curl -i -X POST http://localhost:18002/analytics/query \
  -H 'content-type: application/json' \
  -d '{"sql":"SELECT event_type, event_count FROM event_type_counts ORDER BY 2 DESC","row_limit":5}'
```

확인 결과:

```text
docker compose config -> ok
/health/ready -> {"status":"ok","checks":{"app":"ok","redis":"ok","database":"ok"},"reason":null}
valid SELECT over event_type_counts -> 200, columns/rows/chart payload
pg_sleep query -> 400, rejected_reason=disallowed_function
CROSS JOIN query -> 400, rejected_reason=disallowed_join
ALL(SELECT ...) query -> 400, rejected_reason=disallowed_subquery
FOR UPDATE query -> 400, rejected_reason=disallowed_locking_read
OFFSET query -> 400, rejected_reason=disallowed_offset
DISTINCT query -> 400, rejected_reason=disallowed_distinct
ordinal ORDER BY query -> 400, rejected_reason=disallowed_ordinal_order
oversized SQL text -> 422, string_too_long, max_length=4000
```

Smoke 이후 stack은 아래 명령으로 정리했다.

```bash
DOCKER_BUILDKIT=0 APP_PORT=18002 POSTGRES_PORT=15434 REDIS_PORT=16381 \
  docker compose -p lda_sqlsec down -v
```

정책 probe:

```text
pg_sleep: REJECT disallowed_function
advisory_lock: REJECT disallowed_function
set_config: REJECT disallowed_function
cross_join: REJECT disallowed_join
lateral_sleep: REJECT disallowed_subquery
all_select: REJECT disallowed_subquery
some_select: REJECT disallowed_subquery
select_into: REJECT disallowed_select_into
for_update: REJECT disallowed_locking_read
offset: REJECT disallowed_offset
distinct: REJECT disallowed_distinct
tablesample: REJECT disallowed_table_sample
group_by: REJECT disallowed_grouping
ordinal_order: REJECT disallowed_ordinal_order
simple: PASS SELECT event_type, event_count FROM event_type_counts ORDER BY event_count DESC
```

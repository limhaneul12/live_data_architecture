# 17. Superset-style raw SQL Lab guardrails

작성일: 2026-04-25  
브랜치: `fect/structured-explore-query`

## 배경

SQL Lab을 structured query builder로만 바꾸면 SQL Injection surface는 줄어들지만,
Superset SQL Lab의 핵심인 생 SQL 입력 경험이 사라진다. Superset도 SQL Lab에서는 SQL
문자열을 받고 DB cursor로 실행하므로, 이번 방향은 “생 SQL 유지 + 다층 guardrail”로
정리한다.

## 결정

SQL Lab은 `/analytics/query` raw SQL 경로를 유지한다. 대신 아래 방어선을 조합한다.

- analytics 전용 read-only DB role 사용
- generated view allowlist만 조회 허용
- DML/DDL 및 data-modifying CTE 차단
- `statement_timeout`, `lock_timeout`, `idle_in_transaction_session_timeout` 적용
- outer `LIMIT :row_limit`로 최대 row cap 적용
- system catalog/schema(`information_schema`, `pg_catalog`) 접근 차단
- 위험 함수 및 allowlist 밖 함수 차단
- SQL Lab audit log 기록

## 구현 변경

### 1. SQL shape 완화

기존 policy는 join, group by, CTE, subquery, aggregate function을 모두 차단했다.
Superset-style SQL Lab에 맞게 아래 read-only shape는 허용한다.

- `JOIN`
- `WHERE`
- `GROUP BY`
- `DISTINCT`
- `OFFSET`
- read-only CTE
- read-only subquery
- aggregate function allowlist

단, 모든 physical table/view reference는 generated view allowlist에 있어야 한다. CTE
alias는 physical relation으로 보지 않는다.

### 2. 함수 policy

모든 함수를 차단하지 않고, 과제 분석에 필요한 좁은 allowlist를 둔다.

허용:

- `COUNT`
- `SUM`
- `AVG`
- `MIN`
- `MAX`
- `ROUND`
- `DATE_TRUNC` / sqlglot `TIMESTAMP_TRUNC`

거부 예시:

- `pg_sleep`
- `pg_advisory_lock`
- `set_config`
- `version`
- `generate_series`

### 3. catalog/schema 차단

`information_schema.tables`, `pg_catalog.pg_user` 같은 system catalog/schema relation은
별도 rejection reason(`disallowed_system_catalog`)으로 차단한다. 그 외 schema-qualified
relation(`public.event_type_counts`)은 기존처럼 `cross_schema_relation`으로 거부한다.

### 4. audit log

`SqlQueryService`가 SQL 전문을 로그에 남기지 않고 SHA-256 hash 기준으로 audit event를
남긴다.

- `analytics_sql_rejected`: policy rejection reason 포함
- `analytics_sql_accepted`: relation 목록과 row limit 포함
- `analytics_sql_completed`: 반환 row count 포함

raw SQL 전문을 남기지 않는 이유는 SQL Lab query에 사람이 입력한 조건값이나 민감한
문자열이 섞일 수 있기 때문이다.

### 5. 정적 분석 예외 표기

SQL Lab은 Superset 방식에 맞춰 raw SQL 실행 surface를 의도적으로 유지한다. 따라서
outer limit wrapper의 문자열 SQL 구성은 `# nosec`로 표시하되, 바로 앞단의
`AnalyticsSqlPolicy`, read-only DB role, runtime timeout, generated view grant가 실제
방어선임을 문서화한다.

이벤트 생성기의 `random.Random(seed)`는 보안 토큰 생성이 아니라 재현 가능한 목데이터와
트래픽 패턴 생성을 위한 deterministic random이다. 해당 두 지점도 `# nosec B311`로
의도적 사용임을 표시한다.

## 검증

```bash
UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend python -m pytest \
  backend/tests/event_analytics/test_query_policy.py \
  backend/tests/event_analytics/test_analytics_router.py -q
```

결과:

```text
42 passed
```

추가 확인:

```bash
UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend ruff format --check --config backend/pyproject.toml \
  backend/app/event_analytics/application/query_policy.py \
  backend/app/event_analytics/application/sql_query_service.py \
  backend/tests/event_analytics/test_query_policy.py \
  backend/tests/event_analytics/test_analytics_router.py

UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend ruff check --config backend/pyproject.toml \
  backend/app/event_analytics/application/query_policy.py \
  backend/app/event_analytics/application/sql_query_service.py \
  backend/tests/event_analytics/test_query_policy.py \
  backend/tests/event_analytics/test_analytics_router.py

UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend pyrefly check \
  backend/app/event_analytics/application/query_policy.py \
  backend/app/event_analytics/application/sql_query_service.py \
  backend/tests/event_analytics/test_query_policy.py \
  backend/tests/event_analytics/test_analytics_router.py
```

결과:

```text
ruff format --check -> 4 files already formatted
ruff check -> All checks passed
pyrefly -> 0 errors
```

```bash
uvx bandit -r backend/app event_generator -x backend/tests,event_generator/tests -q
```

결과:

```text
No issues identified.
```

## 남은 리스크

- SQL Lab은 여전히 raw SQL 실행 surface이므로 정적 분석 예외는 의도적 위험 인수다.
- `statement_timeout`은 query cost를 줄이는 강한 방어선이지만 query planner 단계의 모든
  비용을 사전에 예측하지는 않는다.
- Superset급 query cancel endpoint, query history, 사용자별 권한은 아직 없다.

# 2026-04-25 — Structured Explore query and donut chart

브랜치: `fect/structured-explore-query`
기준 브랜치: `fect/superset-analytics-ui`

## 1. 진행 배경

Superset-style UI를 만든 뒤, Explore 화면도 frontend에서 SQL 문자열을 조립해
`/analytics/query`로 보내는 구조가 남아 있었다. 사용자는 더 정석적인 방식으로
`/analytics/explore-query` structured endpoint를 추가하고, backend에서 SQLAlchemy Core로
쿼리를 생성하는 방향을 요청했다.

추가 UI 요구사항은 아래 두 가지다.

- 동그라미 차트 추가
- SQL Lab은 chart preview 없이 query result table만 보여주기

## 2. 구현 범위

### 2.1 Structured Explore API

새 endpoint:

```text
POST /analytics/explore-query
```

요청 예시:

```json
{
  "dataset": "event_type_counts",
  "columns": ["event_type", "event_count"],
  "order_by": "event_count",
  "order_direction": "desc",
  "row_limit": 100
}
```

처리 흐름:

```text
Pydantic request
  -> ExploreQueryService
  -> dataset/column/order allowlist validation
  -> internal dataclass ExploreQuery
  -> PostgresAnalyticsQueryRepository
  -> SQLAlchemy Core select()/table()/column()
  -> PostgreSQL read-only transaction guard
  -> AnalyticsQueryResponse
```

중요한 변화:

- Explore는 더 이상 frontend raw SQL 문자열을 실행 경로로 삼지 않는다.
- frontend가 보낸 dataset/columns/order/limit만 backend catalog allowlist로 검증한다.
- SQLAlchemy Core로 SELECT statement를 만들고 session.execute(statement)로 실행한다.
- manual SQL Lab은 기존 `/analytics/query` 경로를 유지한다.

### 2.2 Backend validation

추가한 검증:

| reason | 조건 |
|---|---|
| `unknown_dataset` | dataset이 generated view catalog에 없음 |
| `missing_columns` | projection column이 없음 |
| `duplicate_columns` | projection column 중복 |
| `unknown_column` | projection column이 dataset metadata에 없음 |
| `unknown_order_column` | order_by가 dataset metadata에 없음 |

row_limit은 기존 정책과 동일하게 최대 500개로 cap한다.

### 2.3 Frontend Explore 연결

Explore의 `Run chart` 버튼은 이제 `/api/analytics/explore-query` proxy를 호출한다.
Generated SQL panel은 실제 실행 SQL이 아니라 사용자가 이해하기 위한 preview로 남겼다.

Chart control에 `Donut chart`를 추가했고, `event_type_counts` 기본 chart를 donut으로 바꿨다.

### 2.4 SQL Lab table-only

SQL Lab은 `Run SQL` 후 chart preview를 숨기고 `ResultTable`만 표시한다.
즉 SQL Lab은 “쿼리 결과 전체 확인” 용도로 두고, charting은 Explore tab이 담당한다.

## 3. 참고한 공식 문서

SQLAlchemy 2.0 공식 문서 기준으로 `select()`는 SELECT construct를 만들고, `table()`은
TableClause를 만드는 Core construct다. 이번 endpoint는 이 Core construct를 사용해
사용자 문자열 대신 allowlisted dataset/column metadata에서 statement를 생성한다.

## 4. 검증 계획

```bash
UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend python -m pytest \
  backend/tests/event_analytics/test_explore_query_service.py \
  backend/tests/event_analytics/test_analytics_router.py \
  backend/tests/event_analytics/test_postgres_analytics_query_repository.py

make ci
make frontend-ci
docker compose config
git diff --check
```

최종 검증 결과는 실행 후 이어서 기록한다.

## 5. 사용자 리뷰 반영 — keyword-only `*` 남용 정리

리뷰 중 내부 함수/메서드에서 keyword-only `*`를 과하게 쓰고 있다는 지적을 받았다.
이번 branch에서 추가/수정한 structured query path는 물론 `event_analytics` 범위에서 남아 있던
불필요한 bare `*` signature를 정리했다.

정리 기준:

- 인자가 1~2개이고 호출 의미가 명확한 helper/service method는 positional 허용
- dataclass의 `kw_only=True`는 내부 model 생성 안정성을 위한 별도 정책이므로 유지
- 실제로 keyword-only가 의미 있는 설정 boundary가 생길 때만 다시 도입

확인:

```bash
rg -n "def .+\(.*\*[,)]|async def .+\(.*\*[,]" backend/app/event_analytics backend/tests/event_analytics -S
```

결과:

```text
no matches
```

## 6. 최종 검증 결과

Targeted backend regression:

```bash
UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend python -m pytest \
  backend/tests/event_analytics/test_explore_query_service.py \
  backend/tests/event_analytics/test_analytics_router.py \
  backend/tests/event_analytics/test_postgres_analytics_query_repository.py
```

결과:

```text
22 passed
```

Full backend quality gate:

```bash
make ci
```

결과:

```text
ruff format/check passed
pyrefly: 0 errors
guardrails passed
146 passed
```

Frontend quality gate:

```bash
make frontend-ci
```

결과:

```text
eslint passed
tsc --noEmit passed
next build passed
```

Compose/diff hygiene:

```text
docker compose config -> ok
git diff --check -> ok
```

Additional dependency check:

```text
npm audit --omit=dev --audit-level=moderate -> found 0 vulnerabilities
```

Reference:

- SQLAlchemy 2.0 `select()` / `table()` Core constructs: https://docs.sqlalchemy.org/en/20/core/selectable.html
- SQLAlchemy Unified Tutorial — Using SELECT Statements: https://docs.sqlalchemy.org/en/20/tutorial/data_select.html

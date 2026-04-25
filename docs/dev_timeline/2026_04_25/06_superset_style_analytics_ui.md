# 2026-04-25 — Superset-style analytics UI

브랜치: `fect/superset-analytics-ui`
기준 브랜치: `fix/analytics-sql-security-hardening`

## 1. 진행 배경

사용자 요구가 단순 SQL textarea 중심 화면에서 Superset 방식의 분석 UI로 바뀌었다.
다만 과제 범위상 dashboard 저장, 인증, query history, 복잡한 drag-and-drop builder까지
구현하면 과해지므로, Superset의 핵심 사용 흐름만 가볍게 가져간다.

목표는 아래 흐름이다.

```text
generated dataset 선택
  -> columns / chart type / sort / row limit control 조정
  -> 안전한 SELECT 자동 생성
  -> /analytics/query 실행
  -> chart preview + table 표시
```

수동 SQL을 완전히 없애지는 않고, 고급 사용 흐름은 SQL Lab에 남긴다.

## 2. 구현 범위

### 2.1 Backend metadata 확장

`GET /analytics/datasets` 응답에 generated view별 column metadata를 추가했다.

```json
{
  "name": "event_type_counts",
  "label": "Event type counts",
  "description": "이벤트 타입별 발생 횟수를 집계한 generated view입니다.",
  "columns": [
    {"name": "event_type", "label": "Event type", "kind": "dimension"},
    {"name": "event_count", "label": "Event count", "kind": "metric"}
  ]
}
```

`kind`는 frontend control과 기본 chart 선택을 돕는 semantic hint다.

| kind | 사용 목적 |
|---|---|
| `dimension` | category / label 축 후보 |
| `metric` | numeric measure / sort 후보 |
| `temporal` | time-series x-axis 후보 |

내부 model은 dataclass로 유지했고, API boundary만 Pydantic schema로 직렬화한다.

### 2.2 Frontend Superset-style layout

`frontend/app/components/analytics-workspace.tsx`를 Superset-style workspace로 재구성했다.

구성:

- top navigation: Event Analytics / Dashboards / Charts / SQL Lab / Datasets
- left sidebar: workflow 설명, saved query 목록, SQL guardrails 요약
- Explore tab: datasource, visualization type, sort, row limit, columns control
- SQL Lab tab: SQL editor, dataset metadata panel, query result
- generated SQL preview
- chart preview + result table

UI 색상과 밀도는 흰색 surface, 청록 brand, panel/card 중심으로 정리했다.

### 2.3 Query flow

Explore mode는 사용자가 구조적 SQL을 직접 조립하지 않도록 backend metadata에서 받은
allowlisted dataset/column 이름으로만 SQL을 만든다.

생성 SQL 예시:

```sql
SELECT event_type, event_count
FROM event_type_counts
ORDER BY event_count DESC
LIMIT 100
```

이 SQL은 기존 hardening 정책을 그대로 통과하는 단순 SELECT 형태다.

SQL Lab mode는 기존 `/analytics/query` raw SQL 경로를 유지하되, 서버 정책이
function/join/subquery/CTE/raw table 접근을 거부한다.

## 3. 설계 결정

- Superset 전체 clone이 아니라 “Explore + SQL Lab”만 v1 범위로 잡았다.
- backend에 별도 query-builder endpoint를 추가하지 않고, 먼저 dataset column metadata를
  노출해 frontend에서 제한 SQL을 생성한다.
- dashboard 저장, chart 저장, auth, query history는 제출 범위에서 제외한다.
- chart library dependency를 추가하지 않고 기존 CSS/SVG preview를 유지한다.
- SQL Lab은 남겨두되 기본 진입점은 Explore로 바꿔 raw SQL 입력 부담을 낮춘다.

## 4. 현재 한계

- Explore generated SQL도 결국 `/analytics/query`로 실행되므로 backend에는 아직
  SQLAlchemy Core 기반 structured query endpoint가 없다.
- Superset처럼 metric/adhoc filter/grouping을 자유롭게 조합하는 builder는 아니다.
- 화면 스크린샷 기반 visual regression은 아직 자동화하지 않았다.

다음 보강 후보는 `/analytics/explore-query` 같은 structured request endpoint를 추가해
frontend가 SQL 문자열 대신 dataset/columns/order/limit을 보내고 backend가 SQLAlchemy Core로
쿼리를 생성하는 방식이다.

## 5. 검증 계획

```bash
UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend python -m pytest \
  backend/tests/event_analytics/test_analytics_catalog.py \
  backend/tests/event_analytics/test_analytics_router.py

cd frontend && npm run lint
cd frontend && npm run typecheck
cd frontend && npm run build

make ci
make frontend-ci
git diff --check
```

최종 결과는 실행 후 이 문서에 이어서 기록한다.

## 6. 최종 검증 결과

Backend targeted regression:

```bash
UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend python -m pytest \
  backend/tests/event_analytics/test_analytics_catalog.py \
  backend/tests/event_analytics/test_analytics_router.py
```

결과:

```text
10 passed
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

Backend full quality gate:

```bash
make ci
```

결과:

```text
ruff format/check passed
pyrefly: 0 errors
guardrails passed
136 passed
```

Compose config / diff hygiene:

```bash
docker compose config -> ok
git diff --check -> ok
```

Additional dependency check:

```text
npm audit --omit=dev --audit-level=moderate -> found 0 vulnerabilities
```

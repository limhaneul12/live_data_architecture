# View Tables page and Chart JOIN plan

## Intent

사용자가 Alembic을 직접 수정하지 않고 분석용 view table을 만들고, 그 결과를 Chart Builder의 dataset으로 사용하는 흐름을 추가한다. Chart Builder에는 dataset 간 JOIN을 선택하는 최소 UI를 추가한다.

## Scope

- View Tables 화면을 추가한다.
- 사용자는 `SELECT` SQL과 view name, description을 입력한다.
- 백엔드는 사용자 SQL을 검증한 뒤 `CREATE OR REPLACE VIEW`를 실행한다.
- 생성된 view metadata는 `analytics_view_tables`에 저장한다.
- `/analytics/datasets`는 built-in generated view와 사용자 생성 view table을 함께 반환한다.
- Chart Builder는 base dataset 기준으로 최대 1개 dataset JOIN을 설정할 수 있다.
- JOIN 실행은 raw SQL이 아니라 structured request를 백엔드에서 SQLAlchemy Core로 생성한다.

## Non-goals

- 외부 DB connection 관리 없음.
- auth/permission UI 없음.
- dashboard/chart 저장 기능 없음.
- arbitrary SQL DDL 입력 없음. 사용자는 `SELECT`만 입력하고 backend가 view DDL을 생성한다.
- 다단계 join graph builder는 하지 않는다. 과제 범위에서는 1-hop join만 허용한다.

## Backend shape

- `analytics_view_tables` metadata table
  - `name`
  - `description`
  - `source_sql`
  - `created_at`
  - `updated_at`
- `AnalyticsCatalogService`
  - built-in datasets + dynamic view table datasets 반환
- `ViewTableService`
  - preview
  - create/update view table
- `ExploreQueryService`
  - base dataset query
  - optional 1-hop join query
- SQL policy
  - SQL Lab: dataset allowlist only
  - View Tables: `events` + allowlisted datasets 기반 SELECT 허용

## Frontend shape

- Top nav: `Charts`, `SQL Lab`, `View Tables`
- View Tables page
  - view name
  - description
  - SELECT editor
  - Preview
  - Save as dataset
- Charts page JOIN controls
  - enable join
  - join table
  - join type
  - base column
  - join column
  - joined columns selection

## Verification

- Backend unit/API tests
- SQLAlchemy compiled SQL tests for JOIN statement
- Frontend typecheck/lint/build
- Full `make ci`

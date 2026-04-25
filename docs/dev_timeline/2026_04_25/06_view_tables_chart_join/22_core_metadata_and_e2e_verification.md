# SQLAlchemy Core metadata query and E2E verification follow-up

## 변경 이유

View Tables 목록을 만들기 위해 `analytics_view_tables` 메타데이터와
`information_schema.columns`를 조인해야 한다. 초안에서는 raw SQL 상수 두 개로
전체 목록/단건 목록을 나눴지만, 사용자 피드백에 따라 이 조회도 SQLAlchemy Core
statement로 전환했다.

## 반영 내용

- `VIEW_TABLE_METADATA_SELECT_SQL`, `VIEW_TABLE_METADATA_SELECT_BY_NAME_SQL` raw SQL 상수를 제거했다.
- `build_view_table_metadata_select_statement(name)`에서 SQLAlchemy Core `select()` + `outerjoin()`으로 메타데이터 조회를 생성한다.
- `asyncpg`의 nullable bind parameter 타입 추론 문제를 raw SQL 분기로 우회하지 않고, Core statement에 `WHERE analytics_view_tables.name = :name_1`를 조건부로 붙이는 방식으로 해결했다.
- View table 생성/갱신은 writer session으로 수행하고, SQL Lab/Chart Builder에서 읽을 수 있도록 `analytics_reader` role에 `GRANT SELECT`를 적용한다.
- frontend analytics proxy에 누락되어 있던 nested route를 추가했다.
  - `GET/POST /api/analytics/view-tables`
  - `POST /api/analytics/view-tables/preview`

## 검증 결과

- `make ci` 통과: 166 tests passed.
- frontend 검증 통과:
  - `npm run typecheck`
  - `npm run lint`
  - `npm run build`
  - `npm audit --omit=dev --audit-level=moderate` → 0 vulnerabilities.
- 보안/구성 검증 통과:
  - `uvx bandit -r backend/app event_generator -x backend/tests,event_generator/tests -q`
  - `docker compose config --quiet`
  - `git diff --check`
- live Docker E2E 통과:
  - events 데이터 존재 확인
  - view table preview 성공
  - `user_event_type_counts_e2e` 저장 성공
  - 저장된 view table SQL Lab 조회 성공
  - Chart Builder structured JOIN query 성공
- 실제 브라우저 QA 통과:
  - View Tables 화면에서 preview/save 수행
  - 저장된 `browser_user_event_type_counts` dataset을 Charts에서 선택
  - `event_type_counts`와 `event_type` 기준 INNER JOIN 구성
  - chart 실행 성공 및 결과 row 표시 확인
  - screenshot: `/tmp/lda_view_tables_chart_join_qa.png`
- DB 확인:
  - `analytics_view_tables` metadata table 존재
  - `user_event_type_counts_e2e`, `browser_user_event_type_counts` view 존재
  - 두 saved view 모두 `analytics_reader`에 `SELECT` 권한 부여됨

## 남은 리스크

- View table source SQL 자체는 여전히 Superset-style raw SELECT 입력이므로 기존 SQL policy와 DB 권한/timeout guardrail에 의존한다.
- Chart Builder JOIN은 현재 1-hop JOIN만 지원한다.
- 브라우저 QA는 headless Chrome smoke 수준이며, 픽셀 단위 디자인 비교는 수행하지 않았다.

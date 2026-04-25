# 2026-04-25 development timeline

오늘 작업 기록은 파일 수가 많아져 기능별 폴더로 분리했다.

## Folders

- `00_coordination/`: branch, ralph/push plan, compose 실행 이슈처럼 작업 흐름을 관리한 기록
- `01_event_generator/`: 이벤트 생성 시간 분포와 날짜 범위 설계
- `02_storage_backend/`: Step 2 저장소, backend analytics API, schema/API 설계
- `03_frontend_visualization/`: Superset-style 화면, Chart Builder, SQL Lab UX, chart/table 렌더링
- `04_sql_security/`: SQL Lab raw SQL guardrail, read-only role, proxy 보안, 보안 리뷰 후속 조치
- `05_database_scope/`: 다중 DB 확장 검토, connection UI 검토 이력, Connections 기능 삭제 결정
- `06_view_tables_chart_join/`: 사용자 생성 view table, Chart Builder 1-hop JOIN, E2E/browser QA 기록
- `07_submission_docs/`: 제출용 README 섹션, screenshot placeholder, 검증 checklist 정리

## Current scope decision

최신 제출 범위는 DB connection 관리 플랫폼이 아니라 Chart Builder + SQL Lab + View Tables 중심이다.
사용자는 `View Tables`에서 검증된 SELECT를 저장하고, `Charts`에서 generated/saved dataset과
최대 1개 JOIN을 사용해 table/chart를 확인한다. 제출 문서 관점의 최신 정리는
`07_submission_docs/23_readme_submission_pack.md`에 기록한다.

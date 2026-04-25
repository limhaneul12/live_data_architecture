# 2026-04-25 development timeline

오늘 작업 기록은 파일 수가 많아져 기능별 폴더로 분리했다.

## Folders

- `00_coordination/`: branch, ralph/push plan, compose 실행 이슈처럼 작업 흐름을 관리한 기록
- `01_event_generator/`: 이벤트 생성 시간 분포와 날짜 범위 설계
- `02_storage_backend/`: Step 2 저장소, backend analytics API, schema/API 설계
- `03_frontend_visualization/`: Superset-style 화면, Chart Builder, SQL Lab UX, chart/table 렌더링
- `04_sql_security/`: SQL Lab raw SQL guardrail, read-only role, proxy 보안, 보안 리뷰 후속 조치
- `05_database_scope/`: 다중 DB 확장 검토, connection UI 검토 이력, Connections 기능 삭제 결정

## Current scope decision

최신 결정은 `05_database_scope/19_remove_connections_feature.md`다. 현재 v1 범위는
DB connection 관리 플랫폼이 아니라 Chart Builder + SQL Lab + generated table allowlist 중심이다.

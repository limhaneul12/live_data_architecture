# Remaining work

작성일: 2026-04-25
대상: 이벤트 생성 → 저장 → 분석 → 시각화 과제의 현재 남은 작업 정리

## 1. 현재 완료된 작업 요약

아래 항목은 현재 완료된 것으로 봅니다.

### 1.1 Backend foundation

- Python 3.12.10 / uv / Makefile 기반 backend 환경 구성
- Ruff / Pyrefly / pytest / guardrails를 포함한 `make ci`
- FastAPI 기본 앱과 Docker Compose 구성
- JSON logging formatter
- Pydantic 기반 logging schema
- Pydantic 기반 health schema
- schema 중앙화: `backend/app/platform/schemas/`
- `orjson` 기반 JSON 직렬화 helper
- request id / trace id logging 필드
- `/health/live` 정상 요청 app-level logging skip
- `/health/live`, `/health/ready`, `/health/heartbeat`
- process-local app lifecycle state
- app 기준 수동 drain 상태 표현
- error stack 환경별 출력 정책
- OpenTelemetry 최소 mapping 초안
- dynamic attribute guardrail: `getattr`, `hasattr`
- lazy import guardrail
- broad type guardrail
- drain / 500 error / logging 관련 정책 문서화
- `platform/`과 `shared/` 역할 분리
- `platform/config`와 `pydantic-settings` 기반 설정 중앙화

### 1.2 Assignment pipeline

- Step 1 이벤트 생성기 — 완료 (`event_generator/`, `fect/event-generator`)
- Step 2 저장 구조/스키마 — 완료 (`events` table, Redis Streams transport, FastAPI consumer, `fect/step2-event-storage-analytics`)
- Step 3 집계 분석 — 완료 (`/analytics/datasets`, `/analytics/presets`, `/analytics/query`, generated views, SQL allowlist, read-only SQL hardening)
- Step 4 Docker 실행 — 완료권 (`docker-compose.yml`에 app/db/redis/event-generator/frontend 포함)
- Step 5 시각화 — 완료권 (`frontend/` Next.js Superset-style Explore/SQL Lab, table + chart preview)

## 2. 현재 의도적으로 멈춘 범위

과제 v1에서는 아래 범위를 의도적으로 제외합니다.

- Superset급 dashboard 저장/권한/drag-and-drop builder
- dashboard 저장 / query history
- 인증 / 사용자별 권한
- Kafka / Redpanda / Kafka Connect
- OpenTelemetry exporter 연결
- metric / alert 실제 도입
- 500 error 기반 자동 drain
- 일반 요청 강제 503 middleware
- fatal exception taxonomy
- automatic recovery
- Redis/shared lifecycle coordination 고도화

이유:

- 과제 필수 요구사항은 작은 이벤트 파이프라인 구현과 SQL 집계 결과 시각화입니다.
- 현재 구현은 generator → Redis Streams → FastAPI consumer → PostgreSQL → analytics API → Next.js visualization까지 핵심 흐름을 이미 충족합니다.
- 위 항목을 지금 넣으면 제출 범위를 넘어 복잡도가 과하게 커집니다.

## 3. 실제로 남은 작업

### 3.1 제출용 README 최종 정리

README에서 아래를 더 명확하게 정리하면 제출 완성도가 올라갑니다.

- Step 1~5 요구사항별 충족 위치
- `docker compose up --build` 실행 방법
- 기본 host port
  - PostgreSQL: `15432 -> 5432`
  - Redis: `16379 -> 6379`
- 예시 SQL 2개 이상
- 시각화 방식 설명
- 안전한 SQL 제한 정책 요약
  - generated view allowlist
  - function/join/subquery/CTE 거부
  - SELECT INTO / locking read 거부
  - OFFSET / DISTINCT / TABLESAMPLE / GROUP BY / ordinal ORDER BY 거부
  - SQL text length / row limit + PostgreSQL timeout

### 3.2 제출용 증빙 수집

아래 증빙을 남기면 좋습니다.

- `docker compose up --build` 성공 로그
- `GET /health/ready` 결과
- event generator가 Redis로 이벤트를 보낸 로그
- PostgreSQL `events` count 증가 확인
- `/analytics/query` 결과
- frontend Superset-style Explore 화면 스크린샷
- SQL Lab 실행 후 chart/table 표시 스크린샷
- unsafe SQL이 400으로 거부되는 예시

### 3.3 브랜치/PR 정리

현재 작업 브랜치는 아래 순서로 merge하는 것이 자연스럽습니다.

1. `fect/event-generator`
2. `fect/step2-event-storage-analytics`
3. `fect/frontend-event-analytics`
4. `fix/analytics-sql-security-hardening`
5. `fect/superset-analytics-ui`

`fect/superset-analytics-ui`는 SQL 보안 hardening branch 위에 쌓인 frontend polish 브랜치입니다.

### 3.4 선택 보강

필수는 아니지만 제출 신뢰도를 더 올리고 싶으면 아래를 추가할 수 있습니다.

- Playwright 기반 browser smoke test
- frontend 스크린샷 자동 저장 스크립트
- README에 제출용 이미지 경로 추가
- chart preview 디자인 polish 추가 반복

## 4. 지금 당장 하지 않는 것이 좋은 작업

아래는 지금 당장 하지 않는 것이 좋습니다.

- 인증
- dashboard 저장
- query history
- Kafka / Redpanda 전환
- Kafka Connect 유사 기능 구현
- OpenTelemetry exporter 연결
- metric / alert 시스템 도입
- 500 error 기반 자동 drain 재도입
- Redis/shared lifecycle coordination
- automatic recovery

현재는 과제 핵심 흐름을 제출 가능한 형태로 정리하는 것이 우선입니다.

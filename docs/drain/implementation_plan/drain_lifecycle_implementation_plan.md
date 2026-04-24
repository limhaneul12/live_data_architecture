# App drain lifecycle implementation plan

작성일: 2026-04-24  
대상: FastAPI backend app-level lifecycle / health endpoint 구현

## 1. 목적

이 문서는 현재 구현된 app 기준 drain/lifecycle 범위를 설명한다.
DB 기반 운영 drain 자동화는 아직 구현하지 않는다. 다만 이벤트 수집 경로의 Redis와 PostgreSQL dependency status는 health 응답에 포함한다.

## 2. 구현 범위

구현된 것:

- process-local in-memory lifecycle state
- `/health/live`
- `/health/live`
- `/health/ready`
- `/health/heartbeat`
- app 기준 running/draining/stopping 상태 표현
- Redis dependency status 표현
- PostgreSQL database dependency status 표현
- 정상 healthcheck request log skip

구현하지 않은 것:

- unhandled exception threshold drain
- lifecycle event log
- 일반 요청 강제 503

## 3. 코드 위치

```text
backend/app/platform/lifecycle/state.py
backend/app/platform/health_router.py
backend/app/platform/schemas/health_schema.py
backend/app/platform/middleware/request_logging.py
backend/app/main.py
```

## 4. 현재 lifecycle 책임

`LifecycleState`는 app 자체 상태만 관리한다.

- `starting`
- `running`
- `draining`
- `stopping`

저장하는 값:

- `started_at`
- `status`
- `redis_status`
- `database_status`
- `drain_started_at`
- `drain_reason`

저장하지 않는 값:

- exception counter
- sliding window
- lifecycle event history

## 5. 미래 재검토 항목

실제 서비스 로직과 운영 요구가 커지면 아래를 재검토한다.

- DB readiness checker 심화 정책
- short-lived failure counter
- unhandled exception threshold drain
- lifecycle/drain event history
- fatal exception taxonomy
- general request 강제 503 여부

## 6. 완료 조건

현재 완료 조건:

- `make ci` 통과
- `/health/live` 200
- `/health/ready` running 200 / draining 503 / redis unavailable 503 / database unavailable 503
- `/health/heartbeat` app lifecycle와 Redis/PostgreSQL dependency status 포함
- 500 error가 lifecycle을 자동 변경하지 않음
- 정상 healthcheck request log skip

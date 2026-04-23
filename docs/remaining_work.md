# Remaining work

작성일: 2026-04-24  
대상: 실제 서비스 로직 구현 전, 현재 시점에서 남겨둔 후속 작업 정리

## 1. 현재 완료된 작업 요약

아래 항목은 현재 완료된 것으로 봅니다.

- Python 3.12.10 / uv / Makefile 기반 backend 환경 구성
- Ruff / Pyrefly / pytest / guardrails를 포함한 `make ci`
- FastAPI 기본 앱과 Docker Compose 구성
- JSON logging formatter
- Pydantic 기반 logging schema
- Pydantic 기반 health schema
- schema 중앙화: `backend/app/platform/schemas/`
- `orjson` 기반 JSON 직렬화 helper
- request id / trace id logging 필드
- `/health` 정상 요청 app-level logging skip
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

## 2. 현재 의도적으로 멈춘 범위

현재는 운영 기반을 여기서 한 번 멈추고, 실제 서비스 로직으로 넘어가는 것이 맞다고 판단했습니다.

의도적으로 하지 않는 것:

- 500 error 기반 자동 drain
- 일반 요청 강제 503 middleware
- fatal exception taxonomy
- DB checker 선구현
- OpenTelemetry exporter 연결
- metric / alert 실제 도입

추가로, logging 내부 구조(`JsonLogServiceContext` 등)와 request logging 함수 시그니처는 현재 단계에서 더 줄이지 않고 유지합니다.  
지금은 관측성 기초가 실제 서비스 로직보다 앞서가지 않도록 여기서 멈추는 편이 낫다고 판단했습니다.

## 3. 실제로 남은 작업

### 3.1 서비스 로직 구현

가장 우선순위가 높은 다음 작업입니다.

권장 순서:

1. 이벤트 생성기
2. 저장 구조/스키마
3. 집계 분석
4. compose 기반 자동 실행
5. 시각화

### 3.2 DB 사용 방식 확정 이후 health 재검토

DB를 실제로 사용하게 되면 아래를 다시 봐야 합니다.

- DB connection / session / pool 방식
- `/health/ready`에 DB 상태를 반영할지
- `/health/heartbeat`에 DB 상태를 반영할지
- DB fail이 readiness에 어떤 영향을 주는지

### 3.3 Drain 상태에서 일반 요청 강제 503 여부

현재 정책은 readiness 503으로만 새 트래픽에서 빠지는 방식입니다.
실제 운영 라우팅 방식이 정해지면, non-health 요청을 앱 레벨에서 503으로 막을지 다시 판단해야 합니다.

### 3.4 Error stack 운영 정책 고도화

현재 구현:

```text
local / stage: error.stack 포함
prod: error.stack 빈 문자열
```

운영 전에는 아래를 더 검토해야 합니다.

- stack 길이 제한
- PII redaction
- sampling
- logger별 정책

### 3.5 Git 정리 / commit

현재 변경량이 크기 때문에, 실제 서비스 로직을 시작하기 전에 한 번 commit 단위를 정리하는 것이 좋습니다.

## 4. 추천 다음 작업 순서

현재 운영 foundation 관점에서는 여기서 잠시 멈추는 것이 맞습니다.
이제는 observability 확장이 아니라 실제 서비스 로직으로 넘어가는 것을 권장합니다.

추천 순서:

1. 이벤트 생성기
2. 저장 구조/스키마
3. 집계 분석
4. compose 기반 자동 실행
5. 시각화

## 5. 지금 당장 하지 않는 것이 좋은 작업

아래는 지금 당장 하지 않는 것이 좋습니다.

- DB checker 선구현
- OpenTelemetry exporter 연결
- metric / alert 시스템 도입
- 500 error 기반 자동 drain 재도입
- Redis/shared lifecycle coordination
- automatic recovery

이유:

- 아직 실제 서비스 로직의 failure mode가 없습니다.
- 아직 운영 스택과 오케스트레이션 정책이 확정되지 않았습니다.
- 지금 구현하면 추상화나 설정이 앞서갈 가능성이 높습니다.
- 현재는 app 기준 lifecycle과 최소 observability foundation을 안정화하는 단계입니다.

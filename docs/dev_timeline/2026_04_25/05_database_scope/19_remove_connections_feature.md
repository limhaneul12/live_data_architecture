# 19. Connections 기능 삭제 및 analytics router 정리

## 배경

Connections 화면과 DB 주소 연결 테스트는 실제 과제 핵심인 이벤트 생성 → 저장 → 분석 →
시각화보다 분석 플랫폼/DB 연결 관리 기능처럼 보이는 표면을 만들었다. 사용자는 기능 범위를
줄이고 Chart Builder와 SQL Lab 중심으로 되돌리기로 결정했다.

## 삭제한 범위

- frontend top navigation의 `Connections` 항목 삭제
- Connections 화면, DB address 입력 form, connection test 결과 UI 삭제
- Next.js proxy의 `/api/analytics/connection-test` route 삭제
- backend `/analytics/connection` endpoint 삭제
- backend `/analytics/connection-test` endpoint 삭제
- connection metadata/probe domain/application/infrastructure 코드와 테스트 삭제

## 유지한 범위

- `Charts`: `/analytics/explore-query` structured endpoint로 SQLAlchemy Core SELECT 생성
- `SQL Lab`: raw SELECT 입력은 유지하되 backend SQL policy와 read-only guardrail 적용
- `Available tables`: SQL Lab 안에서 generated table/column 목록 제공
- backend 내부 analytics DB 주소 선택은 `.env`/config 기반으로 유지

## Router 규칙 보강

Connections 삭제 중 backend router 규칙 미준수도 함께 정리했다.

- `event_analytics/interface/schemas/` package를 만들고 analytics/event schemas를 분리했다.
- router endpoint에 `response_model`, `summary`, `description`, error response model을 명시했다.
- `app/container.py`, `event_analytics/containers.py`를 추가해 root container와 bounded-context container를 분리했다.
- root container가 analytics SQLAlchemy engine/session factory lifecycle을 `providers.Resource`/`providers.Singleton`으로 소유하도록 정리했다.
- route handler가 직접 service instance를 closure로 쓰지 않도록 `dependency_injector` `Provide[Container.event_analytics.*]` 기반 DI로 변경했다.
- router의 직접 `try/except` JSON 변환을 제거하고 `shared/exceptions/exception_decorators.py`의 decorator로 예외를 HTTP payload로 변환한다.
- OpenAPI `responses`는 route에 남기되 SQL Lab/Explore별 설명을 분리했고, runtime error body는 `AnalyticsErrorPayload.from_exception()` 한 경로로 직렬화한다.
- event analytics 예외는 `shared/exceptions/event_analytics_exceptions.py`에 모았다.

## Code review 후속

`$code-review`에서 두 가지 watch가 나왔다.

1. DI가 반쪽 적용이면 새 dependency 비용만 생긴다는 지적
   - 조치: `main.py`에서 직접 engine/session factory를 만들던 부분을 제거하고 root
     container resource로 이동했다.
2. error response schema와 decorator dict가 drift될 수 있다는 지적
   - 조치: `AnalyticsQueryErrorPayload`를 더 넓은 `AnalyticsErrorPayload`로 정리하고
     decorator는 router가 넘긴 schema serializer를 사용하도록 변경했다.

## 의도

이번 변경은 “DB connection 관리 플랫폼”이 아니라 “과제 요구사항을 만족하는 작은 이벤트
분석 파이프라인”으로 범위를 되돌리는 작업이다. 외부 DB 연결 생성/저장/전환을 다시 넣으려면
별도 보안 설계, credential 저장 정책, tenant/permission 정책이 먼저 필요하다.

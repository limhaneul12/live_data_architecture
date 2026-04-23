# 02. Logging foundation 구축

## 무엇을 했는지

이 단계에서는 backend 전체에서 **같은 JSON logging format**을 사용하도록 기반을 정리했습니다.
단순히 로그를 JSON으로 출력하는 것에 그치지 않고, request id / trace id / HTTP 결과 / 예외 구조가 같은 필드 이름으로 남도록 맞췄습니다.

정리한 핵심 항목은 아래와 같습니다.

- `event`, `level`, `msg` 같은 공통 로그 필드
- `request_id`, `trace_id`, `span_id` 같은 상관관계 필드
- `http_method`, `path`, `status_code`, `duration_ms` 같은 요청 결과 필드
- 예외 발생 시 `error.type`, `error.message`, `error.stack` 구조
- health / ready / heartbeat 응답 형식의 일관성

## 어떤 포맷으로 만들었는지

현재 request log는 대략 아래처럼 출력됩니다.

```json
{
  "ts": "2026-04-24T00:00:00.123+00:00",
  "level": "INFO",
  "logger": "app.platform.middleware.request_logging",
  "event": "request_completed",
  "msg": "request completed",
  "func": "app.main.get_health",
  "duration_ms": 2.14,
  "service": "live-data-api",
  "env": "local",
  "version": "0.1.0",
  "request_id": "req-123",
  "correlation_id": "req-123",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "tracer_error": null,
  "http_method": "GET",
  "path": "/health",
  "status_code": 200,
  "error": null
}
```

예외 로그는 같은 형태를 유지하면서 `error` 블록만 채워집니다.

```json
{
  "level": "ERROR",
  "event": "request_failed",
  "msg": "request failed",
  "status_code": 500,
  "error": {
    "type": "ValueError",
    "message": "boom",
    "stack": "Traceback ..."
  }
}
```

## 왜 이 포맷을 선택했는지

이번 단계에서 가장 중요하게 본 것은 **모든 모듈이 같은 로그 형식을 쓰게 만드는 것**이었습니다.
모듈마다 필드 이름이 다르면 로그는 남아 있어도 검색과 집계가 어려워지고, 에러가 났을 때 request 흐름을 따라가기가 매우 힘들어집니다.

그래서 아래 기준으로 포맷을 잡았습니다.

### 1. 먼저 "무슨 일인지"가 보여야 합니다

- `event`: 기계가 집계할 수 있는 이름
- `msg`: 사람이 읽는 설명
- `level`: 심각도

이 세 개를 앞쪽에 두면, 로그 한 줄만 봐도

```text
무슨 이벤트인지
성공/실패인지
사람이 읽는 설명이 무엇인지
```

를 바로 파악할 수 있습니다.

### 2. 그 다음 "어떤 요청인지"가 보여야 합니다

- `request_id`
- `trace_id`
- `span_id`
- `http_method`
- `path`
- `status_code`

이 필드들은 나중에 장애가 났을 때

```text
어떤 요청이었는지
어느 경로였는지
다른 로그와 어떻게 연결되는지
```

를 찾기 위해 넣었습니다.

### 3. 마지막에 상세 맥락을 둡니다

- `duration_ms`
- `func`
- `service`
- `env`
- `version`
- `tracer_error`
- `error`

이 필드들은 상세 디버깅용입니다.
즉, 한 줄을 처음 읽을 때는 앞쪽 필드만 봐도 요지가 보이고, 더 파고들고 싶을 때 뒤쪽 필드를 보면 되도록 의도했습니다.

## 왜 이게 가독성이 좋다고 봤는지

제가 고민한 포인트는 "예쁘게 JSON처럼 보이게 하는 것"이 아니라 **사람이 로그를 훑을 때 읽는 순서**였습니다.

사람은 보통 로그를 볼 때 이렇게 봅니다.

1. 에러인가, 정보인가?
2. 무슨 이벤트인가?
3. 어느 요청인가?
4. 어떤 경로인가?
5. 왜 실패했는가?

그래서 그 순서에 맞게 필드를 유지하려고 했습니다.

- `level`, `event`, `msg`를 앞에 둠
- `request_id`, `trace_id`, `path`, `status_code`를 그 다음에 둠
- `error`와 세부 필드는 뒤에 둠

즉, **로그 한 줄을 왼쪽에서 오른쪽으로 읽을 때 자연스럽게 상황이 펼쳐지도록** 설계한 것입니다.

## 구현하면서 실제로 고민한 부분

이번 작업에서 가장 많이 고민한 부분은 **운영 기반을 어디까지 먼저 만들 것인지**였습니다.
초기에는 drain, lifecycle, OpenTelemetry, dependency health를 더 많이 넣을 수도 있었지만, 아직 실제 서비스 로직이 없는 단계에서 과하게 앞서가는 것은 오히려 유지보수 부담이 된다고 판단했습니다.

그래서 현재는 다음 범위까지만 유지합니다.

- JSON formatter
- request / trace 상관관계
- 공통 필드 이름 통일
- error payload 구조 통일
- 최소 OTEL mapping 초안

반대로 아래는 일단 여기서 멈췄습니다.

- 실제 exporter/collector 연동
- metric / alert 시스템
- 과한 runtime drain 자동화
- DB/Redis dependency 기반 health 확장

## 관련 문서

- `docs/logging_structure/logging_refactoring_plan.md`
- `docs/logging_structure/logging_trace_context_policy.md`
- `docs/logging_structure/logging_error_stack_policy.md`
- `docs/logging_structure/logging_otel_mapping_policy.md`

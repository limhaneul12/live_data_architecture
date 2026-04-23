# Logging trace context policy

작성일: 2026-04-24  
대상: request logging의 `trace_id`, `span_id`, `x-trace-id`, `traceparent` 처리 정책

## 1. 목적

이 문서는 backend request logging에서 trace context를 어떤 우선순위로 결정할지 정의한다.
목표는 OpenTelemetry/W3C Trace Context와 호환되면서도 기존 custom `x-trace-id` 헤더를 fallback으로 유지하는 것이다.

## 2. 공식 기준 요약

### 2.1 W3C Trace Context

W3C Trace Context는 HTTP trace 전파 표준 헤더로 `traceparent`를 정의한다.
`traceparent`는 아래 4개 필드를 하이픈으로 연결한다.

```text
version-trace-id-parent-id-trace-flags
```

초기 검증 기준:

- field 개수는 4개여야 한다.
- version은 2자리 hex여야 한다.
- version `ff`는 허용하지 않는다.
- trace-id는 32자리 hex여야 한다.
- trace-id는 all-zero이면 안 된다.
- parent-id는 16자리 hex여야 한다.
- parent-id는 all-zero이면 안 된다.
- trace-flags는 2자리 hex여야 한다.

### 2.2 OpenTelemetry context propagation

OpenTelemetry는 W3C Trace Context 기반 propagation을 기본 표준으로 사용한다.
서비스 간 causal context를 이어가기 위해 `traceparent`에서 trace id와 parent span id를 추출한다.

## 3. 우선순위

Trace context 결정 우선순위는 다음으로 한다.

```text
1. valid traceparent header
2. active OpenTelemetry span context
3. x-trace-id fallback
4. no trace context
```

## 4. 각 source의 의미

### 4.1 `traceparent`

가장 신뢰하는 표준 전파 source다.

- `trace_id`: traceparent의 trace-id
- `span_id`: traceparent의 parent-id

주의:

- 여기서 span_id는 현재 서버 span id가 아니라 incoming parent id다.
- 실제 OpenTelemetry SDK 연동 후에는 서버 span 생성 시 새 span id가 생길 수 있다.
- 현재 logging 단계에서는 incoming context correlation 용도로 parent-id를 span_id에 넣는다.

### 4.2 active OpenTelemetry span

`trace.get_current_span()`에서 유효한 span context가 있으면 사용한다.

- zero-code instrumentation 또는 middleware가 이미 span을 만든 경우 유효할 수 있다.
- 이 경우 active span의 trace_id/span_id를 사용한다.

### 4.3 `x-trace-id`

custom fallback이다.

- W3C `traceparent`가 없고 active span도 없을 때만 사용한다.
- `x-trace-id`는 trace id만 제공하므로 span_id는 None이다.
- 이 값은 표준 trace context가 아니라 app-local compatibility header로 본다.

### 4.4 no trace context

모든 source가 없거나 유효하지 않으면 trace_id/span_id는 None이다.
request correlation은 `x-request-id`로 유지한다.

## 5. invalid traceparent 처리

invalid `traceparent`는 무시한다.

정책:

- invalid traceparent 때문에 request를 실패시키지 않는다.
- invalid traceparent는 active span 또는 x-trace-id fallback을 막지 않는다.
- 필요하면 나중에 debug/warning metric으로 관측한다.

## 6. request id와 trace id의 경계

`request_id`와 `trace_id`는 다른 목적을 가진다.

- `request_id`: 단일 HTTP request를 식별하는 app-local correlation id
- `trace_id`: 분산 trace 전체를 식별하는 trace correlation id

따라서 trace context가 없다고 request_id를 trace_id에 복사하지 않는다.

## 7. response header 정책

현재 response에는 최종 선택된 trace_id가 있으면 `x-trace-id`로 내려준다.

주의:

- `x-trace-id` response header는 편의용이다.
- 표준 trace context 전파는 `traceparent`가 담당한다.
- 실제 OpenTelemetry SDK/exporter 연동 후에는 response propagation 정책을 재검토한다.

## 8. 테스트 기준

테스트는 다음을 검증한다.

- valid traceparent가 있으면 traceparent의 trace-id/parent-id를 사용한다.
- traceparent와 x-trace-id가 모두 있으면 traceparent가 우선한다.
- invalid traceparent는 무시하고 x-trace-id fallback을 사용한다.
- x-trace-id만 있으면 trace_id로 사용하고 span_id는 None이다.
- trace context가 없으면 trace_id/span_id는 None이다.
- response `x-trace-id`는 최종 trace_id를 반영한다.

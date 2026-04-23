# Logging OpenTelemetry mapping policy

작성일: 2026-04-23  
대상: `JsonLogPayload` → OpenTelemetry-friendly log mapping

## 1. 목적

이 문서는 현재 JSON log payload를 나중에 OpenTelemetry log/event/attribute로 보낼 때 어떤 필드로 매핑할지 정의한다.
이번 단계에서는 exporter를 붙이지 않고, 반드시 필요한 최소 mapping 함수와 테스트 가능한 계약만 만든다.

## 2. 참고한 공식 기준

OpenTelemetry 공식 문서 기준:

- Logs Data Model
  - `SeverityText`는 기존 log level 문자열에 해당한다.
  - `Body`는 structured log의 의미를 보존할 수 있어야 한다.
  - log record는 trace id, span id와 연결될 수 있다.
- HTTP semantic conventions
  - HTTP method는 `http.request.method`를 사용한다.
  - HTTP response status code는 `http.response.status_code`를 사용한다.
  - request path는 URL 관련 attribute로 매핑한다.
- Exception semantic conventions
  - exception type/message/stacktrace를 별도 attribute로 매핑할 수 있다.
  - stacktrace는 민감정보를 포함할 수 있으므로 기존 stack policy를 따른다.
- General/resource attributes
  - service identity는 `service.name`, environment는 deployment environment 계열 attribute로 매핑한다.

## 3. 최소 매핑 원칙

### 3.1 exporter는 아직 붙이지 않는다

이번 단계에서는 OTEL exporter, collector, SDK logger provider를 설정하지 않는다.

이유:

- provider/exporter 선택은 배포 환경과 관측성 스택이 정해진 뒤 결정해야 한다.
- 지금은 payload schema와 최소 semantic mapping이 흔들리지 않게 하는 것이 목적이다.

### 3.2 기존 JSON log output은 유지한다

stdout JSON log는 계속 flat 구조를 유지한다.
OTEL mapping은 별도 변환 함수로 제공한다.

### 3.3 trace id / span id는 top-level mapping result에 둔다

OTEL Logs Data Model에서는 trace/span correlation이 별도 필드로 표현될 수 있다.
따라서 mapping result도 `trace_id`, `span_id`를 attributes와 분리한다.

### 3.4 attributes는 primitive value만 사용한다

초기 mapping은 다음 타입만 허용한다.

```text
str | int | float | bool
```

`None` 값은 attributes에서 제외한다.

## 4. 초기 필수 매핑

| JSON log field | OTEL-friendly target | 비고 |
|---|---|---|
| `ts` | `timestamp` | 문자열 그대로 유지. 실제 SDK 연동 시 datetime 변환 가능 |
| `level` | `severity_text` | Python logging level name |
| `msg` | `body` | log body/message |
| `trace_id` | `trace_id` | top-level result field |
| `span_id` | `span_id` | top-level result field |
| `service` | `attributes["service.name"]` | resource attribute 후보 |
| `env` | `attributes["deployment.environment.name"]` | deployment environment |
| `version` | `attributes["service.version"]` | service version |
| `event` | `attributes["event.name"]` | app-local event name |
| `request_id` | `attributes["app.request_id"]` | app-local request correlation |
| `http_method` | `attributes["http.request.method"]` | HTTP semconv |
| `path` | `attributes["url.path"]` | query 제외 path |
| `status_code` | `attributes["http.response.status_code"]` | HTTP semconv |
| `error.type` | `attributes["exception.type"]` | exception semconv |
| `error.message` | `attributes["exception.message"]` | exception semconv |
| `error.stack` | `attributes["exception.stacktrace"]` | stack policy 적용 후 값 |
| `lifecycle` | `attributes["app.lifecycle"]` | lifecycle event일 때만 |
| `drain_reason` | `attributes["app.drain_reason"]` | lifecycle event일 때만 |

## 5. 보류 mapping 후보

아래 필드는 현재 JSON log에는 있지만, 초기 OTEL mapping 계약에는 넣지 않는다.
필요성이 생기면 별도 근거와 테스트를 추가한 뒤 승격한다.

| JSON log field | 보류 이유 |
|---|---|
| `logger` | log source 이름은 유용하지만 초기 OTEL 필수 분석축은 아님 |
| `func` | `code.function` semantic 적용 범위를 더 검토해야 함 |
| `duration_ms` | 정식 metric 또는 span duration과의 관계를 먼저 정해야 함 |
| `correlation_id` | 현재 request_id와 동일하게 쓰는 경로가 많아 중복 가능 |
| `tracer_error` | tracer instrumentation 자체 오류 정책이 더 필요함 |
| `error_count` | lifecycle drain event 상세 필드. 초기에는 drain_reason만 매핑 |
| `window_seconds` | threshold 상세 필드. 초기에는 drain_reason만 매핑 |
| `last_error_at` | lifecycle 상세 timestamp. 초기에는 payload JSON에는 유지하되 OTEL mapping은 보류 |
| `drain_started_at` | lifecycle 상세 timestamp. 초기에는 payload JSON에는 유지하되 OTEL mapping은 보류 |

## 6. 의도적으로 하지 않는 것

- OTEL exporter 설정
- collector 설정
- trace/span id 검증
- severity number 계산
- duration을 정식 metric으로 변환
- nested JSON body 전송
- PII redaction
- 보류 mapping 후보의 선제 매핑

## 7. 테스트 기준

테스트는 다음을 검증한다.

- `severity_text == level`
- `body == msg`
- `trace_id`, `span_id`가 top-level result에 유지됨
- service/env/version이 OTEL-friendly attribute로 매핑됨
- event/request id가 최소 app-local attribute로 매핑됨
- HTTP method/path/status code가 semantic convention key로 매핑됨
- error payload가 exception attribute로 매핑됨
- lifecycle event에서는 lifecycle/drain_reason만 app-local attribute로 매핑됨
- `None` 값은 attributes에서 제외됨
- 보류 후보 필드는 attributes에 들어가지 않음

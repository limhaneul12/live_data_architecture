# Logging cleanup implementation plan review request

Project: `/Users/imhaneul/Documents/sky_document/project/live_data_architecture`

## Goal

현재 FastAPI backend JSON logging 구조를 과하지 않게 정리하려고 합니다.  
아래 변경 계획이 적절한지 검토해주세요.

코드 변경은 하지 말고, 계획 리뷰만 해주세요.  
한국어로 답변해주세요.

---

## Current context

현재 주요 파일:

```text
backend/app/main.py
backend/app/platform/logging/formatter/config.py
backend/app/platform/logging/payloads.py
backend/app/platform/logging/context/http_request.py
backend/app/shared/types/extra_types.py
backend/app/shared/serialization/orjson_codec.py
```

현재 특징:

- JSON logging은 `JsonFormatter`가 담당합니다.
- `LogRecord`를 `JsonLogPayload` Pydantic 모델로 변환한 뒤 `orjson`으로 출력합니다.
- `JsonLogPayload`는 내부적으로 service/trace/http/error context로 나뉘고, stdout JSON은 flat 구조로 출력합니다.
- `SERVICE_APP_NAME`, `SERVICE_APP_ENV`, `SERVICE_APP_VERSION`은 필수 env입니다.
- `/health/live` endpoint가 있습니다.
- uvicorn access log는 꺼져 있지만 app middleware JSON log는 `/health/live`도 찍을 가능성이 있습니다.
- `backend/app/shared/types/extra_types.py`에는 현재 `JSONObject`, `JSONValue`와 함께 `LogRecord` extra extraction helper들이 같이 있습니다.

---

## Proposed changes

### 1. Move LogRecord extra helpers out of `shared/types`

현재:

```text
backend/app/shared/types/extra_types.py
```

안에 아래가 같이 있음:

```python
type JSONObject = dict[str, JSONValue]
type JSONValue = ...

log_record_extra_str(...)
log_record_extra_str_or_default(...)
log_record_extra_float(...)
log_record_extra_int(...)
```

변경 후:

```text
backend/app/shared/types/extra_types.py
```

에는 타입 alias만 남김:

```python
type JSONObject = dict[str, JSONValue]
type JSONValue = str | int | float | bool | None | list[JSONValue] | JSONObject
```

새 파일 생성:

```text
backend/app/platform/logging/record_extras.py
```

여기로 이동:

```python
log_record_extra_str(...)
log_record_extra_str_or_default(...)
log_record_extra_float(...)
log_record_extra_int(...)
```

이유:

- `JSONObject`, `JSONValue`는 shared type alias가 맞음.
- 하지만 `LogRecord` extra parsing은 logging-specific behavior라 `platform/logging`이 더 적절함.
- `shared/types`는 진짜 타입 alias 중심으로 유지.

---

### 2. Create service context once during logging configuration

현재 `backend/app/platform/logging/formatter/config.py`의 `_log_payload()`에서 매 로그마다 env를 읽음:

```python
service=JsonLogServiceContext(
    service=_required_env("SERVICE_APP_NAME"),
    env=_required_env("SERVICE_APP_ENV"),
    version=_required_env("SERVICE_APP_VERSION"),
)
```

변경 후:

`configure_logging()`에서 한 번만 읽고 검증:

```python
service_context = JsonLogServiceContext(
    service=_required_env("SERVICE_APP_NAME"),
    env=_required_env("SERVICE_APP_ENV"),
    version=_required_env("SERVICE_APP_VERSION"),
)
```

`JsonFormatter`에 주입:

```python
handler.setFormatter(JsonFormatter(service_context=service_context))
```

`JsonFormatter`는 생성자에서 service context를 받음:

```python
class JsonFormatter(logging.Formatter):
    def __init__(self, *, service_context: JsonLogServiceContext) -> None:
        super().__init__()
        self._service_context = service_context
```

`_log_payload()`는 service context를 파라미터로 받음:

```python
def _log_payload(
    *,
    record: logging.LogRecord,
    service_context: JsonLogServiceContext,
) -> JsonLogPayload:
    ...
```

이유:

- `SERVICE_APP_NAME`, `SERVICE_APP_ENV`, `SERVICE_APP_VERSION`은 process lifetime 동안 고정값.
- 매 로그마다 env lookup과 validation을 반복할 필요 없음.
- env 누락은 logging formatter hot path가 아니라 configure/bootstrap 시점에 fail-fast 하는 것이 더 명확함.
- fallback 기본값은 계속 사용하지 않음.

---

### 3. Keep Pydantic payload schema

유지:

```text
backend/app/platform/logging/payloads.py
```

유지할 모델:

```python
JsonLogServiceContext
JsonLogTraceContext
JsonLogHttpContext
JsonLogError
JsonLogPayload
```

유지할 정책:

```python
ConfigDict(extra="forbid", frozen=True, strict=True)
StrictStr
StrictInt
```

이유:

- 로그는 향후 OpenTelemetry event/attribute로 보낼 계획이 있음.
- 따라서 단순 dict보다 schema contract가 있는 편이 좋음.
- Pydantic은 여기서 internal domain state가 아니라 observability boundary contract로 사용됨.
- context 분리(service/trace/http/error)는 OpenTelemetry mapping에 유리함.

---

### 4. Keep flat JSON output

내부 모델은 context로 나뉘지만 stdout JSON은 flat 유지:

```json
{
  "ts": "...",
  "level": "INFO",
  "service": "live-data-api",
  "env": "local",
  "version": "0.1.0",
  "request_id": "...",
  "trace_id": "...",
  "http_method": "GET",
  "path": "/health/live",
  "status_code": 200,
  "error": null
}
```

이유:

- Loki/ELK/CloudWatch/grep 등에서 flat key 검색이 쉬움.
- 내부 context 분리와 외부 flat output의 장점을 둘 다 취할 수 있음.
- nested output으로 바꾸는 것은 지금 단계에서 이득보다 비용이 큼.

---

### 5. Add app-level `/health/live` logging skip

현재 uvicorn access log는 꺼졌지만, FastAPI middleware에서 `/health/live`도 `log_request_outcome()`를 탈 수 있음.

변경 후:

- `/health/live` 요청은 app-level JSON request log emission을 skip.
- 단, response header는 유지:
  - `x-request-id`
  - `x-trace-id` if available

예상 helper:

```python
HEALTHCHECK_PATHS = {"/health/live"}


def should_skip_request_log(path: str) -> bool:
    return path in HEALTHCHECK_PATHS
```

middleware flow:

```python
response = await call_next(request)

if not should_skip_request_log(request.url.path):
    log_request_outcome(...)

response.headers["x-request-id"] = request_id
...
return response
```

이유:

- healthcheck는 활성화하되 로그 노이즈는 피한다는 요구사항 충족.
- middleware 전체를 skip하지 않고, logging emission만 skip해서 header/trace 흐름은 유지.

---

### 6. Add tests for cleanup behavior

추가/보강할 테스트:

#### A. service context env required

- `SERVICE_APP_NAME`, `SERVICE_APP_ENV`, `SERVICE_APP_VERSION`이 설정되어 있으면 `JsonFormatter`가 생성됨.
- 누락되어 있으면 `configure_logging()` 또는 service context builder가 실패.

#### B. formatter uses injected service context

- `JsonFormatter(service_context=...)`로 만든 formatter가 출력 JSON에 service/env/version을 포함하는지 검증.

#### C. `/health/live` request log skip

- `/health/live` 요청 시 app-level `request_completed` log가 발생하지 않는지 검증.
- 단 `x-request-id` header는 여전히 존재해야 함.

#### D. non-health request still logs

- 예: `/not-found` 또는 테스트 전용 route 요청 시 로그가 발생하는지 검증.

---

### 7. Defer middleware extraction

아직 바로 하지 않을 것:

```text
backend/app/platform/logging/http_middleware.py
```

로 middleware를 옮기는 작업.

이유:

- 먼저 behavior cleanup(`/health/live` skip, env one-time injection)을 안정화.
- 테스트로 보호한 뒤 middleware 분리를 하면 리스크가 낮음.
- 지금 동시에 옮기면 diff가 커질 수 있음.

나중에 할 일:

```text
backend/app/main.py
```

에서 middleware 구현을 줄이고:

```text
backend/app/platform/logging/http_middleware.py
```

로 이동.

---

### 8. Defer error stack policy change

현재는 error log에 full stack 포함 유지.

나중에 별도 정책으로 검토:

- local/dev: full stack
- prod: full stack 유지 여부
- stack length limit
- PII redaction
- sampling
- OpenTelemetry exception attribute mapping

이유:

- 지금은 초기 개발 단계라 stack이 디버깅에 유용함.
- 운영 정책 없이 급하게 제거하면 장애 분석성이 떨어질 수 있음.
- 하지만 production 전에는 반드시 정책화 필요.

---

## Proposed implementation order

1. Move `log_record_extra_*` from `shared/types/extra_types.py` to `platform/logging/record_extras.py`.
2. Update imports.
3. Change `JsonFormatter` to receive `JsonLogServiceContext`.
4. Create service context once in `configure_logging()`.
5. Update tests for service context injection.
6. Add `/health/live` log emission skip while preserving headers.
7. Add test for `/health/live` no app-level request log.
8. Run `make ci`.
9. Leave middleware extraction and stack policy for next cleanup pass.

---

## Questions for review

Please review:

1. Is this cleanup order safe?
2. Should `/health/live` skip happen before or after service context injection?
3. Is `record_extras.py` a good module name, or would `log_record_extras.py` / `extra_fields.py` be better?
4. Is keeping Pydantic payload schema correct given future OpenTelemetry usage?
5. Is keeping flat JSON output correct?
6. Should error stack policy be deferred, or should a simple env gate be added now?
7. Are there risks around `configure_logging()` running at import time once it starts validating required env once?

Please answer in Korean.

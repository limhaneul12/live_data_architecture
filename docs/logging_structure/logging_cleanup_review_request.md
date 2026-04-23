# Logging cleanup review request

Date: 2026-04-23
Project: `live_data_architecture`
Scope: FastAPI backend JSON logging cleanup review

## Goal

현재 JSON logging 구조가 너무 과한지, 무엇을 유지하고 무엇을 줄여야 하는지 리뷰해주세요.
코드 변경은 하지 말고, 리뷰 결과만 한국어로 작성해주세요.

## Project rules

- Python 3.12.10
- Backend commands run through `make` and `uv`
- `make ci` includes Ruff, Pyrefly, guardrails, pytest
- Pydantic은 IO/boundary schema에 사용
- Domain/internal state에는 dataclass 선호
- `getattr`, `hasattr`, broad `Any`, broad `object`, `cast` 남용 금지
- JSON logging 통일
- 이후 OpenTelemetry 연동 예정
- healthcheck는 활성화하되 로그 출력은 피하고 싶음
- 기본값으로 버그를 숨기는 fallback 지양

## Files to inspect

Please inspect these files in this repository:

```text
backend/app/platform/logging/formatter/config.py
backend/app/platform/logging/payloads.py
backend/app/platform/logging/context/http_request.py
backend/app/shared/types/extra_types.py
backend/app/shared/serialization/orjson_codec.py
backend/app/main.py
backend/tests/test_logging_json.py
backend/tests/test_request_logging_headers.py
```

## Current structure summary

### `backend/app/platform/logging/formatter/config.py`

- Defines `JsonFormatter`.
- Converts `logging.LogRecord` into `JsonLogPayload`.
- Reads required service metadata from environment:
  - `SERVICE_APP_NAME`
  - `SERVICE_APP_ENV`
  - `SERVICE_APP_VERSION`
- Configures root logger with a JSON `StreamHandler`.
- Removes uvicorn handlers and propagates them to root.

### `backend/app/platform/logging/payloads.py`

- Defines Pydantic models for log schema:
  - `JsonLogServiceContext`
  - `JsonLogTraceContext`
  - `JsonLogHttpContext`
  - `JsonLogError`
  - `JsonLogPayload`
- Uses:
  - `ConfigDict(extra="forbid", frozen=True, strict=True)`
  - `StrictStr`
  - `StrictInt`
- Outputs flat JSON via `to_json_value()`.
- Internally models contexts separately for future OpenTelemetry mapping.

### `backend/app/platform/logging/context/http_request.py`

- Resolves request id.
- Resolves trace context from headers/OpenTelemetry.
- Records exceptions on current OpenTelemetry span.
- Provides `log_request_outcome()` and `log_request_exception()` helpers.

### `backend/app/shared/types/extra_types.py`

- Defines:
  - `JSONObject`
  - `JSONValue`
- Also includes typed `logging.LogRecord` extra extraction helpers:
  - `log_record_extra_str`
  - `log_record_extra_str_or_default`
  - `log_record_extra_float`
  - `log_record_extra_int`

### `backend/app/main.py`

- Creates FastAPI app.
- Calls `configure_logging()`.
- Defines request logging middleware inline.
- Defines `/health/live` endpoint.

## Current concerns to validate

Please evaluate whether these concerns are correct, partially correct, or wrong.

### Concern 1: `/health/live` app-level logging

`uvicorn --no-access-log` is enabled, but the FastAPI middleware may still log `/health/live` through app-level JSON logging.

Question:
- Should `/health/live` be skipped inside middleware?
- If yes, what is the cleanest minimal approach?

### Concern 2: required service env read per log

`SERVICE_APP_NAME`, `SERVICE_APP_ENV`, and `SERVICE_APP_VERSION` have no fallback now, which is intentional.
However, they may be read every time a log record is formatted.

Question:
- Is this too much work on the hot path?
- Should service context be built once during `configure_logging()` and injected into `JsonFormatter`?

### Concern 3: `shared/types/extra_types.py` responsibility

The file centralizes `JSONObject`/`JSONValue`, but also contains `LogRecord` extra extraction helpers.

Question:
- Is this acceptable because these helpers are type-oriented?
- Or should these helpers move to something like `platform/logging/record_extras.py`?

### Concern 4: request logging middleware location

`main.py` currently contains the middleware implementation.

Question:
- Is this acceptable at this stage?
- Or should it move to `platform/logging/middleware.py` or `platform/logging/http_middleware.py`?

### Concern 5: `JsonLogError.stack`

Error logs currently include full stack trace when exception info exists.

Question:
- Is this okay for current phase?
- Should stack output be policy-gated later for production/security/log-volume reasons?

### Concern 6: Pydantic payload models

The logging payload schema uses Pydantic models. There is some boilerplate in `to_json_value()` methods.

Question:
- Is Pydantic justified because logs may become OpenTelemetry events/contracts?
- Or is it overkill and should dataclass/TypedDict be used instead?

### Concern 7: flat output with internal contexts

Internally, payload is split into service/trace/http/error contexts, but stdout JSON is flat.

Question:
- Is this a good compromise?
- Should output remain flat or become nested?

## Desired review output

Please answer in this structure:

1. Executive summary
2. Priority-ranked cleanup list
3. Things to keep
4. Things to remove or move
5. Recommended order of changes
6. Any risks I missed

Please be specific to the files listed above.

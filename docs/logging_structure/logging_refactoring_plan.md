# Logging refactoring plan

작성일: 2026-04-23  
대상: FastAPI backend JSON logging 구조

## 1. 목적

현재 JSON logging 구조에서 유지할 설계와 줄여야 할 설계를 분리한다.
이번 리팩터링은 기능 확장이 아니라 **운영 노이즈 제거, hot path 정리, 모듈 책임 분리**를 목표로 한다.

## 2. 참고 문서

이 계획은 아래 협업/검토 문서를 기준으로 한다.

```text
docs/logging_structure/logging_cleanup_review_request.md
docs/logging_structure/logging_hermes_cleanup_review_response.md
docs/logging_structure/logging_cleanup_implementation_plan.md
docs/logging_structure/logging_hermes_cleanup_refactor_review.md
```

## 3. 현재 유지할 설계

### 3.1 Pydantic log payload schema 유지

유지 대상:

```text
backend/app/platform/logging/payloads.py
```

유지 이유:

- JSON log는 단순 내부 dict가 아니라 향후 OpenTelemetry로 보낼 observability contract다.
- `extra="forbid"`, `frozen=True`, `strict=True`는 log schema drift를 조기에 드러낸다.
- `StrictStr`, `StrictInt`는 식별자/정수 필드 의도를 명확히 한다.
- Pydantic 사용 범위가 logging payload boundary에 제한되어 있어 과하지 않다.

### 3.2 내부 context 분리 유지

유지 대상:

```python
JsonLogServiceContext
JsonLogTraceContext
JsonLogHttpContext
JsonLogError
JsonLogPayload
```

유지 이유:

- service/trace/http/error 역할이 독립적이다.
- 나중에 OpenTelemetry resource/span/http/exception attribute로 매핑하기 쉽다.
- worker, scheduler, collector 로그에서도 context 단위 재사용 가능성이 있다.

### 3.3 외부 출력은 flat JSON 유지

유지 이유:

- Loki, ELK, CloudWatch, grep 기반 검색에서 top-level key가 편하다.
- 내부 모델은 context로 분리하고, stdout 출력만 flat하게 유지하는 절충이 좋다.
- 지금 nested JSON으로 바꾸면 운영상 이득보다 쿼리/문서/테스트 변경 비용이 크다.

### 3.4 error stack은 이번 패스에서 유지

유지 이유:

- 초기 개발/디버깅 단계에서는 full stack이 유용하다.
- 단, production 전에는 stack 길이 제한, redaction, sampling, 출력 여부 정책이 필요하다.

## 4. 이번 리팩터링에서 바꿀 것

## 4.1 service metadata를 formatter 생성 시점에 1회 주입

### 현재 문제

현재 구조는 log payload를 만들 때마다 아래 필수 env를 읽는다.

```python
SERVICE_APP_NAME
SERVICE_APP_ENV
SERVICE_APP_VERSION
```

문제점:

- process lifetime 동안 고정인 값을 매 로그마다 읽는다.
- formatter hot path에서 설정 검증을 반복한다.
- env 누락 오류가 log formatting 중 발생할 수 있다.

### 변경 방향

`configure_logging()`에서 한 번만 읽고 검증한다.

```python
service_context = JsonLogServiceContext(
    service=_required_env("SERVICE_APP_NAME"),
    env=_required_env("SERVICE_APP_ENV"),
    version=_required_env("SERVICE_APP_VERSION"),
)
```

`JsonFormatter` 생성자에 주입한다.

```python
JsonFormatter(service_context=service_context)
```

`_log_payload()`는 service context를 파라미터로 받는다.

```python
def _log_payload(
    *,
    record: logging.LogRecord,
    service_context: JsonLogServiceContext,
) -> JsonLogPayload:
    ...
```

### 주의할 점

현재 `main.py`에서 `configure_logging()`이 import 시점에 호출된다.
따라서 service context 검증도 import 시점에 발생할 수 있다.
이번 패스에서는 이 리스크를 인지하고 테스트 환경변수를 명시적으로 세팅한다.
app factory / settings bootstrap 분리는 다음 패스에서 검토한다.

## 4.2 `/health` 성공 로그 emission skip

### 현재 문제

`uvicorn --no-access-log`는 access log만 끈다.  
현재 FastAPI middleware는 `/health` 요청도 app-level JSON log로 남길 수 있다.

### 변경 방향

- `/health` 성공 응답은 request log emission을 skip한다.
- 단, `x-request-id`, `x-trace-id` header 처리는 유지한다.
- `/health`가 5xx 또는 exception이면 로그를 남긴다.

예상 정책:

```python
HEALTHCHECK_PATHS = {"/health"}


def should_skip_request_log(*, path: str, status_code: int) -> bool:
    return path in HEALTHCHECK_PATHS and status_code < 500
```

### 이유

- 정상 healthcheck는 운영 노이즈다.
- 실패 healthcheck는 운영 signal이므로 남기는 것이 좋다.

## 4.3 LogRecord extra helper를 logging 모듈로 이동

### 현재 문제

현재 파일:

```text
backend/app/shared/types/extra_types.py
```

여기에 아래 두 책임이 섞여 있다.

```python
JSONObject / JSONValue 타입 alias
log_record_extra_* helper
```

`log_record_extra_*`는 타입 alias가 아니라 `logging.LogRecord` 전용 parsing behavior다.

### 변경 방향

`shared/types/extra_types.py`에는 타입 alias만 남긴다.

```python
type JSONObject = dict[str, JSONValue]
type JSONValue = str | int | float | bool | None | list[JSONValue] | JSONObject
```

새 파일:

```text
backend/app/platform/logging/context/log_record_extras.py
```

이동 대상:

```python
log_record_extra_str
log_record_extra_str_or_default
log_record_extra_float
log_record_extra_int
```

### 파일명 결정

Hermes 검토 기준 추천 순위:

1. `log_record_extras.py`
2. `record_extras.py`
3. `extra_fields.py`

이번 계획에서는 `log_record_extras.py`를 사용한다.

## 5. 이번 패스에서 하지 않을 것

### 5.1 middleware 파일 분리

보류 대상:

```text
backend/app/platform/logging/http_middleware.py
```

보류 이유:

- 이번 패스에서는 behavior cleanup과 책임 경계 일부 정리만 한다.
- middleware 분리는 diff를 키울 수 있다.
- `/health` skip과 service context injection을 테스트로 보호한 뒤 다음 패스에서 진행한다.

### 5.2 error stack policy gate 추가

보류 이유:

- full stack은 현재 개발 단계에서 유용하다.
- 단순 env gate를 급하게 추가하면 정책이 어설퍼질 수 있다.
- 다음 패스에서 production stack 출력 여부, redaction, sampling, stack length limit을 별도 정책으로 다룬다.

### 5.3 trace context 우선순위 변경

보류 이유:

- 현재 `x-trace-id`와 `traceparent` 우선순위는 별도 호환성 정책이 필요하다.
- W3C Trace Context 우선으로 바꿀지 여부는 OpenTelemetry mapping 작업 때 함께 결정한다.

### 5.4 app factory / settings bootstrap 도입

보류 이유:

- 지금 도입하면 logging cleanup보다 큰 구조 변경이 된다.
- 다만 `configure_logging()` import-time validation risk는 기록해둔다.

## 6. 테스트 계획

## 6.1 service context 주입 테스트

검증할 것:

- `JsonFormatter(service_context=...)`가 출력 JSON에 `service`, `env`, `version`을 넣는다.
- `SERVICE_APP_NAME`, `SERVICE_APP_ENV`, `SERVICE_APP_VERSION`이 누락되면 configure/service-context 생성 단계에서 실패한다.

## 6.2 `/health` logging skip 테스트

검증할 것:

- `/health` 성공 요청은 `request_completed` app-level JSON log를 남기지 않는다.
- `/health` 성공 응답은 `x-request-id` header를 유지한다.
- `/health` 실패/exception은 로그를 남기는 정책을 유지한다.

## 6.3 non-health logging 유지 테스트

검증할 것:

- non-health 요청은 기존처럼 `request_completed` 또는 대응 event log를 남긴다.
- `request_id`, `trace_id`, `http_method`, `path`, `status_code`, `duration_ms`가 유지된다.

## 6.4 import 이동 테스트

검증할 것:

- `log_record_extra_*` 이동 후 기존 JSON formatter 테스트가 그대로 통과한다.
- `make ci`의 Pyrefly, Ruff, guardrails가 통과한다.

## 7. 최종 구현 순서

Hermes 검토 반영 후 최종 순서:

1. `JsonFormatter`가 `JsonLogServiceContext`를 생성자에서 받도록 변경한다.
2. `configure_logging()`에서 service context를 1회 생성한다.
3. formatter service context 주입 테스트를 추가/수정한다.
4. `/health` 성공 로그 emission skip을 추가한다.
5. `/health` skip 테스트를 추가한다.
6. `log_record_extra_*`를 `platform/logging/context/log_record_extras.py`로 이동한다.
7. `shared/types/extra_types.py`에는 `JSONObject`, `JSONValue`만 남긴다.
8. import를 정리한다.
9. `make ci`를 실행한다.
10. 필요하면 `docker compose config`를 실행한다.

## 8. 완료 조건

완료 조건:

- `make ci` 통과
- `/health` 성공 요청이 app-level JSON request log를 남기지 않음
- `/health` 응답 header는 유지
- non-health 요청은 계속 JSON request log를 남김
- service/env/version은 formatter 생성 시점에 주입됨
- `shared/types`는 타입 alias만 담당
- `platform/logging/context/log_record_extras.py`가 LogRecord extra 추출을 담당

## 9. 남은 리스크

- `configure_logging()`이 import 시점에 실행되는 구조는 유지된다.
- production error stack policy는 아직 없다.
- trace context 우선순위(`x-trace-id` vs `traceparent`)는 아직 확정되지 않았다.
- middleware 분리는 아직 하지 않는다.

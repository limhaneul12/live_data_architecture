"""요청 logging helper와 trace context 처리 모듈."""

from __future__ import annotations

import logging
import string
from collections.abc import Callable
from uuid import uuid4

from fastapi import Request
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

HEALTHCHECK_PATHS = {"/health", "/health/live", "/health/ready", "/health/heartbeat"}
_TRACEPARENT_VERSION_LENGTH = 2
_TRACE_ID_LENGTH = 32
_PARENT_ID_LENGTH = 16
_TRACE_FLAGS_LENGTH = 2
_LOWER_HEX_DIGITS = set(string.hexdigits.lower())
type TraceparentFieldValidator = Callable[[str], bool]


def should_skip_request_log(path: str, status_code: int) -> bool:
    """요청 로그를 생략할지 판단한다.

    인자:
        path: query string을 제외한 요청 path.
        status_code: 응답 HTTP status code.

    반환:
        expected healthcheck 로그를 생략해야 하면 True.
    """
    return path in HEALTHCHECK_PATHS and (status_code < 500 or status_code == 503)


def resolve_request_id(request: Request) -> str:
    """요청 식별자를 읽거나 새로 만든다.

    인자:
        request: 들어온 HTTP 요청.

    반환:
        요청 생명주기 동안 사용할 request id.
    """
    request_id = request.headers.get("x-request-id")
    if request_id:
        return request_id

    correlation_id = request.headers.get("x-correlation-id")
    if correlation_id:
        return correlation_id

    return str(uuid4())


def _is_lower_hex(value: str, *, length: int) -> bool:
    """고정 길이 lowercase hex 문자열인지 확인한다.

    인자:
        value: 검사할 문자열.
        length: 기대하는 길이.

    반환:
        조건을 만족하면 True.
    """
    if len(value) != length:
        return False
    return all(char in _LOWER_HEX_DIGITS for char in value)


def _is_all_zero(value: str) -> bool:
    """문자열이 전부 0으로만 이루어졌는지 확인한다."""
    return set(value) == {"0"}


def _traceparent_hex_validator(
    *,
    length: int,
    allow_all_zero: bool = True,
    forbidden_values: set[str] | None = None,
) -> TraceparentFieldValidator:
    """Traceparent 필드용 hex validator를 만든다.

    인자:
        length: 기대하는 문자열 길이.
        allow_all_zero: all-zero 값을 허용할지 여부.
        forbidden_values: 금지할 특정 값 집합.

    반환:
        단일 traceparent 필드를 검사하는 validator 함수.
    """
    blocked_values = forbidden_values or set()

    def validate(value: str) -> bool:
        """단일 traceparent 필드 값을 검사한다.

        인자:
            value: 검사할 필드 값.

        반환:
            정책을 만족하면 True.
        """
        if not _is_lower_hex(value, length=length):
            return False
        if value in blocked_values:
            return False
        return not (not allow_all_zero and _is_all_zero(value))

    return validate


_TRACEPARENT_FIELD_VALIDATORS: tuple[TraceparentFieldValidator, ...] = (
    _traceparent_hex_validator(
        length=_TRACEPARENT_VERSION_LENGTH,
        forbidden_values={"ff"},
    ),
    _traceparent_hex_validator(
        length=_TRACE_ID_LENGTH,
        allow_all_zero=False,
    ),
    _traceparent_hex_validator(
        length=_PARENT_ID_LENGTH,
        allow_all_zero=False,
    ),
    _traceparent_hex_validator(length=_TRACE_FLAGS_LENGTH),
)


def _parse_traceparent(value: str | None) -> tuple[str | None, str | None]:
    """표준 W3C traceparent 헤더를 파싱한다.

    인자:
        value: traceparent 헤더 원문.

    반환:
        유효하면 trace_id와 span_id, 아니면 None 쌍.
    """
    if value is None:
        return None, None

    parts = value.strip().split("-")
    if len(parts) != 4:
        return None, None

    version, trace_id, parent_id, trace_flags = parts
    traceparent_fields = (version, trace_id, parent_id, trace_flags)
    if not all(
        validator(field)
        for validator, field in zip(
            _TRACEPARENT_FIELD_VALIDATORS,
            traceparent_fields,
            strict=True,
        )
    ):
        return None, None

    return trace_id, parent_id


def current_trace_context() -> tuple[str | None, str | None, str | None]:
    """현재 활성 OpenTelemetry trace context를 읽는다.

    반환:
        trace_id, span_id, tracer_error 튜플.
    """
    try:
        span = trace.get_current_span()
        span_context = span.get_span_context()
        if not span_context.is_valid:
            return None, None, None

        trace_id = f"{span_context.trace_id:032x}"
        span_id = f"{span_context.span_id:016x}"
    except Exception as error:  # pragma: no cover
        return None, None, f"{type(error).__name__}: {error}"
    else:
        return trace_id, span_id, None


def resolve_trace_context(
    request: Request,
) -> tuple[str | None, str | None, str | None]:
    """요청 헤더와 활성 tracer에서 trace context를 결정한다.

    우선순위:
        1. valid traceparent
        2. active OpenTelemetry span
        3. x-trace-id fallback

    인자:
        request: 들어온 HTTP 요청.

    반환:
        trace_id, span_id, tracer_error 튜플.
    """
    parsed_trace_id, parsed_span_id = _parse_traceparent(
        request.headers.get("traceparent")
    )
    if parsed_trace_id is not None:
        return parsed_trace_id, parsed_span_id, None

    active_trace_id, active_span_id, tracer_error = current_trace_context()
    if active_trace_id is not None:
        return active_trace_id, active_span_id, tracer_error

    trace_id_header = request.headers.get("x-trace-id")
    if trace_id_header:
        return trace_id_header, None, tracer_error

    return None, None, tracer_error


def _record_tracer_exception(error: Exception) -> str | None:
    """현재 활성 OpenTelemetry span에 예외를 기록한다.

    인자:
        error: 발생한 예외.

    반환:
        tracer 기록 중 오류가 발생하면 오류 메시지, 아니면 None.
    """
    try:
        span = trace.get_current_span()
        span_context = span.get_span_context()
        if not span_context.is_valid:
            return None

        span.record_exception(error)
        span.set_status(
            Status(
                status_code=StatusCode.ERROR,
                description=f"{type(error).__name__}: {error}",
            )
        )
    except Exception as tracer_error:  # pragma: no cover
        return f"{type(tracer_error).__name__}: {tracer_error}"
    else:
        return None


def log_request_outcome(
    logger: logging.Logger,
    *,
    level: int,
    message: str,
    event: str,
    request_id: str,
    http_method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    func: str | None,
    trace_id: str | None,
    span_id: str | None,
    tracer_error: str | None,
) -> None:
    """예외 객체가 없는 요청 결과를 구조화 로그로 남긴다.

    인자:
        logger: 사용할 logger.
        level: logging level.
        message: 사람이 읽는 로그 메시지.
        event: 검색/집계를 위한 이벤트 이름.
        request_id: 요청 식별자.
        http_method: HTTP method.
        path: 요청 path.
        status_code: 응답 status code.
        duration_ms: 요청 처리 시간(ms).
        func: endpoint 함수 이름.
        trace_id: trace 식별자.
        span_id: span 식별자.
        tracer_error: tracer 연동 오류 메시지.

    반환:
        없음.

    참고:
        이 함수는 성공 응답이나 예외 객체 없이 결정된 상태 코드 기반 결과 로그에만 사용한다.
        실제 예외 객체와 stack trace를 함께 기록해야 할 때는 `log_request_exception()`을 사용한다.
    """
    logger.log(
        level,
        message,
        extra={
            "event": event,
            "request_id": request_id,
            "correlation_id": request_id,
            "trace_id": trace_id,
            "span_id": span_id,
            "tracer_error": tracer_error,
            "http_method": http_method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "func": func,
        },
    )


def log_request_exception(
    logger: logging.Logger,
    *,
    message: str,
    event: str,
    request_id: str,
    http_method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    func: str | None,
    trace_id: str | None,
    span_id: str | None,
    error: Exception,
) -> None:
    """예외 객체가 있는 요청 실패를 로그로 남기고 tracer span에도 기록한다.

    인자:
        logger: 사용할 logger.
        message: 사람이 읽는 로그 메시지.
        event: 검색/집계를 위한 이벤트 이름.
        request_id: 요청 식별자.
        http_method: HTTP method.
        path: 요청 path.
        status_code: 응답 status code.
        duration_ms: 요청 처리 시간(ms).
        func: endpoint 함수 이름.
        trace_id: trace 식별자.
        span_id: span 식별자.
        error: 발생한 예외.

    반환:
        없음.

    참고:
        이 함수는 `logger.exception(...)`을 사용하므로 `exc_info`가 함께 기록된다.
        따라서 formatter가 `error.type`, `error.message`, `error.stack`를 만들 수 있다.
        예외 객체가 없는 단순 결과 로그는 `log_request_outcome()`을 사용한다.
    """
    tracer_error = _record_tracer_exception(error)
    logger.exception(
        message,
        extra={
            "event": event,
            "request_id": request_id,
            "correlation_id": request_id,
            "trace_id": trace_id,
            "span_id": span_id,
            "tracer_error": tracer_error,
            "http_method": http_method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "func": func,
        },
    )

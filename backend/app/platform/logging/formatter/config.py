"""백엔드 서비스의 JSON logging 설정 모듈."""

from __future__ import annotations

import logging
import traceback
from datetime import UTC, datetime
from types import TracebackType

from app.platform.config import AppConfig
from app.platform.logging.context.log_record_extras import (
    log_record_extra_float,
    log_record_extra_int,
    log_record_extra_str,
    log_record_extra_str_or_default,
)
from app.platform.schemas.logging_schema import (
    JsonLogError,
    JsonLogHttpContext,
    JsonLogPayload,
    JsonLogServiceContext,
    JsonLogTraceContext,
)
from app.shared.serialization import dumps_json


def _should_include_error_stack(app_env: str) -> bool:
    """환경 이름에 따라 error stack 포함 여부를 결정한다.

    인자:
        app_env: 현재 애플리케이션 실행 환경 이름.

    반환:
        stack trace를 로그에 포함해야 하면 True.
    """
    return app_env.lower() in {"local", "stage", "prod"}


def _format_stack(
    *,
    exc_type: type[BaseException] | None,
    exc_value: BaseException | None,
    exc_tb: TracebackType | None,
    include_stack: bool,
) -> str:
    """예외 traceback을 JSON 로그용 문자열로 변환한다.

    인자:
        exc_type: 예외 타입.
        exc_value: 예외 인스턴스.
        exc_tb: 예외 traceback.
        include_stack: stack trace를 포함할지 여부.

    반환:
        포함 정책이 켜져 있으면 traceback 문자열, 아니면 빈 문자열.
    """
    if not include_stack:
        return ""
    return "".join(traceback.format_exception(exc_type, exc_value, exc_tb))


def _error_payload(
    *,
    record: logging.LogRecord,
    include_stack: bool,
) -> JsonLogError | None:
    """로그 레코드에서 구조화된 에러 payload를 만든다.

    인자:
        record: Python logging record.
        include_stack: error.stack 필드에 traceback을 포함할지 여부.

    반환:
        예외 정보가 있으면 에러 payload, 없으면 None.
    """
    if not record.exc_info:
        return None

    exc_type, exc_value, exc_tb = record.exc_info
    exc_type_name: str | None = None if exc_type is None else exc_type.__name__
    exc_message: str | None = None if exc_value is None else str(exc_value)

    return JsonLogError(
        type=exc_type_name,
        message=exc_message,
        stack=_format_stack(
            exc_type=exc_type,
            exc_value=exc_value,
            exc_tb=exc_tb,
            include_stack=include_stack,
        ),
    )


def _trace_context(record: logging.LogRecord) -> JsonLogTraceContext:
    """로그 레코드에서 trace context payload를 만든다.

    인자:
        record: Python logging record.

    반환:
        trace/correlation 정보를 담은 payload.
    """
    request_id = log_record_extra_str(record=record, key="request_id")
    return JsonLogTraceContext(
        request_id=request_id,
        correlation_id=log_record_extra_str(
            record=record,
            key="correlation_id",
            default=request_id,
        ),
        trace_id=log_record_extra_str(record=record, key="trace_id"),
        span_id=log_record_extra_str(record=record, key="span_id"),
        tracer_error=log_record_extra_str(record=record, key="tracer_error"),
    )


def _http_context(record: logging.LogRecord) -> JsonLogHttpContext:
    """로그 레코드에서 HTTP context payload를 만든다.

    인자:
        record: Python logging record.

    반환:
        HTTP 요청/응답 정보를 담은 payload.
    """
    return JsonLogHttpContext(
        method=log_record_extra_str(record=record, key="http_method"),
        path=log_record_extra_str(record=record, key="path"),
        status_code=log_record_extra_int(record=record, key="status_code"),
    )


def _log_payload(
    *,
    record: logging.LogRecord,
    service_context: JsonLogServiceContext,
    include_error_stack: bool,
) -> JsonLogPayload:
    """로그 레코드에서 구조화된 Pydantic log payload를 만든다.

    인자:
        record: Python logging record.
        service_context: formatter 생성 시점에 검증된 서비스 context.
        include_error_stack: error.stack 필드에 traceback을 포함할지 여부.

    반환:
        검증된 log payload.
    """
    event_name = log_record_extra_str_or_default(
        record=record,
        key="event",
        default=record.name,
    )
    return JsonLogPayload(
        ts=datetime.now(UTC).isoformat(timespec="milliseconds"),
        level=record.levelname,
        logger=record.name,
        event=event_name,
        msg=record.getMessage(),
        func=log_record_extra_str(record=record, key="func", default=record.funcName),
        duration_ms=log_record_extra_float(record=record, key="duration_ms"),
        service=service_context,
        trace=_trace_context(record),
        http=_http_context(record),
        error=_error_payload(record=record, include_stack=include_error_stack),
    )


class JsonFormatter(logging.Formatter):
    """로그 레코드를 기계가 읽을 수 있는 JSON 문자열로 변환한다."""

    def __init__(
        self,
        *,
        service_context: JsonLogServiceContext,
        include_error_stack: bool,
    ) -> None:
        """로그 formatter 인스턴스를 초기화한다.

        인자:
            service_context: 모든 로그에 주입할 서비스 식별 context.
            include_error_stack: error.stack 필드에 traceback을 포함할지 여부.
        """
        super().__init__()
        self._service_context = service_context
        self._include_error_stack = include_error_stack

    def format(self, record: logging.LogRecord) -> str:
        """로그 레코드를 JSON 문자열로 인코딩한다.

        인자:
            record: Python logging record.

        반환:
            표준 필드를 포함한 JSON 문자열.
        """
        payload = _log_payload(
            record=record,
            service_context=self._service_context,
            include_error_stack=self._include_error_stack,
        )
        return dumps_json(payload.to_json_value()).decode("utf-8")


def _has_json_stream_handler(logger: logging.Logger) -> bool:
    """로거에 JSON stream handler가 이미 있는지 확인한다.

    인자:
        logger: 검사할 logger.

    반환:
        JsonFormatter를 쓰는 StreamHandler가 있으면 True.
    """
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and isinstance(
            handler.formatter,
            JsonFormatter,
        ):
            return True
    return False


def configure_logging() -> None:
    """루트 logger를 JSON stream handler 기반으로 설정한다.

    Logger handler 목록을 직접 확인해서 module-level mutable state 없이
    여러 번 호출해도 같은 handler가 중복 등록되지 않게 한다.
    """
    app_config = AppConfig()
    level_name = app_config.app_log_level.upper()
    log_level = logging.getLevelNamesMapping().get(level_name, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    if not _has_json_stream_handler(root_logger):
        service_context = JsonLogServiceContext(
            service=app_config.app_name,
            env=app_config.app_env,
            version=app_config.app_version,
        )
        include_error_stack = _should_include_error_stack(service_context.env)
        for existing_handler in root_logger.handlers[:]:
            root_logger.removeHandler(existing_handler)
        handler = logging.StreamHandler()
        handler.setFormatter(
            JsonFormatter(
                service_context=service_context,
                include_error_stack=include_error_stack,
            )
        )
        root_logger.addHandler(handler)

    for logger_name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(logger_name)
        for existing_handler in uvicorn_logger.handlers[:]:
            uvicorn_logger.removeHandler(existing_handler)
        uvicorn_logger.propagate = True

    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    for existing_handler in uvicorn_access_logger.handlers[:]:
        uvicorn_access_logger.removeHandler(existing_handler)
    uvicorn_access_logger.propagate = False
    uvicorn_access_logger.disabled = True

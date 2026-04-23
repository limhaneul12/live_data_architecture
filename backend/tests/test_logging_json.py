import logging
from types import TracebackType

import orjson
from app.platform.logging.formatter.config import JsonFormatter
from app.platform.schemas.logging_schema import JsonLogServiceContext


def _service_context() -> JsonLogServiceContext:
    return JsonLogServiceContext(
        service="live-data-api",
        env="test",
        version="0.1.0",
    )


def _raise_value_error() -> None:
    raise ValueError("boom")


def _captured_value_error() -> tuple[
    type[BaseException], BaseException, TracebackType | None
]:
    try:
        _raise_value_error()
    except ValueError as error:
        return type(error), error, error.__traceback__
    raise AssertionError


def test_json_formatter_includes_duration_func_and_identifiers() -> None:
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="request completed",
        args=(),
        exc_info=None,
    )
    record.__dict__.update(
        {
            "event": "request_completed",
            "duration_ms": 12.5,
            "func": "app.main.get_health",
            "request_id": "req-123",
            "trace_id": "trace-123",
            "span_id": "span-123",
        }
    )

    payload = orjson.loads(
        JsonFormatter(
            service_context=_service_context(),
            include_error_stack=True,
        ).format(record)
    )

    assert payload["event"] == "request_completed"
    assert payload["duration_ms"] == 12.5
    assert payload["func"] == "app.main.get_health"
    assert payload["service"] == "live-data-api"
    assert payload["env"] == "test"
    assert payload["version"] == "0.1.0"
    assert payload["request_id"] == "req-123"
    assert payload["correlation_id"] == "req-123"
    assert payload["trace_id"] == "trace-123"
    assert payload["span_id"] == "span-123"


def test_json_formatter_includes_error_block_when_exception_exists() -> None:
    record = logging.LogRecord(
        name="app.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=30,
        msg="request failed",
        args=(),
        exc_info=_captured_value_error(),
    )

    payload = orjson.loads(
        JsonFormatter(
            service_context=_service_context(),
            include_error_stack=True,
        ).format(record)
    )

    assert payload["error"]["type"] == "ValueError"
    assert payload["error"]["message"] == "boom"
    assert "ValueError: boom" in payload["error"]["stack"]


def test_json_formatter_omits_stack_when_policy_disables_it() -> None:
    record = logging.LogRecord(
        name="app.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=40,
        msg="request failed",
        args=(),
        exc_info=_captured_value_error(),
    )

    payload = orjson.loads(
        JsonFormatter(
            service_context=_service_context(),
            include_error_stack=False,
        ).format(record)
    )

    assert payload["error"]["type"] == "ValueError"
    assert payload["error"]["message"] == "boom"
    assert payload["error"]["stack"] == ""

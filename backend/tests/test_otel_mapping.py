from app.platform.logging.mapping.otel_mapping import payload_to_otel_log_mapping
from app.platform.schemas.logging_schema import (
    JsonLogError,
    JsonLogHttpContext,
    JsonLogPayload,
    JsonLogServiceContext,
    JsonLogTraceContext,
)


def _payload() -> JsonLogPayload:
    return JsonLogPayload(
        ts="2026-04-23T00:00:00+00:00",
        level="ERROR",
        logger="app.main",
        event="request_failed",
        msg="request failed",
        func="app.main.get_health",
        duration_ms=12.5,
        service=JsonLogServiceContext(
            service="live-data-api",
            env="test",
            version="0.1.0",
        ),
        trace=JsonLogTraceContext(
            request_id="req-1",
            correlation_id="req-1",
            trace_id="trace-1",
            span_id="span-1",
            tracer_error=None,
        ),
        http=JsonLogHttpContext(
            method="GET",
            path="/health",
            status_code=500,
        ),
        error=JsonLogError(
            type="ValueError",
            message="boom",
            stack="traceback",
        ),
    )


def test_payload_to_otel_log_mapping_maps_core_fields() -> None:
    mapping = payload_to_otel_log_mapping(_payload())

    assert mapping.timestamp == "2026-04-23T00:00:00+00:00"
    assert mapping.severity_text == "ERROR"
    assert mapping.body == "request failed"
    assert mapping.trace_id == "trace-1"
    assert mapping.span_id == "span-1"


def test_payload_to_otel_log_mapping_maps_minimal_attributes() -> None:
    attributes = payload_to_otel_log_mapping(_payload()).attributes

    expected = {
        "service.name": "live-data-api",
        "deployment.environment.name": "test",
        "service.version": "0.1.0",
        "event.name": "request_failed",
        "app.request_id": "req-1",
        "http.request.method": "GET",
        "url.path": "/health",
        "http.response.status_code": 500,
        "exception.type": "ValueError",
        "exception.message": "boom",
        "exception.stacktrace": "traceback",
    }

    assert attributes == expected


def test_payload_to_otel_log_mapping_omits_deferred_and_none_attributes() -> None:
    attributes = payload_to_otel_log_mapping(_payload()).attributes

    deferred_keys = {
        "log.logger",
        "code.function",
        "http.server.request.duration_ms",
        "app.correlation_id",
        "app.tracer_error",
        "app.lifecycle",
        "app.drain_reason",
        "app.error_count",
        "app.window_seconds",
        "app.last_error_at",
        "app.drain_started_at",
    }

    assert deferred_keys.isdisjoint(attributes)

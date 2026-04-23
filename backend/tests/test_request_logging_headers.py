import logging

from app.main import app
from app.platform.logging import resolve_trace_context, should_skip_request_log
from fastapi import Request
from fastapi.testclient import TestClient


def _request_log_records(
    records: list[logging.LogRecord],
) -> list[logging.LogRecord]:
    return [
        record
        for record in records
        if record.__dict__.get("event")
        in {"request_completed", "request_server_error", "request_failed"}
    ]


def _request_with_headers(headers: dict[str, str]) -> Request:
    return Request(
        {
            "type": "http",
            "headers": [
                (key.lower().encode("utf-8"), value.encode("utf-8"))
                for key, value in headers.items()
            ],
        }
    )


def test_health_response_sets_request_id_when_missing() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers.get("x-request-id")


def test_health_response_keeps_existing_request_id() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"x-request-id": "req-from-client"})

    assert response.status_code == 200
    assert response.headers.get("x-request-id") == "req-from-client"


def test_health_response_exposes_trace_id_header() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/health",
            headers={"x-request-id": "req-1", "x-trace-id": "trace-1"},
        )

    assert response.status_code == 200
    assert response.headers.get("x-request-id") == "req-1"
    assert response.headers.get("x-trace-id") == "trace-1"


def test_health_success_does_not_emit_request_log(
    caplog,
) -> None:
    with TestClient(app) as client, caplog.at_level(logging.INFO):
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers.get("x-request-id")
    assert _request_log_records(caplog.records) == []


def test_non_health_request_still_emits_request_log(caplog) -> None:
    with TestClient(app) as client, caplog.at_level(logging.INFO):
        response = client.get("/missing")

    request_logs = _request_log_records(caplog.records)

    assert response.status_code == 404
    assert [record.__dict__.get("path") for record in request_logs] == ["/missing"]
    assert [record.__dict__.get("status_code") for record in request_logs] == [404]


def test_health_logging_skip_policy_keeps_failure_signal() -> None:
    assert should_skip_request_log(path="/health", status_code=200)
    assert should_skip_request_log(path="/health/ready", status_code=503)
    assert should_skip_request_log(path="/health/heartbeat", status_code=503)
    assert not should_skip_request_log(path="/health", status_code=500)
    assert not should_skip_request_log(path="/missing", status_code=200)


def test_traceparent_is_used_before_x_trace_id() -> None:
    request = _request_with_headers(
        {
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
            "x-trace-id": "fallback-trace-id",
        }
    )

    trace_id, span_id, tracer_error = resolve_trace_context(request)

    assert trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert span_id == "00f067aa0ba902b7"
    assert tracer_error is None


def test_invalid_traceparent_falls_back_to_x_trace_id() -> None:
    request = _request_with_headers(
        {
            "traceparent": "00-00000000000000000000000000000000-00f067aa0ba902b7-01",
            "x-trace-id": "fallback-trace-id",
        }
    )

    trace_id, span_id, tracer_error = resolve_trace_context(request)

    assert trace_id == "fallback-trace-id"
    assert span_id is None
    assert tracer_error is None


def test_x_trace_id_is_used_when_no_traceparent_exists() -> None:
    request = _request_with_headers({"x-trace-id": "fallback-trace-id"})

    trace_id, span_id, tracer_error = resolve_trace_context(request)

    assert trace_id == "fallback-trace-id"
    assert span_id is None
    assert tracer_error is None

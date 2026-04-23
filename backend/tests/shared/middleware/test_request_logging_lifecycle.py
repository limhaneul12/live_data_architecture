import logging

from app.platform.middleware import install_request_logging_middleware
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _failing_app() -> FastAPI:
    app = FastAPI()
    logger = logging.getLogger("test.lifecycle.middleware")
    install_request_logging_middleware(app, logger=logger)

    @app.get("/boom")
    def boom() -> dict[str, str]:
        raise RuntimeError("boom")

    return app


def _events(records: list[logging.LogRecord]) -> list[str]:
    return [str(record.__dict__.get("event")) for record in records]


def test_unhandled_exception_logs_request_failed_without_drain_event(caplog) -> None:
    app = _failing_app()

    with (
        TestClient(app, raise_server_exceptions=False) as client,
        caplog.at_level(logging.ERROR),
    ):
        response = client.get("/boom")

    assert response.status_code == 500
    assert "request_failed" in _events(caplog.records)
    assert "lifecycle_draining_started" not in _events(caplog.records)

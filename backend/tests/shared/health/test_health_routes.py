from datetime import UTC, datetime

from app.platform.health_router import install_health_routes
from app.platform.lifecycle import LifecycleState
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _app_with_lifecycle(lifecycle: LifecycleState) -> FastAPI:
    app = FastAPI()
    install_health_routes(app, lifecycle=lifecycle)
    return app


def test_live_returns_ok_when_running() -> None:
    lifecycle = LifecycleState(started_at=datetime(2026, 1, 1, tzinfo=UTC))
    lifecycle.mark_running()
    app = _app_with_lifecycle(lifecycle)

    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_ok_when_running() -> None:
    lifecycle = LifecycleState(started_at=datetime(2026, 1, 1, tzinfo=UTC))
    lifecycle.mark_running()
    app = _app_with_lifecycle(lifecycle)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    expected = {
        "status": "ok",
        "checks": {"app": "ok", "redis": "disabled", "database": "disabled"},
        "reason": None,
    }
    assert response.status_code == 200
    assert response.json() == expected


def test_ready_returns_503_when_draining() -> None:
    lifecycle = LifecycleState(started_at=datetime(2026, 1, 1, tzinfo=UTC))
    lifecycle.mark_running()
    lifecycle.start_draining(
        reason="manual",
        now=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
    )
    app = _app_with_lifecycle(lifecycle)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    expected = {
        "status": "draining",
        "checks": {
            "app": "draining",
            "redis": "disabled",
            "database": "disabled",
        },
        "reason": "manual",
    }
    assert response.status_code == 503
    assert response.json() == expected


def test_heartbeat_includes_lifecycle_snapshot_when_draining() -> None:
    started_at = datetime(2026, 1, 1, tzinfo=UTC)
    drain_started_at = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
    lifecycle = LifecycleState(started_at=started_at)
    lifecycle.mark_running()
    lifecycle.start_draining(
        reason="manual",
        now=drain_started_at,
    )
    app = _app_with_lifecycle(lifecycle)

    with TestClient(app) as client:
        response = client.get("/health/heartbeat")

    heartbeat = response.json()["heartbeat"]
    assert response.status_code == 503
    assert heartbeat["app"] == "draining"
    assert heartbeat["redis"] == "disabled"
    assert heartbeat["database"] == "disabled"
    assert heartbeat["lifecycle"] == "draining"
    assert heartbeat["draining"]
    assert heartbeat["drain_reason"] == "manual"
    assert heartbeat["started_at"] == started_at.isoformat()
    assert heartbeat["drain_started_at"] == drain_started_at.isoformat()


def test_ready_includes_redis_ok_when_stream_runtime_is_healthy() -> None:
    lifecycle = LifecycleState(started_at=datetime(2026, 1, 1, tzinfo=UTC))
    lifecycle.mark_redis_healthy()
    lifecycle.mark_database_healthy()
    lifecycle.mark_running()
    app = _app_with_lifecycle(lifecycle)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    expected = {
        "status": "ok",
        "checks": {"app": "ok", "redis": "ok", "database": "ok"},
        "reason": None,
    }
    assert response.status_code == 200
    assert response.json() == expected


def test_ready_returns_503_when_redis_is_unavailable() -> None:
    lifecycle = LifecycleState(started_at=datetime(2026, 1, 1, tzinfo=UTC))
    lifecycle.mark_running()
    lifecycle.mark_redis_unavailable()
    app = _app_with_lifecycle(lifecycle)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    expected = {
        "status": "not_ready",
        "checks": {"app": "ok", "redis": "unavailable", "database": "disabled"},
        "reason": "redis_unavailable",
    }
    assert response.status_code == 503
    assert response.json() == expected


def test_drain_marks_healthy_redis_as_draining_in_health_payload() -> None:
    lifecycle = LifecycleState(started_at=datetime(2026, 1, 1, tzinfo=UTC))
    lifecycle.mark_redis_healthy()
    lifecycle.mark_database_healthy()
    lifecycle.mark_running()
    lifecycle.start_draining(
        reason="manual",
        now=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
    )
    app = _app_with_lifecycle(lifecycle)

    with TestClient(app) as client:
        response = client.get("/health/heartbeat")

    heartbeat = response.json()["heartbeat"]
    assert response.status_code == 503
    assert heartbeat["app"] == "draining"
    assert heartbeat["redis"] == "draining"
    assert heartbeat["database"] == "draining"


def test_ready_returns_503_when_database_is_unavailable() -> None:
    lifecycle = LifecycleState(started_at=datetime(2026, 1, 1, tzinfo=UTC))
    lifecycle.mark_running()
    lifecycle.mark_database_unavailable()
    app = _app_with_lifecycle(lifecycle)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    expected = {
        "status": "not_ready",
        "checks": {"app": "ok", "redis": "disabled", "database": "unavailable"},
        "reason": "database_unavailable",
    }
    assert response.status_code == 503
    assert response.json() == expected


def test_ready_refreshes_dependency_health_before_snapshot() -> None:
    lifecycle = LifecycleState(started_at=datetime(2026, 1, 1, tzinfo=UTC))
    lifecycle.mark_redis_starting()
    lifecycle.mark_database_starting()
    lifecycle.mark_running()

    async def refresh_dependency_health() -> None:
        lifecycle.mark_redis_healthy()
        lifecycle.mark_database_healthy()

    app = FastAPI()
    install_health_routes(
        app,
        lifecycle=lifecycle,
        refresh_dependency_health=refresh_dependency_health,
    )

    with TestClient(app) as client:
        response = client.get("/health/ready")

    expected = {
        "status": "ok",
        "checks": {"app": "ok", "redis": "ok", "database": "ok"},
        "reason": None,
    }
    assert response.status_code == 200
    assert response.json() == expected

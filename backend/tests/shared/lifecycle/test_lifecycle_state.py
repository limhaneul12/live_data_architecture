from datetime import UTC, datetime, timedelta

from app.platform.lifecycle import (
    DependencyHealthStatus,
    LifecycleState,
    LifecycleStatus,
)


def test_lifecycle_marks_running_from_starting() -> None:
    state = LifecycleState(started_at=datetime(2026, 1, 1, tzinfo=UTC))

    state.mark_running()

    snapshot = state.snapshot()
    assert snapshot.status is LifecycleStatus.RUNNING
    assert snapshot.redis_status is DependencyHealthStatus.DISABLED
    assert snapshot.database_status is DependencyHealthStatus.DISABLED
    assert snapshot.ready


def test_start_draining_changes_app_state() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    state = LifecycleState(started_at=now)
    state.mark_running()

    changed = state.start_draining(reason="manual", now=now + timedelta(seconds=1))

    snapshot = state.snapshot()
    assert changed
    assert snapshot.status is LifecycleStatus.DRAINING
    assert not snapshot.ready
    assert snapshot.drain_reason == "manual"
    assert snapshot.drain_started_at == now + timedelta(seconds=1)


def test_drain_reason_keeps_first_reason() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    state = LifecycleState(started_at=now)
    state.mark_running()

    first = state.start_draining(reason="first", now=now)
    second = state.start_draining(reason="second", now=now + timedelta(seconds=1))

    snapshot = state.snapshot()
    assert first
    assert not second
    assert snapshot.drain_reason == "first"


def test_lifecycle_can_mark_running_after_stopping_for_new_lifespan() -> None:
    state = LifecycleState(started_at=datetime(2026, 1, 1, tzinfo=UTC))
    state.mark_running()
    state.mark_stopping()

    state.mark_running()

    snapshot = state.snapshot()
    assert snapshot.status is LifecycleStatus.RUNNING


def test_lifecycle_does_not_recover_from_draining_by_mark_running() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    state = LifecycleState(started_at=now)
    state.mark_running()
    state.start_draining(reason="first", now=now)

    state.mark_running()

    snapshot = state.snapshot()
    assert snapshot.status is LifecycleStatus.DRAINING


def test_lifecycle_readiness_requires_healthy_redis_when_enabled() -> None:
    state = LifecycleState(started_at=datetime(2026, 1, 1, tzinfo=UTC))
    state.mark_running()

    state.mark_redis_unavailable()

    snapshot = state.snapshot()
    assert snapshot.status is LifecycleStatus.RUNNING
    assert snapshot.redis_status is DependencyHealthStatus.UNAVAILABLE
    assert not snapshot.ready


def test_start_draining_marks_healthy_dependencies_as_draining() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    state = LifecycleState(started_at=now)
    state.mark_redis_healthy()
    state.mark_database_healthy()
    state.mark_running()

    state.start_draining(reason="manual", now=now)

    snapshot = state.snapshot()
    assert snapshot.status is LifecycleStatus.DRAINING
    assert snapshot.redis_status is DependencyHealthStatus.DRAINING
    assert snapshot.database_status is DependencyHealthStatus.DRAINING
    assert not snapshot.ready


def test_lifecycle_readiness_requires_healthy_database_when_enabled() -> None:
    state = LifecycleState(started_at=datetime(2026, 1, 1, tzinfo=UTC))
    state.mark_running()

    state.mark_database_unavailable()

    snapshot = state.snapshot()
    assert snapshot.status is LifecycleStatus.RUNNING
    assert snapshot.database_status is DependencyHealthStatus.UNAVAILABLE
    assert not snapshot.ready

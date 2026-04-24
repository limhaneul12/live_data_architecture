"""프로세스 로컬 lifecycle state 관리 모듈.

이 모듈의 상태는 하나의 Python process 안에서만 공유된다.
uvicorn/gunicorn multi-worker 환경에서는 worker마다 별도 lifecycle 상태를 가진다.

현재 구현은 운영 편의 기능을 빠르게 시작하기 위한 bootstrap 단계다.
서비스가 DB/Redis 같은 shared infrastructure를 도입하면 drain coordination,
short-lived failure counter, lifecycle event history는 외부 저장소 기준으로 재검토한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock


class LifecycleStatus(StrEnum):
    """서비스 lifecycle 상태."""

    STARTING = "starting"
    RUNNING = "running"
    DRAINING = "draining"
    STOPPING = "stopping"


class DependencyHealthStatus(StrEnum):
    """Shared dependency health 상태."""

    DISABLED = "disabled"
    STARTING = "starting"
    OK = "ok"
    DRAINING = "draining"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class LifecycleSnapshot:
    """라이프사이클 상태의 읽기 전용 snapshot."""

    status: LifecycleStatus
    redis_status: DependencyHealthStatus
    database_status: DependencyHealthStatus
    started_at: datetime
    drain_started_at: datetime | None
    drain_reason: str | None

    @property
    def draining(self) -> bool:
        """현재 상태가 draining인지 반환한다.

        Args:
            None.

        Returns:
            현재 lifecycle 상태가 draining이면 True.
        """
        return self.status is LifecycleStatus.DRAINING

    @property
    def ready(self) -> bool:
        """새 트래픽을 받을 수 있는지 반환한다.

        Args:
            None.

        Returns:
            앱과 dependency가 모두 ready 상태이면 True.
        """
        return (
            self.status is LifecycleStatus.RUNNING
            and dependency_is_ready(self.redis_status)
            and dependency_is_ready(self.database_status)
        )


def dependency_is_ready(status: DependencyHealthStatus) -> bool:
    """Dependency status가 readiness 허용 상태인지 반환한다.

    Args:
        status: 확인할 dependency health 상태.

    Returns:
        disabled 또는 ok처럼 readiness를 허용하는 상태이면 True.
    """
    return status in {
        DependencyHealthStatus.DISABLED,
        DependencyHealthStatus.OK,
    }


class LifecycleState:
    """프로세스 로컬 in-memory lifecycle 상태 저장소."""

    def __init__(self, *, started_at: datetime | None = None) -> None:
        """라이프사이클 state 객체를 초기화한다.

        Args:
            started_at: process 시작 시각. 없으면 현재 UTC 시각.
        """
        self._lock = Lock()
        self._started_at = started_at or datetime.now(UTC)
        self._status = LifecycleStatus.STARTING
        self._redis_status = DependencyHealthStatus.DISABLED
        self._database_status = DependencyHealthStatus.DISABLED
        self._drain_started_at: datetime | None = None
        self._drain_reason: str | None = None

    def mark_running(self) -> None:
        """상태를 running으로 전환한다.

        starting 또는 stopping 상태에서만 running으로 전환한다.
        이미 draining인 상태는 자동 recovery하지 않는다.

        Args:
            None.

        Returns:
            None.
        """
        with self._lock:
            if self._status in {LifecycleStatus.STARTING, LifecycleStatus.STOPPING}:
                self._status = LifecycleStatus.RUNNING

    def mark_stopping(self) -> None:
        """상태를 stopping으로 전환한다.

        Args:
            None.

        Returns:
            None.
        """
        with self._lock:
            self._status = LifecycleStatus.STOPPING
            self._redis_status = _drain_dependency(self._redis_status)
            self._database_status = _drain_dependency(self._database_status)

    def mark_redis_starting(self) -> None:
        """Redis dependency 상태를 starting으로 전환한다.

        Args:
            None.

        Returns:
            None.
        """
        with self._lock:
            self._redis_status = DependencyHealthStatus.STARTING

    def mark_redis_healthy(self) -> None:
        """Redis dependency 상태를 정상으로 전환한다.

        Args:
            None.

        Returns:
            None.
        """
        with self._lock:
            self._redis_status = self._healthy_dependency_status()

    def mark_redis_unavailable(self) -> None:
        """Redis dependency 상태를 unavailable로 전환한다.

        Args:
            None.

        Returns:
            None.
        """
        with self._lock:
            self._redis_status = DependencyHealthStatus.UNAVAILABLE

    def mark_redis_draining(self) -> None:
        """Redis dependency 상태를 draining으로 전환한다.

        Args:
            None.

        Returns:
            None.
        """
        with self._lock:
            self._redis_status = _drain_dependency(self._redis_status)

    def mark_redis_disabled(self) -> None:
        """Redis dependency 상태를 disabled로 전환한다.

        Args:
            None.

        Returns:
            None.
        """
        with self._lock:
            self._redis_status = DependencyHealthStatus.DISABLED

    def mark_database_starting(self) -> None:
        """Database dependency 상태를 starting으로 전환한다.

        Args:
            None.

        Returns:
            None.
        """
        with self._lock:
            self._database_status = DependencyHealthStatus.STARTING

    def mark_database_healthy(self) -> None:
        """Database dependency 상태를 정상으로 전환한다.

        Args:
            None.

        Returns:
            None.
        """
        with self._lock:
            self._database_status = self._healthy_dependency_status()

    def mark_database_unavailable(self) -> None:
        """Database dependency 상태를 unavailable로 전환한다.

        Args:
            None.

        Returns:
            None.
        """
        with self._lock:
            self._database_status = DependencyHealthStatus.UNAVAILABLE

    def mark_database_draining(self) -> None:
        """Database dependency 상태를 draining으로 전환한다.

        Args:
            None.

        Returns:
            None.
        """
        with self._lock:
            self._database_status = _drain_dependency(self._database_status)

    def mark_database_disabled(self) -> None:
        """Database dependency 상태를 disabled로 전환한다.

        Args:
            None.

        Returns:
            None.
        """
        with self._lock:
            self._database_status = DependencyHealthStatus.DISABLED

    def start_draining(self, *, reason: str, now: datetime | None = None) -> bool:
        """상태를 draining으로 전환한다.

        Args:
            reason: 최초 drain 사유.
            now: drain 시작 시각. 없으면 현재 UTC 시각.

        Returns:
            이번 호출에서 처음 draining으로 전환되었으면 True.
        """
        with self._lock:
            if self._status is LifecycleStatus.DRAINING:
                return False
            if self._status is LifecycleStatus.STOPPING:
                return False
            self._status = LifecycleStatus.DRAINING
            self._redis_status = _drain_dependency(self._redis_status)
            self._database_status = _drain_dependency(self._database_status)
            self._drain_started_at = now or datetime.now(UTC)
            self._drain_reason = reason
            return True

    def is_ready(self) -> bool:
        """새 트래픽을 받을 수 있는 상태인지 반환한다.

        Args:
            None.

        Returns:
            현재 snapshot 기준으로 새 트래픽 수신이 가능하면 True.
        """
        with self._lock:
            return (
                self._status is LifecycleStatus.RUNNING
                and dependency_is_ready(self._redis_status)
                and dependency_is_ready(self._database_status)
            )

    def snapshot(self) -> LifecycleSnapshot:
        """현재 lifecycle 상태 snapshot을 반환한다.

        Args:
            None.

        Returns:
            읽기 전용 lifecycle snapshot.
        """
        with self._lock:
            return LifecycleSnapshot(
                status=self._status,
                redis_status=self._redis_status,
                database_status=self._database_status,
                started_at=self._started_at,
                drain_started_at=self._drain_started_at,
                drain_reason=self._drain_reason,
            )

    def _healthy_dependency_status(self) -> DependencyHealthStatus:
        if self._status in {LifecycleStatus.DRAINING, LifecycleStatus.STOPPING}:
            return DependencyHealthStatus.DRAINING
        return DependencyHealthStatus.OK


def _drain_dependency(status: DependencyHealthStatus) -> DependencyHealthStatus:
    if status is DependencyHealthStatus.OK:
        return DependencyHealthStatus.DRAINING
    return status

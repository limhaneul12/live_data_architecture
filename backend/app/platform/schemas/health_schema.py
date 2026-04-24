"""헬스체크 endpoint 응답 payload 모델."""

from __future__ import annotations

from app.platform.lifecycle import (
    DependencyHealthStatus,
    LifecycleSnapshot,
    LifecycleStatus,
)
from app.shared.types import JSONObject
from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr


class HealthPayloadModel(BaseModel):
    """헬스체크 응답 payload 공통 Pydantic 설정."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class LiveHealthPayload(HealthPayloadModel):
    """프로세스 생존 확인 응답."""

    status: StrictStr

    def to_json_value(self) -> JSONObject:
        """직렬화 가능한 live JSON 응답으로 변환한다.

        Args:
            None.

        Returns:
            JSON 직렬화 가능한 live health dictionary.
        """
        return {"status": self.status}


class ReadyHealthChecksPayload(HealthPayloadModel):
    """상태 확인 endpoint에서 사용할 dependency check 상태."""

    app: StrictStr
    redis: StrictStr
    database: StrictStr

    def to_json_value(self) -> JSONObject:
        """직렬화 가능한 checks JSON dictionary로 변환한다.

        Args:
            None.

        Returns:
            app, redis, database check 상태 dictionary.
        """
        return {
            "app": self.app,
            "redis": self.redis,
            "database": self.database,
        }


class ReadyHealthPayload(HealthPayloadModel):
    """새 트래픽 수신 가능 여부 응답."""

    status: StrictStr
    checks: ReadyHealthChecksPayload
    reason: StrictStr | None

    def to_json_value(self) -> JSONObject:
        """직렬화 가능한 ready JSON 응답으로 변환한다.

        Args:
            None.

        Returns:
            JSON 직렬화 가능한 ready health dictionary.
        """
        return {
            "status": self.status,
            "checks": self.checks.to_json_value(),
            "reason": self.reason,
        }


class HeartbeatDetailsPayload(HealthPayloadModel):
    """상세 heartbeat 상태 응답."""

    app: StrictStr
    redis: StrictStr
    database: StrictStr
    lifecycle: StrictStr
    draining: StrictBool
    drain_reason: StrictStr | None
    started_at: StrictStr
    drain_started_at: StrictStr | None

    def to_json_value(self) -> JSONObject:
        """직렬화 가능한 heartbeat 상세 JSON dictionary로 변환한다.

        Args:
            None.

        Returns:
            JSON 직렬화 가능한 heartbeat detail dictionary.
        """
        return {
            "app": self.app,
            "redis": self.redis,
            "database": self.database,
            "lifecycle": self.lifecycle,
            "draining": self.draining,
            "drain_reason": self.drain_reason,
            "started_at": self.started_at,
            "drain_started_at": self.drain_started_at,
        }


class HeartbeatHealthPayload(HealthPayloadModel):
    """상세 heartbeat wrapper 응답."""

    heartbeat: HeartbeatDetailsPayload

    def to_json_value(self) -> JSONObject:
        """직렬화 가능한 heartbeat JSON 응답으로 변환한다.

        Args:
            None.

        Returns:
            JSON 직렬화 가능한 heartbeat wrapper dictionary.
        """
        return {"heartbeat": self.heartbeat.to_json_value()}


def app_check_from_status(status: LifecycleStatus) -> str:
    """상태 값을 app check 문자열로 변환한다.

    Args:
        status: 변환할 lifecycle 상태.

    Returns:
        health payload에 표시할 app check 문자열.
    """
    if status is LifecycleStatus.RUNNING:
        return "ok"
    return status.value


def dependency_check_from_status(status: DependencyHealthStatus) -> str:
    """Dependency 상태 값을 check 문자열로 변환한다.

    Args:
        status: 변환할 dependency health 상태.

    Returns:
        health payload에 표시할 dependency check 문자열.
    """
    return status.value


def ready_payload_from_snapshot(snapshot: LifecycleSnapshot) -> ReadyHealthPayload:
    """상태 snapshot에서 ready 응답 payload를 만든다.

    Args:
        snapshot: 현재 lifecycle 상태 snapshot.

    Returns:
        ready endpoint 응답 payload.
    """
    app_check = app_check_from_status(snapshot.status)
    redis_check = dependency_check_from_status(snapshot.redis_status)
    database_check = dependency_check_from_status(snapshot.database_status)
    if snapshot.ready:
        return ReadyHealthPayload(
            status="ok",
            checks=ReadyHealthChecksPayload(
                app=app_check,
                redis=redis_check,
                database=database_check,
            ),
            reason=None,
        )

    status = "draining" if snapshot.draining else "not_ready"
    reason = snapshot.drain_reason
    if reason is None:
        reason = _dependency_unavailable_reason(snapshot)
    return ReadyHealthPayload(
        status=status,
        checks=ReadyHealthChecksPayload(
            app=app_check,
            redis=redis_check,
            database=database_check,
        ),
        reason=reason,
    )


def heartbeat_payload_from_snapshot(
    snapshot: LifecycleSnapshot,
) -> HeartbeatHealthPayload:
    """상태 snapshot에서 heartbeat 응답 payload를 만든다.

    Args:
        snapshot: 현재 lifecycle 상태 snapshot.

    Returns:
        heartbeat endpoint 응답 payload.
    """
    return HeartbeatHealthPayload(
        heartbeat=HeartbeatDetailsPayload(
            app=app_check_from_status(snapshot.status),
            redis=dependency_check_from_status(snapshot.redis_status),
            database=dependency_check_from_status(snapshot.database_status),
            lifecycle=snapshot.status.value,
            draining=snapshot.draining,
            drain_reason=snapshot.drain_reason,
            started_at=snapshot.started_at.isoformat(),
            drain_started_at=(
                None
                if snapshot.drain_started_at is None
                else snapshot.drain_started_at.isoformat()
            ),
        )
    )


def _dependency_unavailable_reason(snapshot: LifecycleSnapshot) -> str | None:
    if snapshot.database_status is DependencyHealthStatus.UNAVAILABLE:
        return "database_unavailable"
    if snapshot.redis_status is DependencyHealthStatus.UNAVAILABLE:
        return "redis_unavailable"
    return None

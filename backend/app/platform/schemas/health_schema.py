"""헬스체크 endpoint 응답 payload 모델."""

from __future__ import annotations

from app.platform.lifecycle import LifecycleSnapshot, LifecycleStatus
from app.shared.types import JSONObject
from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr


class HealthPayloadModel(BaseModel):
    """헬스체크 응답 payload 공통 Pydantic 설정."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class LiveHealthPayload(HealthPayloadModel):
    """프로세스 생존 확인 응답."""

    status: StrictStr

    def to_json_value(self) -> JSONObject:
        """직렬화 가능한 live JSON 응답으로 변환한다."""
        return {"status": self.status}


class AppHealthCheckPayload(HealthPayloadModel):
    """상태 확인 endpoint에서 사용할 app check 상태."""

    app: StrictStr

    def to_json_value(self) -> JSONObject:
        """직렬화 가능한 checks JSON dictionary로 변환한다."""
        return {"app": self.app}


class ReadyHealthPayload(HealthPayloadModel):
    """새 트래픽 수신 가능 여부 응답."""

    status: StrictStr
    checks: AppHealthCheckPayload
    reason: StrictStr | None

    def to_json_value(self) -> JSONObject:
        """직렬화 가능한 ready JSON 응답으로 변환한다."""
        return {
            "status": self.status,
            "checks": self.checks.to_json_value(),
            "reason": self.reason,
        }


class HeartbeatDetailsPayload(HealthPayloadModel):
    """상세 heartbeat 상태 응답."""

    app: StrictStr
    lifecycle: StrictStr
    draining: StrictBool
    drain_reason: StrictStr | None
    started_at: StrictStr
    drain_started_at: StrictStr | None

    def to_json_value(self) -> JSONObject:
        """직렬화 가능한 heartbeat 상세 JSON dictionary로 변환한다."""
        return {
            "app": self.app,
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
        """직렬화 가능한 heartbeat JSON 응답으로 변환한다."""
        return {"heartbeat": self.heartbeat.to_json_value()}


def app_check_from_status(status: LifecycleStatus) -> str:
    """상태 값을 app check 문자열로 변환한다."""
    if status is LifecycleStatus.RUNNING:
        return "ok"
    return status.value


def ready_payload_from_snapshot(snapshot: LifecycleSnapshot) -> ReadyHealthPayload:
    """상태 snapshot에서 ready 응답 payload를 만든다."""
    app_check = app_check_from_status(snapshot.status)
    if snapshot.ready:
        return ReadyHealthPayload(
            status="ok",
            checks=AppHealthCheckPayload(app=app_check),
            reason=None,
        )

    status = "draining" if snapshot.draining else "not_ready"
    return ReadyHealthPayload(
        status=status,
        checks=AppHealthCheckPayload(app=app_check),
        reason=snapshot.drain_reason,
    )


def heartbeat_payload_from_snapshot(
    snapshot: LifecycleSnapshot,
) -> HeartbeatHealthPayload:
    """상태 snapshot에서 heartbeat 응답 payload를 만든다."""
    return HeartbeatHealthPayload(
        heartbeat=HeartbeatDetailsPayload(
            app=app_check_from_status(snapshot.status),
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

"""헬스체크 FastAPI endpoint 등록 모듈."""

from __future__ import annotations

from app.platform.lifecycle import LifecycleSnapshot, LifecycleState
from app.platform.schemas.health_schema import (
    LiveHealthPayload,
    heartbeat_payload_from_snapshot,
    ready_payload_from_snapshot,
)
from app.shared.serialization import dumps_json
from fastapi import FastAPI, status
from fastapi.responses import Response


def _json_response(payload: bytes, status_code: int) -> Response:
    """직렬화된 orjson bytes를 HTTP JSON 응답으로 감싼다."""
    return Response(
        content=payload,
        status_code=status_code,
        media_type="application/json",
    )


def _status_code_from_snapshot(snapshot: LifecycleSnapshot) -> int:
    """상태 snapshot에서 health HTTP status code를 결정한다."""
    if snapshot.ready:
        return status.HTTP_200_OK
    return status.HTTP_503_SERVICE_UNAVAILABLE


def install_health_routes(app: FastAPI, *, lifecycle: LifecycleState) -> None:
    """애플리케이션에 FastAPI health endpoint를 등록한다.

    인자:
        app: endpoint를 등록할 FastAPI app.
        lifecycle: process-local lifecycle 상태.

    반환:
        없음.
    """

    @app.get("/health/live")
    def get_health_live() -> Response:
        """프로세스 생존 상태를 반환한다."""
        payload = LiveHealthPayload(status="ok")
        return _json_response(
            payload=dumps_json(payload.to_json_value()),
            status_code=status.HTTP_200_OK,
        )

    @app.get("/health/ready")
    def get_health_ready() -> Response:
        """새 트래픽 수신 가능 여부를 반환한다."""
        snapshot = lifecycle.snapshot()
        payload = ready_payload_from_snapshot(snapshot)
        return _json_response(
            payload=dumps_json(payload.to_json_value()),
            status_code=_status_code_from_snapshot(snapshot),
        )

    @app.get("/health/heartbeat")
    def get_health_heartbeat() -> Response:
        """상세 heartbeat 상태를 반환한다."""
        snapshot = lifecycle.snapshot()
        payload = heartbeat_payload_from_snapshot(snapshot)
        return _json_response(
            payload=dumps_json(payload.to_json_value()),
            status_code=_status_code_from_snapshot(snapshot),
        )

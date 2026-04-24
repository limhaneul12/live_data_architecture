"""헬스체크 FastAPI endpoint 등록 모듈."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

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
    """직렬화된 orjson bytes를 HTTP JSON 응답으로 감싼다.

    Args:
        payload: 직렬화가 끝난 JSON bytes.
        status_code: HTTP 응답 상태 코드.

    Returns:
        FastAPI/Starlette JSON response.
    """
    return Response(
        content=payload,
        status_code=status_code,
        media_type="application/json",
    )


def _status_code_from_snapshot(snapshot: LifecycleSnapshot) -> int:
    """상태 snapshot에서 health HTTP status code를 결정한다.

    Args:
        snapshot: 현재 lifecycle 상태 snapshot.

    Returns:
        Ready 상태면 200, 아니면 503.
    """
    if snapshot.ready:
        return status.HTTP_200_OK
    return status.HTTP_503_SERVICE_UNAVAILABLE


DependencyHealthRefresher = Callable[[], Awaitable[None]]


def install_health_routes(
    app: FastAPI,
    *,
    lifecycle: LifecycleState,
    refresh_dependency_health: DependencyHealthRefresher | None = None,
) -> None:
    """애플리케이션에 FastAPI health endpoint를 등록한다.

    Args:
        app: endpoint를 등록할 FastAPI app.
        lifecycle: process-local lifecycle 상태.
        refresh_dependency_health: ready/heartbeat 직전 dependency 상태를 갱신하는 callback.

    Returns:
        없음.
    """

    @app.get("/health/live")
    def get_health_live() -> Response:
        """프로세스 생존 상태를 반환한다.

        Args:
            None.

        Returns:
            Live health JSON response.
        """
        payload = LiveHealthPayload(status="ok")
        return _json_response(
            payload=dumps_json(payload.to_json_value()),
            status_code=status.HTTP_200_OK,
        )

    @app.get("/health/ready")
    async def get_health_ready() -> Response:
        """새 트래픽 수신 가능 여부를 반환한다.

        Args:
            None.

        Returns:
            Ready health JSON response.
        """
        if refresh_dependency_health is not None:
            await refresh_dependency_health()
        snapshot = lifecycle.snapshot()
        payload = ready_payload_from_snapshot(snapshot)
        return _json_response(
            payload=dumps_json(payload.to_json_value()),
            status_code=_status_code_from_snapshot(snapshot),
        )

    @app.get("/health/heartbeat")
    async def get_health_heartbeat() -> Response:
        """상세 heartbeat 상태를 반환한다.

        Args:
            None.

        Returns:
            Heartbeat health JSON response.
        """
        if refresh_dependency_health is not None:
            await refresh_dependency_health()
        snapshot = lifecycle.snapshot()
        payload = heartbeat_payload_from_snapshot(snapshot)
        return _json_response(
            payload=dumps_json(payload.to_json_value()),
            status_code=_status_code_from_snapshot(snapshot),
        )

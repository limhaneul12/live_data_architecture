"""요청 JSON logging middleware 모듈."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from types import FunctionType, MethodType

from app.platform.logging import (
    log_request_exception,
    log_request_outcome,
    resolve_request_id,
    resolve_trace_context,
    should_skip_request_log,
)
from app.shared.serialization import dumps_json
from fastapi import FastAPI, Request
from fastapi.responses import Response


def _resolve_endpoint_name(request: Request) -> str | None:
    """요청 scope에서 endpoint 함수 이름을 찾는다.

    인자:
        request: 들어온 HTTP 요청.

    반환:
        endpoint 함수의 fully-qualified name. 알 수 없으면 None.
    """
    endpoint = request.scope.get("endpoint")
    if endpoint is None:
        return None

    if isinstance(endpoint, FunctionType | MethodType):
        return f"{endpoint.__module__}.{endpoint.__qualname__}"

    return None


def _response_headers(
    *,
    request_id: str,
    trace_id: str | None,
) -> dict[str, str]:
    """요청/trace 식별자를 응답 header로 만든다.

    인자:
        request_id: 요청 식별자.
        trace_id: trace 식별자.

    반환:
        응답에 추가할 header dictionary.
    """
    headers = {"x-request-id": request_id}
    if trace_id is not None:
        headers["x-trace-id"] = trace_id
    return headers


def _apply_response_headers(
    *,
    response: Response,
    request_id: str,
    trace_id: str | None,
) -> None:
    """응답 객체에 request/trace 식별자 header를 추가한다.

    인자:
        response: header를 추가할 응답.
        request_id: 요청 식별자.
        trace_id: trace 식별자.

    반환:
        없음.
    """
    for key, value in _response_headers(
        request_id=request_id,
        trace_id=trace_id,
    ).items():
        response.headers[key] = value


def _request_log_metadata(
    *,
    response: Response,
) -> tuple[int, str, str]:
    """응답 상태에 따른 request log metadata를 결정한다.

    인자:
        response: downstream handler가 반환한 응답.

    반환:
        logging level, event 이름, message 튜플.
    """
    if response.status_code >= 500:
        return (
            logging.ERROR,
            "request_server_error",
            "request completed with server error",
        )
    return logging.INFO, "request_completed", "request completed"


def install_request_logging_middleware(
    app: FastAPI,
    *,
    logger: logging.Logger,
) -> None:
    """애플리케이션에 JSON request logging middleware를 등록한다.

    인자:
        app: middleware를 등록할 FastAPI app.
        logger: request log를 남길 logger.

    반환:
        없음.
    """

    @app.middleware("http")
    async def json_request_logging_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """요청 완료/실패를 JSON 로그로 남긴다.

        인자:
            request: 들어온 HTTP 요청.
            call_next: 다음 ASGI handler.

        반환:
            downstream handler가 반환한 HTTP 응답.
        """
        start = time.perf_counter()
        request_id = resolve_request_id(request)
        trace_id, span_id, tracer_error = resolve_trace_context(request)

        request.state.request_id = request_id
        request.state.trace_id = trace_id

        try:
            response = await call_next(request)
        except Exception as error:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            log_request_exception(
                logger,
                message="request failed",
                event="request_failed",
                request_id=request_id,
                http_method=request.method,
                path=request.url.path,
                status_code=500,
                duration_ms=duration_ms,
                func=_resolve_endpoint_name(request),
                trace_id=trace_id,
                span_id=span_id,
                error=error,
            )
            return Response(
                content=dumps_json(
                    {"detail": "Internal Server Error", "request_id": request_id}
                ),
                status_code=500,
                media_type="application/json",
                headers=_response_headers(request_id=request_id, trace_id=trace_id),
            )

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        level, event, message = _request_log_metadata(response=response)

        if not should_skip_request_log(
            path=request.url.path,
            status_code=response.status_code,
        ):
            log_request_outcome(
                logger,
                level=level,
                message=message,
                event=event,
                request_id=request_id,
                http_method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                func=_resolve_endpoint_name(request),
                trace_id=trace_id,
                span_id=span_id,
                tracer_error=tracer_error,
            )

        _apply_response_headers(
            response=response,
            request_id=request_id,
            trace_id=trace_id,
        )
        return response

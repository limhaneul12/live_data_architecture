"""Shared route exception decorators."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from functools import wraps

from app.shared.exceptions.event_analytics_exceptions import EventAnalyticsRouteError
from fastapi.responses import JSONResponse

type EventAnalyticsErrorPayload = Mapping[str, str | None]
type EventAnalyticsErrorPayloadFactory = Callable[
    [EventAnalyticsRouteError],
    EventAnalyticsErrorPayload,
]


def map_event_analytics_route_errors[**P, R](
    payload_factory: EventAnalyticsErrorPayloadFactory,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R | JSONResponse]]]:
    """Map event analytics route exceptions to structured JSON responses.

    Args:
        payload_factory: Function that serializes one event analytics route error.

    Returns:
        Decorator that converts known route exceptions to JSON.
    """

    def decorator(
        route_handler: Callable[P, Awaitable[R]],
    ) -> Callable[P, Awaitable[R | JSONResponse]]:
        """Wrap a route handler with event analytics error mapping.

        Args:
            route_handler: Async FastAPI route handler that may raise an event
                analytics route exception.

        Returns:
            Wrapped route handler that converts known route exceptions to JSON.
        """

        @wraps(route_handler)
        async def wrapped_handler(
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R | JSONResponse:
            """Execute the wrapped route handler with event analytics error mapping.

            Args:
                *args: Positional arguments forwarded by FastAPI.
                **kwargs: Keyword arguments forwarded by FastAPI.

            Returns:
                Original route result or a structured JSON error response.
            """
            try:
                return await route_handler(*args, **kwargs)
            except EventAnalyticsRouteError as exc:
                return JSONResponse(
                    status_code=exc.status_code,
                    content=dict(payload_factory(exc)),
                )

        return wrapped_handler

    return decorator

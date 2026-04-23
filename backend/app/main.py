"""백엔드 애플리케이션 진입점."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.platform.health_router import install_health_routes
from app.platform.lifecycle import LifecycleState
from app.platform.logging import configure_logging
from app.platform.middleware import install_request_logging_middleware
from fastapi import FastAPI

logger = logging.getLogger(__name__)
lifecycle = LifecycleState()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """애플리케이션 시작 시 logging과 lifecycle을 설정한다.

    인자:
        _app: FastAPI 애플리케이션 인스턴스.

    Yields:
        애플리케이션 lifespan 제어권.
    """
    configure_logging()
    lifecycle.mark_running()
    try:
        yield
    finally:
        lifecycle.mark_stopping()


app = FastAPI(lifespan=lifespan)
install_request_logging_middleware(app, logger=logger)
install_health_routes(app, lifecycle=lifecycle)


def healthcheck() -> dict[str, str]:
    """서비스 health 상태를 반환한다.

    반환:
        health 상태 payload.
    """
    return {"status": "ok"}


@app.get("/health")
def get_health() -> dict[str, str]:
    """헬스체크 HTTP 클라이언트용 payload를 반환한다.

    반환:
        health 상태 payload.
    """
    return healthcheck()

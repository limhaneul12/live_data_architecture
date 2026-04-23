"""백엔드 애플리케이션 진입점."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.platform.config import AppConfig
from app.platform.health_router import install_health_routes
from app.platform.lifecycle import LifecycleState
from app.platform.logging import configure_logging
from app.platform.middleware import install_request_logging_middleware
from fastapi import FastAPI

logger = logging.getLogger(__name__)


def _docs_urls(app_env: str) -> tuple[str | None, str | None]:
    """현재 환경에서 Swagger UI와 ReDoc 노출 여부를 결정한다.

    인자:
        app_env: 서비스 실행 환경 이름.

    반환:
        local 환경에서는 `("/docs", "/redoc")`, 그 외 환경에서는 `(None, None)`.
    """
    if app_env == "local":
        return "/docs", "/redoc"
    return None, None


def _openapi_url(app_env: str) -> str | None:
    """현재 환경에서 OpenAPI 스키마 노출 여부를 결정한다.

    인자:
        app_env: 서비스 실행 환경 이름.

    반환:
        local 환경에서는 `/openapi.json`, 그 외 환경에서는 `None`.
    """
    if app_env == "local":
        return "/openapi.json"
    return None


def create_app(app_config: AppConfig) -> FastAPI:
    """FastAPI 애플리케이션을 생성한다.

    인자:
        app_config: 서비스 공통 설정.

    반환:
        환경별 docs 정책이 적용된 FastAPI 애플리케이션.
    """
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

    # local 환경에서만 문서와 OpenAPI 스키마를 노출한다.
    envs = app_config.app_env
    docs_url, redoc_url = _docs_urls(envs)
    app = FastAPI(
        lifespan=lifespan,
        openapi_url=_openapi_url(envs),
        docs_url=docs_url,
        redoc_url=redoc_url,
    )
    install_request_logging_middleware(app, logger=logger)
    install_health_routes(app, lifecycle=lifecycle)
    return app


app = create_app(AppConfig())

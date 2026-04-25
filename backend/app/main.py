"""백엔드 애플리케이션 진입점."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.event_analytics.application.analytics_connection import (
    build_analytics_connection_info,
)
from app.event_analytics.application.explore_query_service import ExploreQueryService
from app.event_analytics.application.query_policy import AnalyticsSqlPolicy
from app.event_analytics.application.sql_query_service import SqlQueryService
from app.event_analytics.infrastructure.analytics_connection_probe import (
    check_postgres_connection,
)
from app.event_analytics.infrastructure.database_url import to_sqlalchemy_async_url
from app.event_analytics.infrastructure.repositories.postgres_analytics_query_repository import (
    PostgresAnalyticsQueryRepository,
)
from app.event_analytics.interface.consumer_lifespan import (
    EventConsumerRuntime,
    start_event_consumer_runtime,
)
from app.event_analytics.interface.router.analytics_router import (
    install_analytics_routes,
)
from app.platform.config import (
    AnalyticsDatabaseConfig,
    AppConfig,
    DatabaseConfig,
    StreamConfig,
    resolve_analytics_database_address,
)
from app.platform.health_router import install_health_routes
from app.platform.lifecycle import LifecycleState
from app.platform.logging import configure_logging
from app.platform.middleware import install_request_logging_middleware
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)
DEPENDENCY_HEALTH_TIMEOUT_SECONDS = 1.0


def _docs_urls(app_env: str) -> tuple[str | None, str | None]:
    """현재 환경에서 Swagger UI와 ReDoc 노출 여부를 결정한다.

    Args:
        app_env: 서비스 실행 환경 이름.

    Returns:
        local 환경에서는 `("/docs", "/redoc")`, 그 외 환경에서는 `(None, None)`.
    """
    if app_env == "local":
        return "/docs", "/redoc"
    return None, None


def _openapi_url(app_env: str) -> str | None:
    """현재 환경에서 OpenAPI 스키마 노출 여부를 결정한다.

    Args:
        app_env: 서비스 실행 환경 이름.

    Returns:
        local 환경에서는 `/openapi.json`, 그 외 환경에서는 `None`.
    """
    if app_env == "local":
        return "/openapi.json"
    return None


def create_app(app_config: AppConfig) -> FastAPI:
    """FastAPI 애플리케이션을 생성한다.

    Args:
        app_config: 서비스 공통 설정.

    Returns:
        환경별 docs 정책이 적용된 FastAPI 애플리케이션.
    """
    lifecycle = LifecycleState()
    event_consumer_runtime: EventConsumerRuntime | None = None
    database_config = DatabaseConfig()
    analytics_database_config = AnalyticsDatabaseConfig()
    analytics_database_address = resolve_analytics_database_address(
        database_config=database_config,
        analytics_database_config=analytics_database_config,
    )
    analytics_connection_info = build_analytics_connection_info(
        database_config=database_config,
        analytics_database_config=analytics_database_config,
    )
    analytics_engine = create_async_engine(
        to_sqlalchemy_async_url(str(analytics_database_address)),
    )
    analytics_session_factory = async_sessionmaker(
        analytics_engine,
        expire_on_commit=False,
    )
    analytics_query_repository = PostgresAnalyticsQueryRepository(
        session_factory=analytics_session_factory,
    )
    analytics_query_service = SqlQueryService(
        policy=AnalyticsSqlPolicy(),
        repository=analytics_query_repository,
    )
    explore_query_service = ExploreQueryService(
        repository=analytics_query_repository,
    )

    async def refresh_dependency_health() -> None:
        """Refresh runtime dependency health before readiness responses.

        Args:
            None.

        Returns:
            None.
        """
        if event_consumer_runtime is None:
            lifecycle.mark_database_disabled()
            lifecycle.mark_redis_disabled()
            return

        await _refresh_database_health(
            lifecycle=lifecycle,
            runtime=event_consumer_runtime,
        )
        await _refresh_redis_health(
            lifecycle=lifecycle,
            runtime=event_consumer_runtime,
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        """애플리케이션 시작 시 logging과 lifecycle을 설정한다.

        Args:
            _app: FastAPI 애플리케이션 인스턴스.

        Returns:
            애플리케이션 lifespan 제어권.
        """
        nonlocal event_consumer_runtime
        configure_logging()
        if app_config.event_consumer_enabled:
            lifecycle.mark_database_starting()
            lifecycle.mark_redis_starting()
            try:
                event_consumer_runtime = await start_event_consumer_runtime(
                    database_url=str(database_config.db_address),
                    stream_config=StreamConfig(),
                )
            except Exception:
                lifecycle.mark_database_unavailable()
                lifecycle.mark_redis_unavailable()
                raise
            lifecycle.mark_database_healthy()
            lifecycle.mark_redis_healthy()
        lifecycle.mark_running()
        try:
            yield
        finally:
            if event_consumer_runtime is not None:
                lifecycle.mark_database_draining()
                lifecycle.mark_redis_draining()
                await event_consumer_runtime.stop()
                lifecycle.mark_database_disabled()
                lifecycle.mark_redis_disabled()
                event_consumer_runtime = None
            await analytics_engine.dispose()
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
    install_health_routes(
        app,
        lifecycle=lifecycle,
        refresh_dependency_health=refresh_dependency_health,
    )
    install_analytics_routes(
        app,
        query_service=analytics_query_service,
        explore_query_service=explore_query_service,
        connection_info=analytics_connection_info,
        connection_tester=check_postgres_connection,
    )
    return app


app = create_app(AppConfig())


async def _refresh_database_health(
    *,
    lifecycle: LifecycleState,
    runtime: EventConsumerRuntime,
) -> None:
    try:
        await asyncio.wait_for(
            runtime.ping_database(),
            timeout=DEPENDENCY_HEALTH_TIMEOUT_SECONDS,
        )
    except Exception:
        lifecycle.mark_database_unavailable()
        return
    lifecycle.mark_database_healthy()


async def _refresh_redis_health(
    *,
    lifecycle: LifecycleState,
    runtime: EventConsumerRuntime,
) -> None:
    try:
        await asyncio.wait_for(
            runtime.ping_redis(),
            timeout=DEPENDENCY_HEALTH_TIMEOUT_SECONDS,
        )
    except Exception:
        lifecycle.mark_redis_unavailable()
        return
    lifecycle.mark_redis_healthy()

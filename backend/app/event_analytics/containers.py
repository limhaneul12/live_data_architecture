"""Event analytics bounded-context dependency container."""

from __future__ import annotations

from app.event_analytics.application.explore_query_service import ExploreQueryService
from app.event_analytics.application.query_policy import AnalyticsSqlPolicy
from app.event_analytics.application.sql_query_service import SqlQueryService
from app.event_analytics.infrastructure.repositories.postgres_analytics_query_repository import (
    PostgresAnalyticsQueryRepository,
)
from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import async_sessionmaker


class EventAnalyticsContainer(containers.DeclarativeContainer):
    """Compose event analytics repositories and use cases."""

    analytics_session_factory = providers.Dependency(instance_of=async_sessionmaker)

    analytics_query_repository = providers.Singleton(
        PostgresAnalyticsQueryRepository,
        session_factory=analytics_session_factory,
    )
    sql_policy = providers.Factory(AnalyticsSqlPolicy)
    sql_query_service = providers.Factory(
        SqlQueryService,
        policy=sql_policy,
        repository=analytics_query_repository,
    )
    explore_query_service = providers.Factory(
        ExploreQueryService,
        repository=analytics_query_repository,
    )

"""Root dependency container for backend runtime wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.event_analytics.containers import EventAnalyticsContainer
from app.event_analytics.infrastructure.database_url import to_sqlalchemy_async_url
from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


@asynccontextmanager
async def init_analytics_engine(database_address: str) -> AsyncIterator[AsyncEngine]:
    """Create and dispose the root-owned analytics SQLAlchemy engine.

    Args:
        database_address: PostgreSQL database URL used for analytics reads.

    Returns:
        Async context manager yielding the analytics SQLAlchemy engine.
    """
    engine = create_async_engine(to_sqlalchemy_async_url(database_address))
    try:
        yield engine
    finally:
        await engine.dispose()


def build_analytics_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Build the analytics SQLAlchemy async session factory.

    Args:
        engine: Root-owned analytics SQLAlchemy engine.

    Returns:
        Async session factory bound to the analytics engine.
    """
    return async_sessionmaker(engine, expire_on_commit=False)


class Container(containers.DeclarativeContainer):
    """Own root-level dependency wiring for bounded contexts."""

    wiring_config = containers.WiringConfiguration(
        modules=[
            "app.event_analytics.interface.router.analytics_router",
        ],
    )

    database_address = providers.Dependency(instance_of=str)
    analytics_database_address = providers.Dependency(instance_of=str)
    database_engine = providers.Resource(
        init_analytics_engine,
        database_address=database_address,
    )
    analytics_engine = providers.Resource(
        init_analytics_engine,
        database_address=analytics_database_address,
    )
    database_session_factory = providers.Singleton(
        build_analytics_session_factory,
        engine=database_engine,
    )
    analytics_session_factory = providers.Singleton(
        build_analytics_session_factory,
        engine=analytics_engine,
    )
    event_analytics = providers.Container(
        EventAnalyticsContainer,
        analytics_session_factory=analytics_session_factory,
        management_session_factory=database_session_factory,
    )

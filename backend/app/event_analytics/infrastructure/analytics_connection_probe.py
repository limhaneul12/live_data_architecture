"""PostgreSQL connectivity probe for user-submitted analytics DB addresses."""

from __future__ import annotations

from app.event_analytics.constants import ANALYTICS_CONNECTION_TEST_TIMEOUT_SECONDS
from app.event_analytics.domain.analytics_connection import (
    AnalyticsConnectionTestResult,
)
from app.event_analytics.infrastructure.database_url import to_sqlalchemy_async_url
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

MASKED_INVALID_DATABASE_URL = "invalid database URL"
SUPPORTED_POSTGRES_DRIVER_NAMES = frozenset({"postgresql", "postgresql+asyncpg"})


async def check_postgres_connection(
    database_address: str,
) -> AnalyticsConnectionTestResult:
    """Check whether a user-submitted PostgreSQL address is reachable.

    Args:
        database_address: Raw database address submitted from the Connections UI.

    Returns:
        Password-masked PostgreSQL connectivity result.
    """
    masked_address = mask_database_address(database_address)
    try:
        parsed_url = make_url(database_address)
    except ArgumentError:
        return AnalyticsConnectionTestResult(
            database="postgresql",
            address=masked_address,
            reachable=False,
            message="PostgreSQL 주소 형식을 확인할 수 없습니다.",
        )

    if parsed_url.drivername not in SUPPORTED_POSTGRES_DRIVER_NAMES:
        return AnalyticsConnectionTestResult(
            database="postgresql",
            address=masked_address,
            reachable=False,
            message="현재 connection wizard는 PostgreSQL 주소만 지원합니다.",
        )

    engine = create_async_engine(
        to_sqlalchemy_async_url(database_address),
        connect_args={"timeout": ANALYTICS_CONNECTION_TEST_TIMEOUT_SECONDS},
        pool_pre_ping=True,
    )
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (OSError, SQLAlchemyError):
        return AnalyticsConnectionTestResult(
            database="postgresql",
            address=masked_address,
            reachable=False,
            message="DB 주소로 연결할 수 없습니다.",
        )
    finally:
        await engine.dispose()

    return AnalyticsConnectionTestResult(
        database="postgresql",
        address=masked_address,
        reachable=True,
        message="DB 연결에 성공했습니다.",
    )


def mask_database_address(database_address: str) -> str:
    """Mask credentials in a user-submitted database address.

    Args:
        database_address: Raw database DSN submitted from the UI.

    Returns:
        DSN rendered with password hidden, or a safe invalid-address marker.
    """
    try:
        return make_url(database_address).render_as_string(hide_password=True)
    except ArgumentError:
        return MASKED_INVALID_DATABASE_URL

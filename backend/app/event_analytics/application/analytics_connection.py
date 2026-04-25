"""Build safe analytics database connection metadata for the UI."""

from __future__ import annotations

from app.event_analytics.domain.analytics_connection import AnalyticsConnectionInfo
from app.platform.config import (
    AnalyticsDatabaseConfig,
    DatabaseConfig,
    resolve_analytics_database_address,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

MASKED_INVALID_DATABASE_URL = "invalid database URL"


def build_analytics_connection_info(
    *,
    database_config: DatabaseConfig,
    analytics_database_config: AnalyticsDatabaseConfig,
) -> AnalyticsConnectionInfo:
    """Build safe UI metadata for the configured analytics database.

    Args:
        database_config: Writer/consumer database configuration.
        analytics_database_config: Optional analytics read-only database configuration.

    Returns:
        Password-masked analytics connection metadata for the frontend.
    """
    database_address = resolve_analytics_database_address(
        database_config=database_config,
        analytics_database_config=analytics_database_config,
    )
    if analytics_database_config.db_address is None:
        source = "writer_fallback_dsn"
        message = (
            "ANALYTICS_DATABASE_DB_ADDRESS가 없어 writer DB 주소를 fallback으로 "
            "사용 중입니다."
        )
    else:
        source = "analytics_read_only_dsn"
        message = "SQL Lab/Explore는 analytics read-only DB 주소를 사용합니다."

    return AnalyticsConnectionInfo(
        database="postgresql",
        address=mask_database_address(str(database_address)),
        source=source,
        editable=False,
        supported_databases=("postgresql",),
        message=message,
    )


def mask_database_address(database_address: str) -> str:
    """Mask credentials in a database address before sending it to the UI.

    Args:
        database_address: Raw database DSN from settings.

    Returns:
        DSN rendered with password hidden, or a safe invalid-address marker.
    """
    try:
        return make_url(database_address).render_as_string(hide_password=True)
    except ArgumentError:
        return MASKED_INVALID_DATABASE_URL

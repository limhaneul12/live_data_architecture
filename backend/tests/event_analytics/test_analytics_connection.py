import pytest
from app.event_analytics.application.analytics_connection import (
    MASKED_INVALID_DATABASE_URL,
    build_analytics_connection_info,
    mask_database_address,
)
from app.platform.config import AnalyticsDatabaseConfig, DatabaseConfig


def test_mask_database_address_hides_password() -> None:
    masked = mask_database_address(
        "postgresql://analytics_reader:secret@localhost:15432/live_data"
    )

    assert masked == "postgresql://analytics_reader:***@localhost:15432/live_data"


def test_mask_database_address_returns_safe_marker_for_invalid_url() -> None:
    assert mask_database_address("not a valid url") == MASKED_INVALID_DATABASE_URL


def test_build_analytics_connection_info_prefers_read_only_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ANALYTICS_DATABASE_DB_ADDRESS",
        "postgresql://analytics_reader:secret@localhost:15432/live_data",
    )

    connection = build_analytics_connection_info(
        database_config=DatabaseConfig(),
        analytics_database_config=AnalyticsDatabaseConfig(),
    )

    assert connection.database == "postgresql"
    assert connection.address == (
        "postgresql://analytics_reader:***@localhost:15432/live_data"
    )
    assert connection.source == "analytics_read_only_dsn"
    assert connection.editable is False
    assert connection.supported_databases == ("postgresql",)


def test_build_analytics_connection_info_marks_writer_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANALYTICS_DATABASE_DB_ADDRESS", raising=False)

    connection = build_analytics_connection_info(
        database_config=DatabaseConfig(),
        analytics_database_config=AnalyticsDatabaseConfig(),
    )

    assert connection.source == "writer_fallback_dsn"
    assert connection.editable is False

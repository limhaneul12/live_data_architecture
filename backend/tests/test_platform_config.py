import pytest
from app.platform.config import (
    AnalyticsDatabaseConfig,
    AppConfig,
    DatabaseConfig,
    StreamConfig,
    resolve_analytics_database_address,
)


def test_app_config_reads_service_env() -> None:
    config = AppConfig()

    assert config.app_name == "live-data-api"
    assert config.app_env == "local"
    assert config.app_version == "0.1.0"
    assert config.app_log_level == "INFO"
    assert config.event_consumer_enabled is False


def test_database_config_reads_database_address() -> None:
    config = DatabaseConfig()

    assert (
        str(config.db_address)
        == "postgresql://live_data:live_data@localhost:5432/live_data"
    )


def test_analytics_database_config_is_optional() -> None:
    config = AnalyticsDatabaseConfig()

    assert config.db_address is None


def test_resolve_analytics_database_address_falls_back_to_writer_address() -> None:
    database_config = DatabaseConfig()
    analytics_database_config = AnalyticsDatabaseConfig()

    resolved = resolve_analytics_database_address(
        database_config=database_config,
        analytics_database_config=analytics_database_config,
    )

    assert resolved == database_config.db_address


def test_resolve_analytics_database_address_prefers_read_only_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ANALYTICS_DATABASE_DB_ADDRESS",
        "postgresql://analytics_reader:analytics_reader@localhost:5432/live_data",
    )
    database_config = DatabaseConfig()
    analytics_database_config = AnalyticsDatabaseConfig()

    resolved = resolve_analytics_database_address(
        database_config=database_config,
        analytics_database_config=analytics_database_config,
    )

    assert (
        str(resolved)
        == "postgresql://analytics_reader:analytics_reader@localhost:5432/live_data"
    )


def test_stream_config_uses_local_redis_defaults() -> None:
    config = StreamConfig()

    expected = {
        "redis_url": "redis://localhost:6379/0",
        "redis_mode": "single",
        "batch_size": 100,
        "block_ms": 1000,
    }
    assert config.model_dump() == expected
    assert config.redis_urls == ("redis://localhost:6379/0",)

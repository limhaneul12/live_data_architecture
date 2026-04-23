from app.platform.config import AppConfig, DatabaseConfig


def test_app_config_reads_service_env() -> None:
    config = AppConfig()

    assert config.app_name == "live-data-api"
    assert config.app_env == "local"
    assert config.app_version == "0.1.0"
    assert config.app_log_level == "INFO"


def test_database_config_reads_database_address() -> None:
    config = DatabaseConfig()

    assert (
        str(config.db_address)
        == "postgresql://live_data:live_data@localhost:5432/live_data"
    )

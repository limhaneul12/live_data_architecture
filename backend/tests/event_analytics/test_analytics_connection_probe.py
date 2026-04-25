import asyncio

from app.event_analytics.infrastructure.analytics_connection_probe import (
    check_postgres_connection,
)


def test_postgres_connection_probe_rejects_invalid_url() -> None:
    result = asyncio.run(check_postgres_connection("not a valid url"))

    assert result.database == "postgresql"
    assert result.address == "invalid database URL"
    assert result.reachable is False
    assert result.message == "PostgreSQL 주소 형식을 확인할 수 없습니다."


def test_postgres_connection_probe_rejects_non_postgres_url() -> None:
    result = asyncio.run(
        check_postgres_connection("mysql://analytics_reader:secret@localhost/live_data")
    )

    assert result.database == "postgresql"
    assert result.address == "mysql://analytics_reader:***@localhost/live_data"
    assert result.reachable is False
    assert result.message == "현재 connection wizard는 PostgreSQL 주소만 지원합니다."

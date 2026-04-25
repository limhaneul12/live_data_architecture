from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import cast

from app.event_analytics.domain.explore_query import ExploreQuery
from app.event_analytics.domain.query_result import AnalyticsRows
from app.event_analytics.infrastructure.repositories.postgres_analytics_query_repository import (
    ANALYTICS_IDLE_IN_TRANSACTION_TIMEOUT_MS,
    ANALYTICS_LOCK_TIMEOUT_MS,
    ANALYTICS_SEARCH_PATH_SQL,
    ANALYTICS_STATEMENT_TIMEOUT_MS,
    AnalyticsSelectStatement,
    PostgresAnalyticsQueryRepository,
    build_analytics_runtime_guard_sql,
    build_explore_select_statement,
    build_limited_select_sql,
    json_safe_value,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import TextClause


class FakeResult:
    def keys(self) -> tuple[str, ...]:
        return ("event_type",)

    def mappings(self) -> FakeResult:
        return self

    def all(self) -> list[dict[str, str]]:
        return [{"event_type": "page_view"}]


class FakeTransaction:
    async def __aenter__(self) -> FakeTransaction:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class FakeSession:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, int] | None]] = []

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def begin(self) -> FakeTransaction:
        return FakeTransaction()

    async def execute(
        self,
        statement: TextClause | AnalyticsSelectStatement,
        parameters: dict[str, int] | None = None,
    ) -> FakeResult:
        self.executed.append((str(statement), parameters))
        return FakeResult()


class FakeSessionFactory:
    def __init__(self) -> None:
        self.session = FakeSession()

    def __call__(self) -> FakeSession:
        return self.session


def test_postgres_query_repository_wraps_select_with_outer_limit() -> None:
    wrapped_sql = build_limited_select_sql(
        "SELECT event_type, event_count FROM event_type_counts"
    )

    assert wrapped_sql == (
        "SELECT * FROM (SELECT event_type, event_count FROM event_type_counts) "
        "AS analytics_query LIMIT :row_limit"
    )


def test_postgres_query_repository_builds_runtime_guard_sql() -> None:
    guard_sql = build_analytics_runtime_guard_sql()

    assert guard_sql == (
        "SET TRANSACTION READ ONLY",
        f"SET LOCAL search_path = {ANALYTICS_SEARCH_PATH_SQL}",
        f"SET LOCAL statement_timeout = '{ANALYTICS_STATEMENT_TIMEOUT_MS}ms'",
        f"SET LOCAL lock_timeout = '{ANALYTICS_LOCK_TIMEOUT_MS}ms'",
        "SET LOCAL idle_in_transaction_session_timeout = "
        f"'{ANALYTICS_IDLE_IN_TRANSACTION_TIMEOUT_MS}ms'",
    )


def test_postgres_query_repository_applies_runtime_guard_before_query() -> None:
    session_factory = FakeSessionFactory()
    repository = PostgresAnalyticsQueryRepository(
        cast(async_sessionmaker[AsyncSession], session_factory),
    )

    rows = asyncio.run(
        repository.execute_select(
            "SELECT event_type FROM event_type_counts",
            row_limit=10,
        )
    )

    assert rows == AnalyticsRows(
        columns=("event_type",),
        rows=({"event_type": "page_view"},),
    )
    assert session_factory.session.executed == [
        ("SET TRANSACTION READ ONLY", None),
        (f"SET LOCAL search_path = {ANALYTICS_SEARCH_PATH_SQL}", None),
        (f"SET LOCAL statement_timeout = '{ANALYTICS_STATEMENT_TIMEOUT_MS}ms'", None),
        (f"SET LOCAL lock_timeout = '{ANALYTICS_LOCK_TIMEOUT_MS}ms'", None),
        (
            "SET LOCAL idle_in_transaction_session_timeout = "
            f"'{ANALYTICS_IDLE_IN_TRANSACTION_TIMEOUT_MS}ms'",
            None,
        ),
        (
            "SELECT * FROM (SELECT event_type FROM event_type_counts) "
            "AS analytics_query LIMIT :row_limit",
            {"row_limit": 10},
        ),
    ]


def test_build_explore_select_statement_uses_sqlalchemy_core_allowlisted_shape() -> (
    None
):
    statement = build_explore_select_statement(
        ExploreQuery(
            dataset_name="event_type_counts",
            column_names=("event_type", "event_count"),
            order_by="event_count",
            order_direction="desc",
            row_limit=20,
        )
    )

    compiled = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert compiled == (
        "SELECT event_type_counts.event_type, event_type_counts.event_count \n"
        "FROM event_type_counts ORDER BY event_type_counts.event_count DESC \n"
        " LIMIT 20"
    )


def test_postgres_query_repository_executes_explore_query_with_runtime_guard() -> None:
    session_factory = FakeSessionFactory()
    repository = PostgresAnalyticsQueryRepository(
        cast(async_sessionmaker[AsyncSession], session_factory),
    )

    rows = asyncio.run(
        repository.execute_explore_query(
            ExploreQuery(
                dataset_name="event_type_counts",
                column_names=("event_type",),
                order_by=None,
                order_direction="asc",
                row_limit=10,
            )
        )
    )

    assert rows == AnalyticsRows(
        columns=("event_type",),
        rows=({"event_type": "page_view"},),
    )
    assert session_factory.session.executed[-1] == (
        "SELECT event_type_counts.event_type \nFROM event_type_counts\n LIMIT :param_1",
        None,
    )


def test_postgres_query_repository_converts_db_values_to_json_safe_values() -> None:
    converted_values = {
        "decimal": json_safe_value(Decimal("12.34")),
        "datetime": json_safe_value(datetime(2026, 4, 25, tzinfo=UTC)),
        "text": json_safe_value("ok"),
        "number": json_safe_value(3),
        "null": json_safe_value(None),
    }

    assert converted_values == {
        "decimal": 12.34,
        "datetime": "2026-04-25T00:00:00+00:00",
        "text": "ok",
        "number": 3,
        "null": None,
    }

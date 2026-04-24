"""SQLAlchemy repository for safe analytics SELECT execution."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import cast

from app.event_analytics.domain.query_result import AnalyticsRows
from app.event_analytics.domain.repositories.analytics_query_repository import (
    AnalyticsQueryRepository,
)
from app.shared.types import JSONObject, JSONValue
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

type DatabaseScalar = str | int | float | bool | None | Decimal | datetime | date
type DatabaseRow = dict[str, DatabaseScalar]


class AnalyticsQueryExecutionError(Exception):
    """Raised when PostgreSQL cannot execute a validated analytics query."""


class PostgresAnalyticsQueryRepository(AnalyticsQueryRepository):
    """Execute validated analytics SELECT statements against PostgreSQL."""

    def __init__(self, *, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Initialize the repository with a root-owned session factory.

        Args:
            session_factory: Factory that creates SQLAlchemy async sessions.

        Returns:
            None.
        """
        self._session_factory = session_factory

    async def execute_select(self, *, sql: str, row_limit: int) -> AnalyticsRows:
        """Execute a validated read-only SELECT and return JSON-safe rows.

        Args:
            sql: Policy-validated SELECT statement.
            row_limit: Maximum rows returned by the outer query wrapper.

        Returns:
            JSON-safe row set from PostgreSQL.
        """
        limited_sql = build_limited_select_sql(sql=sql)
        try:
            async with self._session_factory() as session, session.begin():
                await session.execute(text("SET TRANSACTION READ ONLY"))
                result = await session.execute(
                    text(limited_sql),
                    {"row_limit": row_limit},
                )
                columns = tuple(result.keys())
                rows = tuple(
                    row_mapping_to_json(row=cast(DatabaseRow, dict(row)))
                    for row in result.mappings().all()
                )
        except SQLAlchemyError as exc:
            raise AnalyticsQueryExecutionError from exc
        return AnalyticsRows(columns=columns, rows=rows)


def build_limited_select_sql(*, sql: str) -> str:
    """Wrap a validated SELECT statement with a server-side outer LIMIT.

    Args:
        sql: Policy-validated SELECT statement.

    Returns:
        SQL statement that applies the repository row limit.
    """
    # Safe by construction: `sql` is accepted only after parser-backed SELECT
    # validation and generated-view allowlist checks in AnalyticsSqlPolicy.
    return f"SELECT * FROM ({sql}) AS analytics_query LIMIT :row_limit"  # noqa: S608


def row_mapping_to_json(*, row: DatabaseRow) -> JSONObject:
    """Convert one SQLAlchemy row mapping into a JSON-safe dictionary.

    Args:
        row: SQLAlchemy row mapping converted to a plain dictionary.

    Returns:
        JSON-safe row dictionary for API serialization.
    """
    return {key: json_safe_value(value) for key, value in row.items()}


def json_safe_value(value: DatabaseScalar) -> JSONValue:
    """Convert a PostgreSQL value into the project's JSON value contract.

    Args:
        value: Raw value returned from SQLAlchemy/PostgreSQL.

    Returns:
        JSON-compatible scalar value.
    """
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)

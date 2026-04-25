"""SQLAlchemy repository for safe analytics SELECT execution."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Final, cast

from app.event_analytics.domain.explore_query import ExploreQuery
from app.event_analytics.domain.query_result import AnalyticsRows
from app.event_analytics.domain.repositories.analytics_query_repository import (
    AnalyticsQueryRepository,
)
from app.shared.types import JSONObject, JSONValue
from sqlalchemy import column, select, table, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import TextClause

type DatabaseScalar = str | int | float | bool | None | Decimal | datetime | date
type DatabaseRow = dict[str, DatabaseScalar]
type AnalyticsSelectStatement = Select[tuple[DatabaseScalar, ...]]

ANALYTICS_STATEMENT_TIMEOUT_MS: Final = 3_000
ANALYTICS_LOCK_TIMEOUT_MS: Final = 500
ANALYTICS_IDLE_IN_TRANSACTION_TIMEOUT_MS: Final = 5_000
ANALYTICS_SEARCH_PATH_SQL: Final = "public, pg_catalog"


class AnalyticsQueryExecutionError(Exception):
    """Raised when PostgreSQL cannot execute a validated analytics query."""


class PostgresAnalyticsQueryRepository(AnalyticsQueryRepository):
    """Execute validated analytics SELECT statements against PostgreSQL."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Initialize the repository with a root-owned session factory.

        Args:
            session_factory: Factory that creates SQLAlchemy async sessions.

        Returns:
            None.
        """
        self._session_factory = session_factory

    async def execute_select(self, sql: str, row_limit: int) -> AnalyticsRows:
        """Execute a validated read-only SELECT and return JSON-safe rows.

        Args:
            sql: Policy-validated SELECT statement.
            row_limit: Maximum rows returned by the outer query wrapper.

        Returns:
            JSON-safe row set from PostgreSQL.
        """
        limited_sql = build_limited_select_sql(sql)
        try:
            return await self._execute_statement(
                text(limited_sql),
                parameters={"row_limit": row_limit},
            )
        except SQLAlchemyError as exc:
            raise AnalyticsQueryExecutionError from exc

    async def execute_explore_query(self, query: ExploreQuery) -> AnalyticsRows:
        """Execute a structured Explore query through SQLAlchemy Core.

        Args:
            query: Validated generated-dataset query contract.

        Returns:
            JSON-safe row set from PostgreSQL.
        """
        statement = build_explore_select_statement(query)
        try:
            return await self._execute_statement(statement, parameters=None)
        except SQLAlchemyError as exc:
            raise AnalyticsQueryExecutionError from exc

    async def _execute_statement(
        self,
        statement: TextClause | AnalyticsSelectStatement,
        parameters: dict[str, int] | None,
    ) -> AnalyticsRows:
        """Execute a prepared analytics statement with PostgreSQL guardrails.

        Args:
            statement: Textual or SQLAlchemy Core SELECT statement.
            parameters: Optional bind parameters for the statement.

        Returns:
            JSON-safe row set from PostgreSQL.
        """
        async with self._session_factory() as session, session.begin():
            for guard_sql in build_analytics_runtime_guard_sql():
                await session.execute(text(guard_sql))
            result = await session.execute(statement, parameters)
            columns = tuple(result.keys())
            rows = tuple(
                row_mapping_to_json(cast(DatabaseRow, dict(row)))
                for row in result.mappings().all()
            )
        return AnalyticsRows(columns=columns, rows=rows)


def build_limited_select_sql(sql: str) -> str:
    """Wrap a validated SELECT statement with a server-side outer LIMIT.

    Args:
        sql: Policy-validated SELECT statement.

    Returns:
        SQL statement that applies the repository row limit.
    """
    # Safe by construction: `sql` is accepted only after parser-backed SELECT
    # validation and generated-view allowlist checks in AnalyticsSqlPolicy.
    return f"SELECT * FROM ({sql}) AS analytics_query LIMIT :row_limit"  # nosec  # noqa: S608


def build_explore_select_statement(query: ExploreQuery) -> AnalyticsSelectStatement:
    """Build a SQLAlchemy Core SELECT for a structured Explore query.

    Args:
        query: Validated generated-dataset query contract.

    Returns:
        SQLAlchemy Core SELECT statement scoped to one generated dataset.
    """
    dataset_table = table(
        query.dataset_name,
        *(column(column_name) for column_name in _required_column_names(query)),
    )
    statement = select(
        *(dataset_table.c[column_name] for column_name in query.column_names)
    ).select_from(dataset_table)
    if query.order_by is not None:
        order_column = dataset_table.c[query.order_by]
        if query.order_direction == "desc":
            statement = statement.order_by(order_column.desc())
        else:
            statement = statement.order_by(order_column.asc())
    return statement.limit(query.row_limit)


def _required_column_names(query: ExploreQuery) -> tuple[str, ...]:
    """Return projection and ordering columns needed to build the SQL table clause.

    Args:
        query: Validated generated-dataset query contract.

    Returns:
        Unique column names required by SELECT and ORDER BY.
    """
    column_names = list(query.column_names)
    if query.order_by is not None and query.order_by not in column_names:
        column_names.append(query.order_by)
    return tuple(column_names)


def build_analytics_runtime_guard_sql() -> tuple[str, ...]:
    """Build PostgreSQL session guardrails for manual analytics SQL.

    Args:
        None.

    Returns:
        SQL statements that make the current transaction read-only and bounded.
    """
    return (
        "SET TRANSACTION READ ONLY",
        f"SET LOCAL search_path = {ANALYTICS_SEARCH_PATH_SQL}",
        f"SET LOCAL statement_timeout = '{ANALYTICS_STATEMENT_TIMEOUT_MS}ms'",
        f"SET LOCAL lock_timeout = '{ANALYTICS_LOCK_TIMEOUT_MS}ms'",
        "SET LOCAL idle_in_transaction_session_timeout = "
        f"'{ANALYTICS_IDLE_IN_TRANSACTION_TIMEOUT_MS}ms'",
    )


def row_mapping_to_json(row: DatabaseRow) -> JSONObject:
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

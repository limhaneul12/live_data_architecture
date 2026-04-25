"""SQLAlchemy repository for safe analytics SELECT execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final, cast

from app.event_analytics.domain.analytics_catalog import (
    AnalyticsDataset,
    AnalyticsDatasetColumn,
    AnalyticsViewTable,
    ColumnKind,
)
from app.event_analytics.domain.explore_query import ExploreColumnRef, ExploreQuery
from app.event_analytics.domain.query_result import AnalyticsRows
from app.event_analytics.domain.repositories.analytics_dataset_repository import (
    AnalyticsDatasetRepository,
)
from app.event_analytics.domain.repositories.analytics_query_repository import (
    AnalyticsQueryRepository,
)
from app.event_analytics.infrastructure.repositories.postgres_event_repository import (
    EventAnalyticsBase,
)
from app.shared.exceptions import (
    EventAnalyticsDatabaseExecutionError as AnalyticsQueryExecutionError,
)
from app.shared.types import JSONObject, JSONValue
from sqlalchemy import DateTime, Integer, Text, column, func, select, table, text
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement, TextClause
from sqlalchemy.sql.selectable import TableClause

type DatabaseScalar = str | int | float | bool | None | Decimal | datetime | date
type DatabaseRow = dict[str, DatabaseScalar]
type AnalyticsSelectStatement = Select[tuple[DatabaseScalar, ...]]

ANALYTICS_STATEMENT_TIMEOUT_MS: Final = 3_000
ANALYTICS_LOCK_TIMEOUT_MS: Final = 500
ANALYTICS_IDLE_IN_TRANSACTION_TIMEOUT_MS: Final = 5_000
ANALYTICS_SEARCH_PATH_SQL: Final = "public, pg_catalog"
INFORMATION_SCHEMA_COLUMNS: Final = table(
    "columns",
    column("table_schema", Text),
    column("table_name", Text),
    column("column_name", Text),
    column("data_type", Text),
    column("ordinal_position", Integer),
    schema="information_schema",
)


@dataclass(slots=True)
class ViewTableAccumulator:
    """Mutable accumulator for view table metadata rows."""

    description: str
    source_sql: str
    columns: list[AnalyticsDatasetColumn]


class AnalyticsViewTableRecord(EventAnalyticsBase):
    """ORM mapped row for user-created analytics view table metadata."""

    __tablename__ = "analytics_view_tables"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_sql: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PostgresAnalyticsQueryRepository(
    AnalyticsQueryRepository,
    AnalyticsDatasetRepository,
):
    """Execute validated analytics SELECT statements against PostgreSQL."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        management_session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        """Initialize the repository with a root-owned session factory.

        Args:
            session_factory: Factory that creates analytics read sessions.
            management_session_factory: Optional factory for view table DDL and
                metadata operations.

        Returns:
            None.
        """
        self._session_factory = session_factory
        self._management_session_factory = management_session_factory or session_factory

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

    async def list_view_table_datasets(self) -> tuple[AnalyticsDataset, ...]:
        """Return datasets backed by user-created view tables.

        Args:
            None.

        Returns:
            Dynamic analytics dataset descriptors.
        """
        view_tables = await self.list_view_tables()
        return tuple(dataset_from_view_table(view_table) for view_table in view_tables)

    async def list_view_tables(self) -> tuple[AnalyticsViewTable, ...]:
        """Return user-created view table metadata.

        Args:
            None.

        Returns:
            User-created view table metadata with current columns.
        """
        try:
            async with self._management_session_factory() as session:
                return await load_view_tables(session, name=None)
        except SQLAlchemyError as exc:
            raise AnalyticsQueryExecutionError from exc

    async def create_or_replace_view_table(
        self,
        name: str,
        description: str,
        source_sql: str,
    ) -> AnalyticsViewTable:
        """Create or replace one analytics view table and persist metadata.

        Args:
            name: Validated view table name.
            description: Human-readable view table description.
            source_sql: Policy-validated SELECT SQL used as view source.

        Returns:
            Created or updated view table metadata.
        """
        reader_role_name = await self._analytics_reader_role_name()
        try:
            async with self._management_session_factory() as session, session.begin():
                await session.execute(
                    text(build_create_view_table_sql(name, source_sql))
                )
                await session.execute(
                    text(build_grant_view_table_sql(name, reader_role_name))
                )
                await session.execute(
                    build_upsert_view_table_metadata_statement(
                        name=name,
                        description=description,
                        source_sql=source_sql,
                    )
                )
                view_tables = await load_view_tables(session, name=name)
        except SQLAlchemyError as exc:
            raise AnalyticsQueryExecutionError from exc
        return view_tables[0]

    async def _analytics_reader_role_name(self) -> str:
        """Return the PostgreSQL role used for analytics read queries.

        Args:
            None.

        Returns:
            Current database role name from the analytics read connection.
        """
        try:
            async with self._session_factory() as session:
                result = await session.execute(text("SELECT current_user"))
        except SQLAlchemyError as exc:
            raise AnalyticsQueryExecutionError from exc
        return str(result.scalar_one())

    async def preview_view_table_sql(
        self,
        source_sql: str,
        row_limit: int,
    ) -> AnalyticsRows:
        """Preview a validated view table SELECT before saving.

        Args:
            source_sql: Policy-validated SELECT SQL used as view source.
            row_limit: Maximum preview rows returned.

        Returns:
            JSON-safe preview rows.
        """
        limited_sql = build_limited_select_sql(source_sql)
        try:
            return await self._execute_statement(
                text(limited_sql),
                parameters={"row_limit": row_limit},
                session_factory=self._management_session_factory,
            )
        except SQLAlchemyError as exc:
            raise AnalyticsQueryExecutionError from exc

    async def _execute_statement(
        self,
        statement: TextClause | AnalyticsSelectStatement,
        parameters: dict[str, int] | None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> AnalyticsRows:
        """Execute a prepared analytics statement with PostgreSQL guardrails.

        Args:
            statement: Textual or SQLAlchemy Core SELECT statement.
            parameters: Optional bind parameters for the statement.
            session_factory: Optional session factory override.

        Returns:
            JSON-safe row set from PostgreSQL.
        """
        active_session_factory = session_factory or self._session_factory
        async with active_session_factory() as session, session.begin():
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


def build_create_view_table_sql(name: str, source_sql: str) -> str:
    """Build DDL for a validated user-created analytics view table.

    Args:
        name: Validated lowercase view table name.
        source_sql: Policy-validated SELECT SQL.

    Returns:
        PostgreSQL CREATE OR REPLACE VIEW statement.
    """
    return f"CREATE OR REPLACE VIEW {name} AS {source_sql}"  # nosec


def build_grant_view_table_sql(name: str, role_name: str) -> str:
    """Build DCL that lets the analytics read role query a saved view table.

    Args:
        name: Validated lowercase view table name.
        role_name: Database role name read from the analytics connection.

    Returns:
        PostgreSQL GRANT statement for the saved view table.
    """
    return f"GRANT SELECT ON TABLE {name} TO {quoted_identifier(role_name)}"  # nosec


def quoted_identifier(identifier: str) -> str:
    """Quote a PostgreSQL identifier.

    Args:
        identifier: Raw database identifier.

    Returns:
        Double-quoted PostgreSQL identifier.
    """
    return '"' + identifier.replace('"', '""') + '"'


def build_upsert_view_table_metadata_statement(
    name: str,
    description: str,
    source_sql: str,
):
    """Build an ORM-backed upsert for user-created view table metadata.

    Args:
        name: Validated view table name.
        description: View table description.
        source_sql: Policy-validated view source SELECT.

    Returns:
        PostgreSQL insert statement with conflict update.
    """
    statement = postgres_insert(AnalyticsViewTableRecord).values(
        name=name,
        description=description,
        source_sql=source_sql,
    )
    return statement.on_conflict_do_update(
        index_elements=[AnalyticsViewTableRecord.name],
        set_={
            "description": statement.excluded.description,
            "source_sql": statement.excluded.source_sql,
            "updated_at": func.now(),
        },
    )


def build_explore_select_statement(query: ExploreQuery) -> AnalyticsSelectStatement:
    """Build a SQLAlchemy Core SELECT for a structured Explore query.

    Args:
        query: Validated generated-dataset query contract.

    Returns:
        SQLAlchemy Core SELECT statement scoped to one generated dataset.
    """
    required_columns_by_dataset = _required_columns_by_dataset(query)
    dataset_tables = {
        dataset_name: table(
            dataset_name,
            *(column(column_name) for column_name in column_names),
        )
        for dataset_name, column_names in required_columns_by_dataset.items()
    }
    dataset_table = dataset_tables[query.dataset_name]
    selectable = dataset_table
    for join in query.joins:
        join_table = dataset_tables[join.dataset_name]
        selectable = selectable.join(
            join_table,
            dataset_table.c[join.left_column] == join_table.c[join.right_column],
            isouter=join.join_type == "left",
        )
    statement = select(
        *(
            selected_column_expression(
                column_ref,
                dataset_tables=dataset_tables,
                use_qualified_label=bool(query.joins),
            )
            for column_ref in query.column_refs
        )
    ).select_from(selectable)
    if query.order_by is not None:
        order_column = dataset_tables[query.order_by.dataset_name].c[
            query.order_by.column_name
        ]
        if query.order_direction == "desc":
            statement = statement.order_by(order_column.desc())
        else:
            statement = statement.order_by(order_column.asc())
    return statement.limit(query.row_limit)


def selected_column_expression(
    column_ref: ExploreColumnRef,
    dataset_tables: dict[str, TableClause],
    use_qualified_label: bool,
) -> ColumnElement[DatabaseScalar]:
    """Return one SQLAlchemy column expression for an Explore projection.

    Args:
        column_ref: Dataset column reference selected by the frontend.
        dataset_tables: SQLAlchemy table clauses keyed by dataset name.
        use_qualified_label: Whether joined queries should label output columns.

    Returns:
        SQLAlchemy selectable column expression.
    """
    dataset_table = dataset_tables[column_ref.dataset_name]
    expression = dataset_table.c[column_ref.column_name]
    if not use_qualified_label:
        return expression
    return expression.label(output_column_name(column_ref))


def output_column_name(column_ref: ExploreColumnRef) -> str:
    """Return a stable output column alias for joined Explore queries.

    Args:
        column_ref: Dataset column reference selected by the frontend.

    Returns:
        Qualified output column name.
    """
    return f"{column_ref.dataset_name}_{column_ref.column_name}"


def _required_columns_by_dataset(query: ExploreQuery) -> dict[str, tuple[str, ...]]:
    """Return all columns needed to build SQLAlchemy table clauses.

    Args:
        query: Validated generated-dataset query contract.

    Returns:
        Dataset names mapped to unique required column names.
    """
    column_names_by_dataset: dict[str, list[str]] = {query.dataset_name: []}
    for column_ref in query.column_refs:
        append_unique_column(column_names_by_dataset, column_ref)
    if query.order_by is not None:
        append_unique_column(column_names_by_dataset, query.order_by)
    for join in query.joins:
        append_unique_column(
            column_names_by_dataset,
            ExploreColumnRef(
                dataset_name=query.dataset_name,
                column_name=join.left_column,
            ),
        )
        append_unique_column(
            column_names_by_dataset,
            ExploreColumnRef(
                dataset_name=join.dataset_name,
                column_name=join.right_column,
            ),
        )
    return {
        dataset_name: tuple(column_names)
        for dataset_name, column_names in column_names_by_dataset.items()
    }


def append_unique_column(
    column_names_by_dataset: dict[str, list[str]],
    column_ref: ExploreColumnRef,
) -> None:
    """Append a dataset column to a required-column map once.

    Args:
        column_names_by_dataset: Mutable required-column map.
        column_ref: Dataset column reference to append.

    Returns:
        None.
    """
    column_names = column_names_by_dataset.setdefault(column_ref.dataset_name, [])
    if column_ref.column_name not in column_names:
        column_names.append(column_ref.column_name)


def dataset_from_view_table(view_table: AnalyticsViewTable) -> AnalyticsDataset:
    """Convert one saved view table into a dataset descriptor.

    Args:
        view_table: User-created view table metadata.

    Returns:
        Dynamic analytics dataset descriptor.
    """
    return AnalyticsDataset(
        name=view_table.name,
        label=view_table.name,
        description=view_table.description,
        columns=view_table.columns,
        origin="view_table",
    )


async def load_view_tables(
    session: AsyncSession,
    name: str | None,
) -> tuple[AnalyticsViewTable, ...]:
    """Load user-created view table metadata and current column shapes.

    Args:
        session: Active SQLAlchemy async session.
        name: Optional view table name filter.

    Returns:
        User-created view table metadata.
    """
    result = await session.execute(build_view_table_metadata_select_statement(name))
    grouped_view_tables: dict[str, ViewTableAccumulator] = {}
    for row in result.mappings().all():
        view_name = str(row["name"])
        view_table = grouped_view_tables.setdefault(
            view_name,
            ViewTableAccumulator(
                description=str(row["description"]),
                source_sql=str(row["source_sql"]),
                columns=[],
            ),
        )
        column_name = row["column_name"]
        if column_name is not None:
            view_table.columns.append(
                AnalyticsDatasetColumn(
                    name=str(column_name),
                    label=str(column_name),
                    kind=column_kind_from_postgres_type(str(row["data_type"])),
                )
            )
    return tuple(
        AnalyticsViewTable(
            name=view_name,
            description=view_table.description,
            source_sql=view_table.source_sql,
            columns=tuple(view_table.columns),
        )
        for view_name, view_table in grouped_view_tables.items()
    )


def build_view_table_metadata_select_statement(
    name: str | None,
) -> AnalyticsSelectStatement:
    """Build a Core metadata query for user-created view tables.

    Args:
        name: Optional view table name filter.

    Returns:
        SQLAlchemy Core SELECT for metadata and information_schema column lookup.
    """
    view_tables = AnalyticsViewTableRecord.__table__
    information_schema_columns = INFORMATION_SCHEMA_COLUMNS
    statement = (
        select(
            view_tables.c.name.label("name"),
            view_tables.c.description.label("description"),
            view_tables.c.source_sql.label("source_sql"),
            information_schema_columns.c.column_name.label("column_name"),
            information_schema_columns.c.data_type.label("data_type"),
            information_schema_columns.c.ordinal_position.label("ordinal_position"),
        )
        .select_from(
            view_tables.outerjoin(
                information_schema_columns,
                (information_schema_columns.c.table_schema == "public")
                & (information_schema_columns.c.table_name == view_tables.c.name),
            )
        )
        .order_by(
            view_tables.c.name,
            information_schema_columns.c.ordinal_position,
        )
    )
    if name is not None:
        statement = statement.where(view_tables.c.name == name)
    return cast(AnalyticsSelectStatement, statement)


def column_kind_from_postgres_type(data_type: str) -> ColumnKind:
    """Infer frontend column kind from a PostgreSQL information_schema type.

    Args:
        data_type: PostgreSQL information_schema column type.

    Returns:
        Dataset column kind used by Chart Builder.
    """
    normalized_type = data_type.lower()
    if normalized_type in {
        "bigint",
        "double precision",
        "integer",
        "numeric",
        "real",
        "smallint",
    }:
        return "metric"
    if "timestamp" in normalized_type or normalized_type in {"date", "time"}:
        return "temporal"
    return "dimension"


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

"""Application service for user-created analytics view tables."""

from __future__ import annotations

import re
from typing import Final

from app.event_analytics.application.analytics_catalog import ALLOWED_DATASET_NAMES
from app.event_analytics.application.analytics_catalog_service import (
    AnalyticsCatalogService,
)
from app.event_analytics.application.chart_suggestion import suggest_chart
from app.event_analytics.application.query_policy import (
    AnalyticsSqlPolicy,
    ValidatedSqlQuery,
)
from app.event_analytics.domain.analytics_catalog import (
    AnalyticsDataset,
    AnalyticsViewTable,
)
from app.event_analytics.domain.query_result import AnalyticsQueryResult
from app.event_analytics.domain.repositories.analytics_dataset_repository import (
    AnalyticsDatasetRepository,
)
from app.shared.exceptions import (
    EventAnalyticsDatabaseExecutionError,
    EventAnalyticsSqlPolicyViolationError,
    EventAnalyticsViewTableExecutionUnavailableError,
    EventAnalyticsViewTableValidationError,
)

MAX_VIEW_TABLE_ROW_LIMIT: Final = 100
MAX_VIEW_TABLE_DESCRIPTION_LENGTH: Final = 240
VIEW_TABLE_NAME_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]{2,50}$")
VIEW_TABLE_SOURCE_RELATION_NAMES: Final = frozenset({"events"})


class ViewTableService:
    """Validate, preview, and save user-created analytics view tables."""

    def __init__(
        self,
        repository: AnalyticsDatasetRepository,
        catalog_service: AnalyticsCatalogService,
        policy: AnalyticsSqlPolicy,
    ) -> None:
        """Initialize the view table service.

        Args:
            repository: Repository that persists view metadata and DDL.
            catalog_service: Service that lists built-in and dynamic datasets.
            policy: SQL SELECT validator reused for view source SQL.

        Returns:
            None.
        """
        self._repository = repository
        self._catalog_service = catalog_service
        self._policy = policy

    async def preview(self, source_sql: str, row_limit: int) -> AnalyticsQueryResult:
        """Preview one view table source SELECT before saving.

        Args:
            source_sql: User-submitted SELECT SQL.
            row_limit: Requested preview row limit.

        Returns:
            Preview query result with chart metadata.
        """
        validated = await self._validate_source_sql(
            source_sql,
            requested_row_limit=row_limit,
        )
        try:
            rows = await self._repository.preview_view_table_sql(
                source_sql=validated.sql,
                row_limit=validated.row_limit,
            )
        except EventAnalyticsDatabaseExecutionError as exc:
            raise EventAnalyticsViewTableExecutionUnavailableError from exc
        return AnalyticsQueryResult(
            columns=rows.columns,
            rows=rows.rows,
            chart=suggest_chart(rows),
        )

    async def create(
        self,
        name: str,
        description: str,
        source_sql: str,
    ) -> AnalyticsDataset:
        """Create or replace one view table and expose it as a dataset.

        Args:
            name: User-submitted view table name.
            description: User-submitted view table description.
            source_sql: User-submitted SELECT SQL.

        Returns:
            Dataset descriptor for the saved view table.
        """
        normalized_name = normalized_view_table_name(name)
        normalized_description = normalized_view_table_description(description)
        await self._ensure_name_is_not_reserved(normalized_name)
        validated = await self._validate_source_sql(source_sql, requested_row_limit=1)
        try:
            view_table = await self._repository.create_or_replace_view_table(
                name=normalized_name,
                description=normalized_description,
                source_sql=validated.sql,
            )
        except EventAnalyticsDatabaseExecutionError as exc:
            raise EventAnalyticsViewTableExecutionUnavailableError from exc
        return dataset_from_view_table(view_table)

    async def delete(self, name: str) -> None:
        """Delete one user-created view table.

        Args:
            name: User-submitted view table name.

        Returns:
            None.
        """
        normalized_name = normalized_view_table_name(name)
        await self._ensure_name_is_not_reserved(normalized_name)
        try:
            await self._repository.delete_view_table(normalized_name)
        except EventAnalyticsDatabaseExecutionError as exc:
            raise EventAnalyticsViewTableExecutionUnavailableError from exc

    async def _validate_source_sql(
        self,
        source_sql: str,
        requested_row_limit: int,
    ) -> ValidatedSqlQuery:
        """Validate source SQL against view table relation boundaries.

        Args:
            source_sql: User-submitted SELECT SQL.
            requested_row_limit: Requested row limit for validation capping.

        Returns:
            Validated SQL contract from the shared SQL policy.
        """
        allowed_relations = await self._view_table_source_relations()
        try:
            return self._policy.validate(
                sql=source_sql,
                requested_row_limit=min(requested_row_limit, MAX_VIEW_TABLE_ROW_LIMIT),
                allowed_relations=allowed_relations,
            )
        except EventAnalyticsSqlPolicyViolationError as exc:
            raise EventAnalyticsViewTableValidationError(
                exc.reason,
                message=exc.message,
            ) from exc

    async def _view_table_source_relations(self) -> frozenset[str]:
        """Return relations that may be used to define a view table.

        Args:
            None.

        Returns:
            Relation allowlist for view table source SQL.
        """
        return (
            await self._catalog_service.allowed_dataset_names()
        ) | VIEW_TABLE_SOURCE_RELATION_NAMES

    async def _ensure_name_is_not_reserved(self, name: str) -> None:
        """Reject names that collide with protected base relations.

        Args:
            name: Normalized view table name.

        Returns:
            None.
        """
        if name in ALLOWED_DATASET_NAMES or name in VIEW_TABLE_SOURCE_RELATION_NAMES:
            raise EventAnalyticsViewTableValidationError(
                "reserved_view_table_name",
                message="built-in dataset이나 원본 table 이름은 view table 이름으로 사용할 수 없습니다.",
            )


def normalized_view_table_name(name: str) -> str:
    """Normalize and validate a user-created view table name.

    Args:
        name: Raw view table name from the API request.

    Returns:
        Lowercase validated view table name.
    """
    normalized_name = name.strip().lower()
    if VIEW_TABLE_NAME_PATTERN.fullmatch(normalized_name) is None:
        raise EventAnalyticsViewTableValidationError(
            "invalid_view_table_name",
            message="view table 이름은 소문자/숫자/underscore만 사용할 수 있습니다.",
        )
    return normalized_name


def normalized_view_table_description(description: str) -> str:
    """Normalize and validate a user-created view table description.

    Args:
        description: Raw description from the API request.

    Returns:
        Trimmed description.
    """
    normalized_description = description.strip()
    if len(normalized_description) > MAX_VIEW_TABLE_DESCRIPTION_LENGTH:
        raise EventAnalyticsViewTableValidationError(
            "view_table_description_too_long",
            message=(
                "view table 설명은 "
                f"{MAX_VIEW_TABLE_DESCRIPTION_LENGTH}자 이하만 허용합니다."
            ),
        )
    return normalized_description


def dataset_from_view_table(view_table: AnalyticsViewTable) -> AnalyticsDataset:
    """Convert saved view table metadata into a chartable dataset descriptor.

    Args:
        view_table: Persisted view table metadata.

    Returns:
        Dataset descriptor exposed to Chart Builder and SQL Lab.
    """
    return AnalyticsDataset(
        name=view_table.name,
        label=view_table.name,
        description=view_table.description,
        columns=view_table.columns,
        origin="view_table",
    )

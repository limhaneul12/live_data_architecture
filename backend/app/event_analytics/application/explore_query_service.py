"""Application service for structured Superset-style Explore queries."""

from __future__ import annotations

from app.event_analytics.application.analytics_catalog import get_datasets
from app.event_analytics.application.chart_suggestion import suggest_chart
from app.event_analytics.domain.analytics_catalog import AnalyticsDataset
from app.event_analytics.domain.explore_query import ExploreQuery, ExploreSortDirection
from app.event_analytics.domain.query_result import AnalyticsQueryResult
from app.event_analytics.domain.repositories.analytics_query_repository import (
    AnalyticsQueryRepository,
)

MAX_EXPLORE_QUERY_ROW_LIMIT = 500


class ExploreQueryValidationError(Exception):
    """Raised when a structured Explore request is outside the dataset catalog."""

    def __init__(self, reason: str, message: str) -> None:
        """Initialize a structured query validation error.

        Args:
            reason: Stable machine-readable rejection reason.
            message: Human-readable rejection detail.

        Returns:
            None.
        """
        super().__init__(message)
        self.reason = reason
        self.message = message


class ExploreQueryService:
    """Validate structured Explore requests and execute them through a repository."""

    def __init__(self, repository: AnalyticsQueryRepository) -> None:
        """Initialize the Explore query service.

        Args:
            repository: Read repository for generated analytics datasets.

        Returns:
            None.
        """
        self._repository = repository

    async def execute(
        self,
        dataset_name: str,
        column_names: tuple[str, ...],
        order_by: str | None,
        order_direction: ExploreSortDirection,
        row_limit: int,
    ) -> AnalyticsQueryResult:
        """Execute one validated structured Explore query.

        Args:
            dataset_name: Generated dataset selected by the frontend.
            column_names: Dataset columns selected for projection.
            order_by: Optional dataset column used for ordering.
            order_direction: Sort direction for the optional ordering column.
            row_limit: Requested maximum row count.

        Returns:
            Query result with JSON-safe rows and chart suggestion.
        """
        query = build_explore_query(
            dataset_name,
            column_names=column_names,
            order_by=order_by,
            order_direction=order_direction,
            row_limit=row_limit,
        )
        rows = await self._repository.execute_explore_query(query)
        return AnalyticsQueryResult(
            columns=rows.columns,
            rows=rows.rows,
            chart=suggest_chart(rows),
        )


def build_explore_query(
    dataset_name: str,
    column_names: tuple[str, ...],
    order_by: str | None,
    order_direction: ExploreSortDirection,
    row_limit: int,
) -> ExploreQuery:
    """Build a validated internal structured query from frontend controls.

    Args:
        dataset_name: Generated dataset selected by the frontend.
        column_names: Dataset columns selected for projection.
        order_by: Optional dataset column used for ordering.
        order_direction: Sort direction for the optional ordering column.
        row_limit: Requested maximum row count.

    Returns:
        Validated structured query with a capped row limit.
    """
    dataset = _find_dataset(dataset_name)
    allowed_columns = frozenset(column.name for column in dataset.columns)
    _ensure_selected_columns_are_allowed(
        column_names,
        allowed_columns=allowed_columns,
    )
    _ensure_order_column_is_allowed(order_by, allowed_columns)
    return ExploreQuery(
        dataset_name=dataset.name,
        column_names=column_names,
        order_by=order_by,
        order_direction=order_direction,
        row_limit=min(row_limit, MAX_EXPLORE_QUERY_ROW_LIMIT),
    )


def _find_dataset(dataset_name: str) -> AnalyticsDataset:
    """Find one generated dataset by name.

    Args:
        dataset_name: Dataset name requested by the frontend.

    Returns:
        Matching generated dataset descriptor.
    """
    for dataset in get_datasets():
        if dataset.name == dataset_name:
            return dataset
    raise ExploreQueryValidationError(
        "unknown_dataset",
        message="알 수 없는 analytics dataset입니다.",
    )


def _ensure_selected_columns_are_allowed(
    selected_columns: tuple[str, ...],
    allowed_columns: frozenset[str],
) -> None:
    """Reject empty, duplicated, or unknown projection columns.

    Args:
        selected_columns: Dataset columns requested by the frontend.
        allowed_columns: Column allowlist from the dataset catalog.

    Returns:
        None.
    """
    if not selected_columns:
        raise ExploreQueryValidationError(
            "missing_columns",
            message="Explore query에는 최소 1개 이상의 column이 필요합니다.",
        )
    if len(selected_columns) != len(set(selected_columns)):
        raise ExploreQueryValidationError(
            "duplicate_columns",
            message="Explore query column은 중복될 수 없습니다.",
        )
    if any(column_name not in allowed_columns for column_name in selected_columns):
        raise ExploreQueryValidationError(
            "unknown_column",
            message="dataset에 없는 column은 조회할 수 없습니다.",
        )


def _ensure_order_column_is_allowed(
    order_by: str | None,
    allowed_columns: frozenset[str],
) -> None:
    """Reject unknown ordering columns.

    Args:
        order_by: Optional ordering column requested by the frontend.
        allowed_columns: Column allowlist from the dataset catalog.

    Returns:
        None.
    """
    if order_by is not None and order_by not in allowed_columns:
        raise ExploreQueryValidationError(
            "unknown_order_column",
            message="dataset에 없는 column으로 정렬할 수 없습니다.",
        )

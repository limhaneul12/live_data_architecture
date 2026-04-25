"""Application service for structured Superset-style Explore queries."""

from __future__ import annotations

from app.event_analytics.application.analytics_catalog import get_datasets
from app.event_analytics.application.analytics_catalog_service import (
    AnalyticsCatalogService,
)
from app.event_analytics.application.chart_suggestion import suggest_chart
from app.event_analytics.domain.analytics_catalog import AnalyticsDataset
from app.event_analytics.domain.explore_query import (
    ExploreColumnRef,
    ExploreJoin,
    ExploreQuery,
    ExploreSortDirection,
)
from app.event_analytics.domain.query_result import AnalyticsQueryResult
from app.event_analytics.domain.repositories.analytics_query_repository import (
    AnalyticsQueryRepository,
)
from app.shared.exceptions import (
    EventAnalyticsDatabaseExecutionError,
    EventAnalyticsExploreExecutionUnavailableError,
    EventAnalyticsExploreQueryValidationError as ExploreQueryValidationError,
)

MAX_EXPLORE_QUERY_ROW_LIMIT = 500
MAX_EXPLORE_JOIN_COUNT = 1


class ExploreQueryService:
    """Validate structured Explore requests and execute them through a repository."""

    def __init__(
        self,
        repository: AnalyticsQueryRepository,
        catalog_service: AnalyticsCatalogService | None = None,
    ) -> None:
        """Initialize the Explore query service.

        Args:
            repository: Read repository for generated analytics datasets.
            catalog_service: Optional dynamic dataset catalog service.

        Returns:
            None.
        """
        self._repository = repository
        self._catalog_service = catalog_service

    async def execute(
        self,
        dataset_name: str,
        column_refs: tuple[ExploreColumnRef, ...],
        joins: tuple[ExploreJoin, ...],
        order_by: ExploreColumnRef | None,
        order_direction: ExploreSortDirection,
        row_limit: int,
    ) -> AnalyticsQueryResult:
        """Execute one validated structured Explore query.

        Args:
            dataset_name: Generated dataset selected by the frontend.
            column_refs: Dataset columns selected for projection.
            joins: Optional 1-hop joins selected by the frontend.
            order_by: Optional dataset column used for ordering.
            order_direction: Sort direction for the optional ordering column.
            row_limit: Requested maximum row count.

        Returns:
            Query result with JSON-safe rows and chart suggestion.
        """
        datasets = await self._list_datasets()
        query = build_explore_query(
            dataset_name,
            datasets=datasets,
            column_refs=column_refs,
            joins=joins,
            order_by=order_by,
            order_direction=order_direction,
            row_limit=row_limit,
        )
        try:
            rows = await self._repository.execute_explore_query(query)
        except EventAnalyticsDatabaseExecutionError as exc:
            raise EventAnalyticsExploreExecutionUnavailableError from exc
        return AnalyticsQueryResult(
            columns=rows.columns,
            rows=rows.rows,
            chart=suggest_chart(rows),
        )

    async def _list_datasets(self) -> tuple[AnalyticsDataset, ...]:
        """Return the Explore dataset catalog.

        Args:
            None.

        Returns:
            Built-in and dynamic dataset descriptors.
        """
        if self._catalog_service is None:
            return get_datasets()
        return await self._catalog_service.list_datasets()


def build_explore_query(
    dataset_name: str,
    datasets: tuple[AnalyticsDataset, ...],
    column_refs: tuple[ExploreColumnRef, ...],
    joins: tuple[ExploreJoin, ...],
    order_by: ExploreColumnRef | None,
    order_direction: ExploreSortDirection,
    row_limit: int,
) -> ExploreQuery:
    """Build a validated internal structured query from frontend controls.

    Args:
        dataset_name: Generated dataset selected by the frontend.
        datasets: Dataset catalog available to this request.
        column_refs: Dataset columns selected for projection.
        joins: Optional 1-hop joins selected by the frontend.
        order_by: Optional dataset column used for ordering.
        order_direction: Sort direction for the optional ordering column.
        row_limit: Requested maximum row count.

    Returns:
        Validated structured query with a capped row limit.
    """
    dataset_by_name = {dataset.name: dataset for dataset in datasets}
    dataset = _find_dataset(dataset_name, dataset_by_name)
    _ensure_join_shape_is_allowed(
        joins,
        base_dataset=dataset,
        dataset_by_name=dataset_by_name,
    )
    join_dataset_names = frozenset(join.dataset_name for join in joins)
    selectable_dataset_names = frozenset({dataset.name}) | join_dataset_names
    _ensure_selected_columns_are_allowed(
        column_refs,
        selectable_dataset_names=selectable_dataset_names,
        dataset_by_name=dataset_by_name,
    )
    _ensure_order_column_is_allowed(
        order_by,
        selectable_dataset_names=selectable_dataset_names,
        dataset_by_name=dataset_by_name,
    )
    return ExploreQuery(
        dataset_name=dataset.name,
        column_refs=column_refs,
        joins=joins,
        order_by=order_by,
        order_direction=order_direction,
        row_limit=min(row_limit, MAX_EXPLORE_QUERY_ROW_LIMIT),
    )


def _find_dataset(
    dataset_name: str,
    dataset_by_name: dict[str, AnalyticsDataset],
) -> AnalyticsDataset:
    """Find one generated dataset by name.

    Args:
        dataset_name: Dataset name requested by the frontend.
        dataset_by_name: Available datasets keyed by name.

    Returns:
        Matching generated dataset descriptor.
    """
    dataset = dataset_by_name.get(dataset_name)
    if dataset is not None:
        return dataset
    raise ExploreQueryValidationError(
        "unknown_dataset",
        message="알 수 없는 analytics dataset입니다.",
    )


def _ensure_join_shape_is_allowed(
    joins: tuple[ExploreJoin, ...],
    base_dataset: AnalyticsDataset,
    dataset_by_name: dict[str, AnalyticsDataset],
) -> None:
    """Reject unknown or unsupported Explore joins.

    Args:
        joins: Requested 1-hop joins.
        base_dataset: Base dataset selected by the frontend.
        dataset_by_name: Available datasets keyed by name.

    Returns:
        None.
    """
    if len(joins) > MAX_EXPLORE_JOIN_COUNT:
        raise ExploreQueryValidationError(
            "too_many_joins",
            message=f"Chart Builder JOIN은 최대 {MAX_EXPLORE_JOIN_COUNT}개만 허용합니다.",
        )
    base_column_names = _dataset_column_names(base_dataset)
    seen_join_datasets: set[str] = set()
    for join in joins:
        join_dataset = dataset_by_name.get(join.dataset_name)
        if join_dataset is None:
            raise ExploreQueryValidationError(
                "unknown_join_dataset",
                message="JOIN할 수 없는 dataset입니다.",
            )
        if join.dataset_name == base_dataset.name:
            raise ExploreQueryValidationError(
                "self_join_not_supported",
                message="같은 dataset self join은 현재 Chart Builder에서 지원하지 않습니다.",
            )
        if join.dataset_name in seen_join_datasets:
            raise ExploreQueryValidationError(
                "duplicate_join_dataset",
                message="같은 dataset은 한 번만 JOIN할 수 있습니다.",
            )
        seen_join_datasets.add(join.dataset_name)
        if join.left_column not in base_column_names:
            raise ExploreQueryValidationError(
                "unknown_join_left_column",
                message="base dataset에 없는 column으로 JOIN할 수 없습니다.",
            )
        if join.right_column not in _dataset_column_names(join_dataset):
            raise ExploreQueryValidationError(
                "unknown_join_right_column",
                message="JOIN dataset에 없는 column으로 JOIN할 수 없습니다.",
            )


def _ensure_selected_columns_are_allowed(
    selected_columns: tuple[ExploreColumnRef, ...],
    selectable_dataset_names: frozenset[str],
    dataset_by_name: dict[str, AnalyticsDataset],
) -> None:
    """Reject empty, duplicated, or unknown projection columns.

    Args:
        selected_columns: Dataset columns requested by the frontend.
        selectable_dataset_names: Dataset names available in the query scope.
        dataset_by_name: Available datasets keyed by name.

    Returns:
        None.
    """
    if not selected_columns:
        raise ExploreQueryValidationError(
            "missing_columns",
            message="Explore query에는 최소 1개 이상의 column이 필요합니다.",
        )
    selected_column_keys = {
        (column_ref.dataset_name, column_ref.column_name)
        for column_ref in selected_columns
    }
    if len(selected_columns) != len(selected_column_keys):
        raise ExploreQueryValidationError(
            "duplicate_columns",
            message="Explore query column은 중복될 수 없습니다.",
        )
    for column_ref in selected_columns:
        _ensure_column_ref_is_selectable(
            column_ref,
            selectable_dataset_names=selectable_dataset_names,
            dataset_by_name=dataset_by_name,
        )


def _ensure_order_column_is_allowed(
    order_by: ExploreColumnRef | None,
    selectable_dataset_names: frozenset[str],
    dataset_by_name: dict[str, AnalyticsDataset],
) -> None:
    """Reject unknown ordering columns.

    Args:
        order_by: Optional ordering column requested by the frontend.
        selectable_dataset_names: Dataset names available in the query scope.
        dataset_by_name: Available datasets keyed by name.

    Returns:
        None.
    """
    if order_by is not None:
        try:
            _ensure_column_ref_is_selectable(
                order_by,
                selectable_dataset_names=selectable_dataset_names,
                dataset_by_name=dataset_by_name,
            )
        except ExploreQueryValidationError as exc:
            raise ExploreQueryValidationError(
                "unknown_order_column",
                message="dataset에 없는 column으로 정렬할 수 없습니다.",
            ) from exc


def _ensure_column_ref_is_selectable(
    column_ref: ExploreColumnRef,
    selectable_dataset_names: frozenset[str],
    dataset_by_name: dict[str, AnalyticsDataset],
) -> None:
    """Reject a column reference outside the current Explore query scope.

    Args:
        column_ref: Requested dataset column reference.
        selectable_dataset_names: Dataset names available in the query scope.
        dataset_by_name: Available datasets keyed by name.

    Returns:
        None.
    """
    if column_ref.dataset_name not in selectable_dataset_names:
        raise ExploreQueryValidationError(
            "unknown_column_dataset",
            message="JOIN되지 않은 dataset column은 조회할 수 없습니다.",
        )
    dataset = dataset_by_name[column_ref.dataset_name]
    if column_ref.column_name not in _dataset_column_names(dataset):
        raise ExploreQueryValidationError(
            "unknown_column",
            message="dataset에 없는 column은 조회할 수 없습니다.",
        )


def _dataset_column_names(dataset: AnalyticsDataset) -> frozenset[str]:
    """Return dataset column names.

    Args:
        dataset: Dataset descriptor.

    Returns:
        Column name allowlist.
    """
    return frozenset(column.name for column in dataset.columns)

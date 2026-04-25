"""Application service for built-in and user-created analytics datasets."""

from __future__ import annotations

from app.event_analytics.application.analytics_catalog import get_datasets
from app.event_analytics.domain.analytics_catalog import (
    AnalyticsDataset,
    AnalyticsViewTable,
)
from app.event_analytics.domain.repositories.analytics_dataset_repository import (
    AnalyticsDatasetRepository,
)
from app.shared.exceptions import EventAnalyticsDatabaseExecutionError


class AnalyticsCatalogService:
    """Return the analytics dataset catalog visible to SQL Lab and Charts."""

    def __init__(
        self,
        repository: AnalyticsDatasetRepository | None = None,
    ) -> None:
        """Initialize the dataset catalog service.

        Args:
            repository: Optional dynamic dataset repository.

        Returns:
            None.
        """
        self._repository = repository

    async def list_datasets(self) -> tuple[AnalyticsDataset, ...]:
        """Return built-in datasets plus user-created view table datasets.

        Args:
            None.

        Returns:
            Dataset descriptors visible to the analytics UI.
        """
        built_in_datasets = get_datasets()
        if self._repository is None:
            return built_in_datasets
        try:
            dynamic_datasets = await self._repository.list_view_table_datasets()
        except EventAnalyticsDatabaseExecutionError:
            return built_in_datasets
        return (*built_in_datasets, *dynamic_datasets)

    async def list_view_tables(self) -> tuple[AnalyticsViewTable, ...]:
        """Return user-created view table metadata.

        Args:
            None.

        Returns:
            User-created view table metadata with current columns.
        """
        if self._repository is None:
            return ()
        try:
            return await self._repository.list_view_tables()
        except EventAnalyticsDatabaseExecutionError:
            return ()

    async def allowed_dataset_names(self) -> frozenset[str]:
        """Return relation names accepted by SQL Lab and Chart Builder.

        Args:
            None.

        Returns:
            Lowercase dataset/view names.
        """
        return frozenset(dataset.name for dataset in await self.list_datasets())

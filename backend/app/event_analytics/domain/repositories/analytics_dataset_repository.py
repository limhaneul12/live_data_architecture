"""Analytics dataset metadata repository contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.event_analytics.domain.analytics_catalog import (
    AnalyticsDataset,
    AnalyticsViewTable,
)
from app.event_analytics.domain.query_result import AnalyticsRows


class AnalyticsDatasetRepository(ABC):
    """Persistence contract for dynamic analytics dataset metadata."""

    @abstractmethod
    async def list_view_table_datasets(self) -> tuple[AnalyticsDataset, ...]:
        """Return datasets backed by user-created view tables.

        Args:
            None.

        Returns:
            Dynamic analytics dataset descriptors.
        """

    @abstractmethod
    async def list_view_tables(self) -> tuple[AnalyticsViewTable, ...]:
        """Return user-created view table metadata.

        Args:
            None.

        Returns:
            User-created view table metadata with current columns.
        """

    @abstractmethod
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

    @abstractmethod
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

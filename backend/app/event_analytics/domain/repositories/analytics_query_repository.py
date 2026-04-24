"""Analytics SQL read repository base contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.event_analytics.domain.query_result import AnalyticsRows


class AnalyticsQueryRepository(ABC):
    """Persistence read contract for allowlisted analytics SQL."""

    @abstractmethod
    async def execute_select(
        self,
        *,
        sql: str,
        row_limit: int,
    ) -> AnalyticsRows:
        """Execute a validated read-only analytics SELECT statement.

        Args:
            sql: Policy-validated SQL SELECT statement.
            row_limit: Maximum rows the repository may return.

        Returns:
            JSON-safe result rows returned by the backing store.
        """

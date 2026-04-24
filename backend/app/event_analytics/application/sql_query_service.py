"""Application service for executing safe analytics SQL."""

from __future__ import annotations

from app.event_analytics.application.chart_suggestion import suggest_chart
from app.event_analytics.application.query_policy import AnalyticsSqlPolicy
from app.event_analytics.domain.query_result import AnalyticsQueryResult
from app.event_analytics.domain.repositories.analytics_query_repository import (
    AnalyticsQueryRepository,
)


class SqlQueryService:
    """Validate SQL policy, execute it, and attach chart metadata."""

    def __init__(
        self,
        *,
        policy: AnalyticsSqlPolicy,
        repository: AnalyticsQueryRepository,
    ) -> None:
        """Initialize the SQL query service.

        Args:
            policy: Server-side SQL policy validator.
            repository: Read repository for validated analytics SQL.

        Returns:
            None.
        """
        self._policy = policy
        self._repository = repository

    async def execute(self, *, sql: str, row_limit: int) -> AnalyticsQueryResult:
        """Execute one manual or preset analytics SQL query.

        Args:
            sql: SQL submitted by the UI or selected preset.
            row_limit: Requested maximum result row count.

        Returns:
            Query result with JSON-safe rows and chart suggestion.
        """
        validated = self._policy.validate(sql=sql, requested_row_limit=row_limit)
        rows = await self._repository.execute_select(
            sql=validated.sql,
            row_limit=validated.row_limit,
        )
        return AnalyticsQueryResult(
            columns=rows.columns,
            rows=rows.rows,
            chart=suggest_chart(rows),
        )

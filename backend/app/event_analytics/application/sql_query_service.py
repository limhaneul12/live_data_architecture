"""Application service for executing safe analytics SQL."""

from __future__ import annotations

import hashlib
import logging

from app.event_analytics.application.chart_suggestion import suggest_chart
from app.event_analytics.application.query_policy import (
    AnalyticsSqlPolicy,
    SqlPolicyViolationError,
    ValidatedSqlQuery,
)
from app.event_analytics.domain.query_result import AnalyticsQueryResult
from app.event_analytics.domain.repositories.analytics_query_repository import (
    AnalyticsQueryRepository,
)

LOGGER = logging.getLogger(__name__)


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

    async def execute(self, sql: str, row_limit: int) -> AnalyticsQueryResult:
        """Execute one manual or preset analytics SQL query.

        Args:
            sql: SQL submitted by the UI or selected preset.
            row_limit: Requested maximum result row count.

        Returns:
            Query result with JSON-safe rows and chart suggestion.
        """
        sql_hash = analytics_sql_hash(sql)
        try:
            validated = self._policy.validate(sql=sql, requested_row_limit=row_limit)
        except SqlPolicyViolationError as exc:
            log_sql_policy_rejection(
                sql_hash=sql_hash,
                reason=exc.reason,
            )
            raise

        log_sql_policy_acceptance(validated=validated, sql_hash=sql_hash)
        rows = await self._repository.execute_select(
            sql=validated.sql,
            row_limit=validated.row_limit,
        )
        log_sql_execution_result(
            row_count=len(rows.rows),
            sql_hash=sql_hash,
        )
        return AnalyticsQueryResult(
            columns=rows.columns,
            rows=rows.rows,
            chart=suggest_chart(rows),
        )


def analytics_sql_hash(sql: str) -> str:
    """Hash SQL text for audit logs without storing raw query text.

    Args:
        sql: Manual SQL text submitted to SQL Lab.

    Returns:
        Hex-encoded SHA-256 digest of the submitted SQL.
    """
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def log_sql_policy_rejection(*, sql_hash: str, reason: str) -> None:
    """Write an audit log for SQL rejected before database execution.

    Args:
        sql_hash: SHA-256 digest of the submitted SQL.
        reason: Stable policy rejection reason.

    Returns:
        None.
    """
    LOGGER.warning(
        "analytics SQL rejected sql_sha256=%s reason=%s",
        sql_hash,
        reason,
        extra={"event": "analytics_sql_rejected"},
    )


def log_sql_policy_acceptance(
    *,
    validated: ValidatedSqlQuery,
    sql_hash: str,
) -> None:
    """Write an audit log for SQL accepted by server-side policy.

    Args:
        validated: Validated SQL execution contract.
        sql_hash: SHA-256 digest of the submitted SQL.

    Returns:
        None.
    """
    relation_list = ",".join(sorted(validated.referenced_relations))
    LOGGER.info(
        "analytics SQL accepted sql_sha256=%s relations=%s row_limit=%s",
        sql_hash,
        relation_list,
        validated.row_limit,
        extra={"event": "analytics_sql_accepted"},
    )


def log_sql_execution_result(*, row_count: int, sql_hash: str) -> None:
    """Write an audit log after SQL Lab database execution completes.

    Args:
        row_count: Number of rows returned from the repository.
        sql_hash: SHA-256 digest of the submitted SQL.

    Returns:
        None.
    """
    LOGGER.info(
        "analytics SQL completed sql_sha256=%s row_count=%s",
        sql_hash,
        row_count,
        extra={"event": "analytics_sql_completed"},
    )

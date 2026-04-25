"""Event analytics exception types shared by application and routers."""

from __future__ import annotations

from fastapi import status


class EventAnalyticsRouteError(Exception):
    """Base class for event analytics failures that have an HTTP mapping."""

    def __init__(
        self,
        *,
        status_code: int,
        error_code: str,
        message: str,
        rejected_reason: str | None,
    ) -> None:
        """Initialize a route-mappable event analytics exception.

        Args:
            status_code: HTTP status code that should be returned.
            error_code: Stable machine-readable API error code.
            message: Human-readable API error message.
            rejected_reason: Optional stable rejection reason for clients.

        Returns:
            None.
        """
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.rejected_reason = rejected_reason


class EventAnalyticsSqlPolicyViolationError(EventAnalyticsRouteError):
    """Raised when SQL Lab input violates the analytics SQL policy."""

    def __init__(self, reason: str, message: str) -> None:
        """Initialize a SQL policy violation.

        Args:
            reason: Stable machine-readable policy rejection reason.
            message: Human-readable rejection detail.

        Returns:
            None.
        """
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="sql_policy_violation",
            message=message,
            rejected_reason=reason,
        )
        self.reason = reason


class EventAnalyticsExploreQueryValidationError(EventAnalyticsRouteError):
    """Raised when a structured Explore query is outside the dataset catalog."""

    def __init__(self, reason: str, message: str) -> None:
        """Initialize an Explore query validation failure.

        Args:
            reason: Stable machine-readable validation rejection reason.
            message: Human-readable rejection detail.

        Returns:
            None.
        """
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="explore_query_violation",
            message=message,
            rejected_reason=reason,
        )
        self.reason = reason


class EventAnalyticsDatabaseExecutionError(Exception):
    """Raised when PostgreSQL cannot execute a validated analytics read."""


class EventAnalyticsSqlExecutionUnavailableError(EventAnalyticsRouteError):
    """Raised when SQL Lab cannot execute against the analytics database."""

    def __init__(self) -> None:
        """Initialize a SQL Lab database-unavailable failure.

        Args:
            None.

        Returns:
            None.
        """
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="analytics_database_unavailable",
            message="analytics SQL을 실행할 수 없습니다.",
            rejected_reason=None,
        )


class EventAnalyticsExploreExecutionUnavailableError(EventAnalyticsRouteError):
    """Raised when structured Explore cannot execute against the database."""

    def __init__(self) -> None:
        """Initialize an Explore database-unavailable failure.

        Args:
            None.

        Returns:
            None.
        """
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="analytics_database_unavailable",
            message="analytics Explore query를 실행할 수 없습니다.",
            rejected_reason=None,
        )

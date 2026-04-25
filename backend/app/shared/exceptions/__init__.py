"""Shared exception catalog exports."""

from app.shared.exceptions.event_analytics_exceptions import (
    EventAnalyticsDatabaseExecutionError,
    EventAnalyticsExploreExecutionUnavailableError,
    EventAnalyticsExploreQueryValidationError,
    EventAnalyticsRouteError,
    EventAnalyticsSqlExecutionUnavailableError,
    EventAnalyticsSqlPolicyViolationError,
)
from app.shared.exceptions.exception_decorators import map_event_analytics_route_errors

__all__ = [
    "EventAnalyticsDatabaseExecutionError",
    "EventAnalyticsExploreExecutionUnavailableError",
    "EventAnalyticsExploreQueryValidationError",
    "EventAnalyticsRouteError",
    "EventAnalyticsSqlExecutionUnavailableError",
    "EventAnalyticsSqlPolicyViolationError",
    "map_event_analytics_route_errors",
]

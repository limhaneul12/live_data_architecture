"""Event analytics repository contracts."""

from app.event_analytics.domain.repositories.analytics_dataset_repository import (
    AnalyticsDatasetRepository,
)
from app.event_analytics.domain.repositories.analytics_query_repository import (
    AnalyticsQueryRepository,
)
from app.event_analytics.domain.repositories.event_repository import EventRepository

__all__ = [
    "AnalyticsDatasetRepository",
    "AnalyticsQueryRepository",
    "EventRepository",
]

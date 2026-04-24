"""Event analytics repository base contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.event_analytics.domain.events import WebEvent


class EventRepository(ABC):
    """Persistence base contract for storing validated web events."""

    @abstractmethod
    async def save_batch(self, events: Sequence[WebEvent]) -> int:
        """Persist a batch of events and return inserted row count.

        Args:
            events: Validated internal event dataclasses to persist.

        Returns:
            Number of rows inserted by the backing store.
        """

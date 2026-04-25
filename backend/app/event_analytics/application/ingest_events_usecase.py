"""Application use case for storing validated web events."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.event_analytics.domain.events import WebEvent
from app.event_analytics.domain.repositories.event_repository import EventRepository


@dataclass(frozen=True, slots=True)
class IngestEventsResult:
    """Result of one event ingestion batch."""

    received_count: int
    inserted_count: int


class IngestEventsUseCase:
    """Store validated web events through the event repository port."""

    def __init__(self, repository: EventRepository) -> None:
        """Initialize this use case.

        Args:
            repository: Port used to persist validated event batches.

        Returns:
            None.
        """
        self._repository = repository

    async def ingest(self, events: Sequence[WebEvent]) -> IngestEventsResult:
        """Persist the given events as one logical batch.

        Args:
            events: Validated internal event dataclasses to store.

        Returns:
            Batch ingestion result containing received and inserted counts.
        """
        received_count = len(events)
        if received_count == 0:
            return IngestEventsResult(received_count=0, inserted_count=0)

        inserted_count = await self._repository.save_batch(events)
        return IngestEventsResult(
            received_count=received_count,
            inserted_count=inserted_count,
        )

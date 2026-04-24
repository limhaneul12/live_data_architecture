import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime

from app.event_analytics.application.ingest_events_usecase import IngestEventsUseCase
from app.event_analytics.domain.events import WebEvent
from app.event_analytics.domain.repositories.event_repository import EventRepository


class FakeEventRepository(EventRepository):
    def __init__(self) -> None:
        self.saved_batches: list[list[WebEvent]] = []

    async def save_batch(self, events: Sequence[WebEvent]) -> int:
        batch = list(events)
        self.saved_batches.append(batch)
        return len(batch)


def build_event(event_id: str = "evt_abc123def456") -> WebEvent:
    return WebEvent(
        schema_version="web_event.v1",
        event_id=event_id,
        event_type="page_view",
        occurred_at=datetime(2026, 4, 24, tzinfo=UTC),
        user_id="user_001",
        traffic_phase="normal",
        producer_id="producer_local",
        page_path="/products",
        category_id=None,
        product_id=None,
        amount=None,
        currency=None,
        error_code=None,
        error_message=None,
    )


def test_ingest_events_usecase_saves_events_as_one_batch() -> None:
    repository = FakeEventRepository()
    usecase = IngestEventsUseCase(repository=repository)
    events = [build_event("evt_1"), build_event("evt_2")]

    result = asyncio.run(usecase.ingest(events))

    assert result.received_count == 2
    assert result.inserted_count == 2
    assert repository.saved_batches == [events]


def test_ingest_events_usecase_skips_repository_when_batch_is_empty() -> None:
    repository = FakeEventRepository()
    usecase = IngestEventsUseCase(repository=repository)

    result = asyncio.run(usecase.ingest([]))

    assert result.received_count == 0
    assert result.inserted_count == 0
    assert repository.saved_batches == []

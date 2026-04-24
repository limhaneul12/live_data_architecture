import asyncio
from collections.abc import Sequence
from typing import cast

from app.event_analytics.application.ingest_events_usecase import (
    IngestEventsResult,
    IngestEventsUseCase,
)
from app.event_analytics.domain.events import WebEvent
from app.event_analytics.infrastructure.streams.redis_stream_consumer import (
    RedisStreamEventConsumer,
    StreamMessage,
)
from app.event_analytics.interface.consumer_lifespan import EventStreamIngestionLoop
from app.shared.types import JSONObject


class DatabaseUnavailableError(Exception):
    pass


class StreamUnavailableError(Exception):
    pass


class FakeStreamConsumer:
    def __init__(self, messages: Sequence[StreamMessage]) -> None:
        self._messages = list(messages)
        self.acked_ids: list[str] = []
        self.group_ensured = False

    async def ensure_group(self) -> None:
        self.group_ensured = True

    async def read_batch(self) -> list[StreamMessage]:
        return self._messages

    async def ack_many(self, message_ids: list[str]) -> int:
        self.acked_ids.extend(message_ids)
        return len(message_ids)


class FailingOnceStreamConsumer(FakeStreamConsumer):
    def __init__(self, *, stop_event: asyncio.Event) -> None:
        super().__init__([])
        self.stop_event = stop_event
        self.read_count = 0

    async def read_batch(self) -> list[StreamMessage]:
        self.read_count += 1
        if self.read_count == 1:
            raise StreamUnavailableError
        self.stop_event.set()
        return []


class FakeUseCase:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.saved_events: list[WebEvent] = []

    async def ingest(self, events: Sequence[WebEvent]) -> IngestEventsResult:
        if self.fail:
            raise DatabaseUnavailableError
        self.saved_events.extend(events)
        return IngestEventsResult(
            received_count=len(events),
            inserted_count=len(events),
        )


def valid_payload(event_id: str = "evt_1") -> JSONObject:
    return {
        "schema_version": "web_event.v1",
        "event_id": event_id,
        "event_type": "page_view",
        "occurred_at": "2026-04-24T00:00:00.000Z",
        "user_id": "user_001",
        "traffic_phase": "normal",
        "producer_id": "producer_local",
        "page_path": "/products",
        "category_id": None,
        "product_id": None,
        "amount": None,
        "currency": None,
        "error_code": None,
        "error_message": None,
    }


def build_loop(
    *,
    stream: FakeStreamConsumer,
    usecase: FakeUseCase,
    error_backoff_seconds: float = 0.0,
) -> EventStreamIngestionLoop:
    return EventStreamIngestionLoop(
        stream_consumer=cast(RedisStreamEventConsumer, stream),
        usecase=cast(IngestEventsUseCase, usecase),
        error_backoff_seconds=error_backoff_seconds,
    )


def test_ingestion_loop_acks_after_successful_batch_store() -> None:
    stream = FakeStreamConsumer([StreamMessage("1-0", valid_payload())])
    usecase = FakeUseCase()
    loop = build_loop(stream=stream, usecase=usecase)

    result = asyncio.run(loop.poll_once())

    assert result.read_count == 1
    assert result.valid_count == 1
    assert result.acked_count == 1
    assert result.store_failed is False
    assert [event.event_id for event in usecase.saved_events] == ["evt_1"]
    assert stream.acked_ids == ["1-0"]


def test_ingestion_loop_does_not_ack_valid_messages_when_store_fails() -> None:
    stream = FakeStreamConsumer([StreamMessage("1-0", valid_payload())])
    loop = build_loop(stream=stream, usecase=FakeUseCase(fail=True))

    result = asyncio.run(loop.poll_once())

    assert result.read_count == 1
    assert result.valid_count == 1
    assert result.acked_count == 0
    assert result.store_failed is True
    assert stream.acked_ids == []


def test_ingestion_loop_acks_invalid_payload_without_calling_usecase() -> None:
    stream = FakeStreamConsumer(
        [StreamMessage("1-0", valid_payload() | {"schema_version": "web_event.v2"})]
    )
    usecase = FakeUseCase()
    loop = build_loop(stream=stream, usecase=usecase)

    result = asyncio.run(loop.poll_once())

    assert result.read_count == 1
    assert result.valid_count == 0
    assert result.invalid_count == 1
    assert result.acked_count == 1
    assert usecase.saved_events == []
    assert stream.acked_ids == ["1-0"]


def test_run_forever_keeps_polling_after_stream_read_failure() -> None:
    async def scenario() -> FailingOnceStreamConsumer:
        stop_event = asyncio.Event()
        stream = FailingOnceStreamConsumer(stop_event=stop_event)
        loop = build_loop(stream=stream, usecase=FakeUseCase())

        await asyncio.wait_for(loop.run_forever(stop_event=stop_event), timeout=1)

        return stream

    stream = asyncio.run(scenario())

    assert stream.group_ensured is True
    assert stream.read_count == 2

"""FastAPI lifecycle helpers for Redis Stream event ingestion."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass

from app.event_analytics.application.ingest_events_usecase import IngestEventsUseCase
from app.event_analytics.constants import EVENT_CONSUMER_ERROR_BACKOFF_SECONDS
from app.event_analytics.domain.events import WebEvent
from app.event_analytics.infrastructure.database_url import to_sqlalchemy_async_url
from app.event_analytics.infrastructure.repositories.postgres_event_repository import (
    PostgresEventRepository,
)
from app.event_analytics.infrastructure.streams.redis_client_factory import (
    AsyncRedisClient,
    build_async_redis_client,
)
from app.event_analytics.infrastructure.streams.redis_stream_consumer import (
    RedisStreamEventConsumer,
)
from app.event_analytics.interface.schemas import WebEventPayload
from app.platform.config import StreamConfig
from app.shared.types import JSONObject
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EventStreamIngestionPollResult:
    """Observable result of one stream ingestion polling iteration."""

    read_count: int
    valid_count: int
    invalid_count: int
    acked_count: int
    inserted_count: int
    store_failed: bool = False


@dataclass(slots=True)
class EventConsumerRuntime:
    """Running background consumer resources owned by the FastAPI lifespan."""

    stop_event: asyncio.Event
    task: asyncio.Task[None]
    redis: AsyncRedisClient
    engine: AsyncEngine
    shutdown_timeout_seconds: float = 2.0

    async def stop(self) -> None:
        """Request consumer shutdown and close owned async resources.

        Args:
            None.

        Returns:
            None.
        """
        self.stop_event.set()
        try:
            await asyncio.wait_for(self.task, timeout=self.shutdown_timeout_seconds)
        except TimeoutError:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        finally:
            await self.redis.aclose()
            await self.engine.dispose()

    async def ping_redis(self) -> None:
        """Verify that the owned Redis connection responds to PING.

        Args:
            None.

        Returns:
            None.
        """
        await self.redis.ping()

    async def ping_database(self) -> None:
        """Verify that the owned PostgreSQL connection responds to SELECT 1.

        Args:
            None.

        Returns:
            None.
        """
        await ping_database_engine(self.engine)


class EventStreamIngestionLoop:
    """Poll Redis Stream events and store them through the ingestion use case."""

    def __init__(
        self,
        *,
        stream_consumer: RedisStreamEventConsumer,
        usecase: IngestEventsUseCase,
        error_backoff_seconds: float = EVENT_CONSUMER_ERROR_BACKOFF_SECONDS,
    ) -> None:
        """Initialize this ingestion loop.

        Args:
            stream_consumer: Redis Stream adapter used to read and ack messages.
            usecase: Application use case used to persist valid events.
            error_backoff_seconds: Backoff seconds after stream or database failures.

        Returns:
            None.
        """
        self._stream_consumer = stream_consumer
        self._usecase = usecase
        self._error_backoff_seconds = error_backoff_seconds

    async def poll_once(self) -> EventStreamIngestionPollResult:
        """Read one stream batch, store valid events, then ack successful messages.

        Args:
            None.

        Returns:
            Observable result for one polling iteration.
        """
        messages = await self._stream_consumer.read_batch()
        valid_events: list[WebEvent] = []
        valid_message_ids: list[str] = []
        invalid_message_ids: list[str] = []

        for message in messages:
            event = _coerce_payload(message.payload)
            if event is None:
                logger.warning("Dropping invalid event payload %s", message.message_id)
                invalid_message_ids.append(message.message_id)
                continue
            valid_events.append(event)
            valid_message_ids.append(message.message_id)

        acked_count = await self._stream_consumer.ack_many(invalid_message_ids)
        inserted_count = 0
        if valid_events:
            try:
                result = await self._usecase.ingest(valid_events)
            except Exception:
                logger.exception("Failed to store event stream batch")
                return EventStreamIngestionPollResult(
                    read_count=len(messages),
                    valid_count=len(valid_events),
                    invalid_count=len(invalid_message_ids),
                    acked_count=acked_count,
                    inserted_count=0,
                    store_failed=True,
                )
            inserted_count = result.inserted_count
            acked_count += await self._stream_consumer.ack_many(valid_message_ids)

        return EventStreamIngestionPollResult(
            read_count=len(messages),
            valid_count=len(valid_events),
            invalid_count=len(invalid_message_ids),
            acked_count=acked_count,
            inserted_count=inserted_count,
        )

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        """Run polling iterations until the caller signals shutdown.

        Args:
            stop_event: Event set by the runtime owner to request graceful shutdown.

        Returns:
            None.
        """
        group_ready = False
        while not stop_event.is_set():
            try:
                if not group_ready:
                    await self._stream_consumer.ensure_group()
                    group_ready = True
                result = await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                group_ready = False
                logger.exception("Event stream poll failed")
                await _wait_for_stop_or_backoff(
                    stop_event=stop_event,
                    seconds=self._error_backoff_seconds,
                )
                continue

            if result.store_failed:
                await _wait_for_stop_or_backoff(
                    stop_event=stop_event,
                    seconds=self._error_backoff_seconds,
                )


async def start_event_consumer_runtime(
    *,
    database_url: str,
    stream_config: StreamConfig,
) -> EventConsumerRuntime:
    """Create resources and start the event stream ingestion loop.

    Args:
        database_url: PostgreSQL connection URL.
        stream_config: Redis Stream runtime configuration.

    Returns:
        Running consumer runtime with owned Redis, DB, and task resources.
    """
    engine = create_async_engine(to_sqlalchemy_async_url(database_url))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    redis = build_async_redis_client(stream_config)
    stream_consumer = RedisStreamEventConsumer(
        redis=redis,
        stream_config=stream_config,
    )
    await redis.ping()
    await ping_database_engine(engine)
    await stream_consumer.ensure_group()
    usecase = IngestEventsUseCase(
        repository=PostgresEventRepository(session_factory=session_factory),
    )
    loop = EventStreamIngestionLoop(
        stream_consumer=stream_consumer,
        usecase=usecase,
    )
    stop_event = asyncio.Event()
    task = asyncio.create_task(loop.run_forever(stop_event=stop_event))
    return EventConsumerRuntime(
        stop_event=stop_event,
        task=task,
        redis=redis,
        engine=engine,
    )


def _coerce_payload(payload: JSONObject) -> WebEvent | None:
    """Validate and convert a stream payload into an internal event.

    Args:
        payload: Raw JSON object decoded from Redis Streams.

    Returns:
        Internal event dataclass, or None when validation fails.
    """
    try:
        parsed = WebEventPayload.model_validate(payload)
    except ValidationError:
        return None
    return WebEvent(
        schema_version=parsed.schema_version,
        event_id=parsed.event_id,
        event_type=parsed.event_type,
        occurred_at=parsed.occurred_at,
        user_id=parsed.user_id,
        traffic_phase=parsed.traffic_phase,
        producer_id=parsed.producer_id,
        page_path=parsed.page_path,
        category_id=parsed.category_id,
        product_id=parsed.product_id,
        amount=parsed.amount,
        currency=parsed.currency,
        error_code=parsed.error_code,
        error_message=parsed.error_message,
    )


async def ping_database_engine(engine: AsyncEngine) -> None:
    """Run the lightweight PostgreSQL health query used by startup/health probes.

    Args:
        engine: SQLAlchemy async engine to probe.

    Returns:
        None.
    """
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def _wait_for_stop_or_backoff(
    *,
    stop_event: asyncio.Event,
    seconds: float,
) -> None:
    """Sleep for backoff unless shutdown is requested first.

    Args:
        stop_event: Event that signals graceful shutdown.
        seconds: Maximum backoff duration.

    Returns:
        None.
    """
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=seconds)
    except TimeoutError:
        return

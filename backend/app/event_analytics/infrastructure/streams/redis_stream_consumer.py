"""Redis Streams adapter for event analytics ingestion."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast

from app.event_analytics.constants import (
    EVENT_CONSUMER_GROUP,
    EVENT_CONSUMER_NAME,
    EVENT_STREAM_GROUP_START_ID,
    EVENT_STREAM_KEY,
    EVENT_STREAM_NEW_ID,
    EVENT_STREAM_PENDING_ID,
)
from app.event_analytics.infrastructure.streams.redis_client_factory import (
    AsyncRedisClient,
)
from app.platform.config import StreamConfig
from app.shared.types import JSONObject, JSONValue
from redis.exceptions import ResponseError

RedisText = str | bytes
RedisStreamFields = dict[RedisText, RedisText]
RedisReadGroupEntries = list[
    tuple[RedisText, list[tuple[RedisText, RedisStreamFields]]]
]


@dataclass(frozen=True, slots=True)
class StreamMessage:
    """Decoded Redis Stream message payload with its stream message id."""

    message_id: str
    payload: JSONObject


class RedisStreamEventConsumer:
    """Read and acknowledge `web_event.v1` payloads from Redis Streams."""

    def __init__(self, redis: AsyncRedisClient, stream_config: StreamConfig) -> None:
        """Initialize this consumer with a root-owned Redis client.

        Args:
            redis: Redis client owned by the runtime lifecycle.
            stream_config: Batch read and blocking timeout configuration.

        Returns:
            None.
        """
        self._redis = redis
        self._stream_config = stream_config

    async def ensure_group(self) -> None:
        """Ensure the canonical consumer group exists.

        Args:
            None.

        Returns:
            None.
        """
        try:
            await self._redis.xgroup_create(
                name=EVENT_STREAM_KEY,
                groupname=EVENT_CONSUMER_GROUP,
                id=EVENT_STREAM_GROUP_START_ID,
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def read_batch(self) -> list[StreamMessage]:
        """Read pending retries first, then read never-delivered messages.

        Args:
            None.

        Returns:
            Decoded Redis Stream messages for one consumer batch.
        """
        pending_messages = await self._read_messages(
            stream_id=EVENT_STREAM_PENDING_ID,
            block_ms=None,
        )
        if pending_messages:
            return pending_messages

        return await self._read_messages(
            stream_id=EVENT_STREAM_NEW_ID,
            block_ms=self._stream_config.block_ms,
        )

    async def _read_messages(
        self,
        *,
        stream_id: str,
        block_ms: int | None,
    ) -> list[StreamMessage]:
        """Read and decode one Redis Stream batch for the requested stream id.

        Args:
            stream_id: Redis stream read cursor, either pending or new id.
            block_ms: Optional Redis blocking timeout.

        Returns:
            Decoded stream messages for the requested cursor.
        """
        entries = cast(
            RedisReadGroupEntries,
            await self._redis.xreadgroup(
                groupname=EVENT_CONSUMER_GROUP,
                consumername=EVENT_CONSUMER_NAME,
                streams={EVENT_STREAM_KEY: stream_id},
                count=self._stream_config.batch_size,
                block=block_ms,
            ),
        )
        return [
            StreamMessage(
                message_id=_decode_text(message_id),
                payload=_decode_payload(raw_fields),
            )
            for _stream_name, stream_messages in entries
            for message_id, raw_fields in stream_messages
        ]

    async def ack_many(self, message_ids: list[str]) -> int:
        """Acknowledge a group of stream messages in one Redis call.

        Args:
            message_ids: Redis Stream message ids to acknowledge.

        Returns:
            Number of message ids acknowledged by Redis.
        """
        if not message_ids:
            return 0
        return await self._redis.xack(
            EVENT_STREAM_KEY,
            EVENT_CONSUMER_GROUP,
            *message_ids,
        )


def _decode_payload(raw_fields: RedisStreamFields) -> JSONObject:
    """Decode a Redis Stream payload field as a JSON object.

    Args:
        raw_fields: Raw Redis Stream field dictionary.

    Returns:
        Decoded JSON object, or an empty object when invalid.
    """
    payload_value = raw_fields.get(b"payload") or raw_fields.get("payload")
    if payload_value is None:
        return {}

    try:
        parsed = cast(JSONValue, json.loads(_decode_text(payload_value)))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return cast(JSONObject, parsed)


def _decode_text(value: RedisText) -> str:
    """Decode Redis bytes/str values into text.

    Args:
        value: Redis value returned as bytes or str.

    Returns:
        Decoded text value.
    """
    if isinstance(value, bytes):
        return value.decode()
    return value

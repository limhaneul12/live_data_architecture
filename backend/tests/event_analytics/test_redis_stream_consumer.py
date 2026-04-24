import asyncio
import json
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
from app.event_analytics.infrastructure.streams.redis_stream_consumer import (
    RedisReadGroupEntries,
    RedisStreamEventConsumer,
)
from app.platform.config import StreamConfig


class FakeRedis:
    def __init__(self) -> None:
        self.created_groups: list[dict[str, str | bool]] = []
        self.acked: list[dict[str, str | tuple[str, ...]]] = []
        self.read_calls: list[dict[str, dict[str, str] | int | None]] = []
        self.pending_entries: RedisReadGroupEntries = []
        self.new_entries: RedisReadGroupEntries = [
            (
                EVENT_STREAM_KEY.encode(),
                [
                    (
                        b"1-0",
                        {
                            b"payload": json.dumps(
                                {
                                    "schema_version": "web_event.v1",
                                    "event_id": "evt_1",
                                }
                            ).encode()
                        },
                    )
                ],
            )
        ]

    async def xgroup_create(
        self,
        name: str,
        groupname: str,
        id: str = EVENT_STREAM_GROUP_START_ID,
        mkstream: bool = True,
    ) -> bool:
        self.created_groups.append(
            {"name": name, "groupname": groupname, "id": id, "mkstream": mkstream}
        )
        return True

    async def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: dict[str, str],
        count: int,
        block: int | None,
    ) -> RedisReadGroupEntries:
        assert groupname == EVENT_CONSUMER_GROUP
        assert consumername == EVENT_CONSUMER_NAME
        assert count == 100
        self.read_calls.append({"streams": streams, "block": block})
        if streams == {EVENT_STREAM_KEY: EVENT_STREAM_PENDING_ID}:
            return self.pending_entries
        if streams == {EVENT_STREAM_KEY: EVENT_STREAM_NEW_ID}:
            return self.new_entries
        raise AssertionError

    async def xack(self, name: str, groupname: str, *ids: str) -> int:
        self.acked.append({"name": name, "groupname": groupname, "ids": ids})
        return len(ids)


def build_consumer(redis: FakeRedis) -> RedisStreamEventConsumer:
    return RedisStreamEventConsumer(
        redis=cast(AsyncRedisClient, redis),
        stream_config=StreamConfig(),
    )


def test_redis_stream_consumer_ensures_group_with_mkstream() -> None:
    redis = FakeRedis()
    consumer = build_consumer(redis)

    asyncio.run(consumer.ensure_group())

    assert redis.created_groups == [
        {
            "name": EVENT_STREAM_KEY,
            "groupname": EVENT_CONSUMER_GROUP,
            "id": EVENT_STREAM_GROUP_START_ID,
            "mkstream": True,
        }
    ]


def test_redis_stream_consumer_reads_payload_batch() -> None:
    redis = FakeRedis()
    consumer = build_consumer(redis)

    messages = asyncio.run(consumer.read_batch())

    assert len(messages) == 1
    assert messages[0].message_id == "1-0"
    assert messages[0].payload == {
        "schema_version": "web_event.v1",
        "event_id": "evt_1",
    }
    assert redis.read_calls == [
        {"streams": {EVENT_STREAM_KEY: EVENT_STREAM_PENDING_ID}, "block": None},
        {"streams": {EVENT_STREAM_KEY: EVENT_STREAM_NEW_ID}, "block": 1000},
    ]


def test_redis_stream_consumer_retries_pending_before_new_messages() -> None:
    redis = FakeRedis()
    redis.pending_entries = [
        (
            EVENT_STREAM_KEY,
            [
                (
                    "0-1",
                    {"payload": json.dumps({"event_id": "evt_pending"})},
                )
            ],
        )
    ]
    consumer = build_consumer(redis)

    messages = asyncio.run(consumer.read_batch())

    assert [message.message_id for message in messages] == ["0-1"]
    assert messages[0].payload == {"event_id": "evt_pending"}
    assert redis.read_calls == [
        {"streams": {EVENT_STREAM_KEY: EVENT_STREAM_PENDING_ID}, "block": None}
    ]


def test_redis_stream_consumer_treats_malformed_json_as_invalid_payload() -> None:
    redis = FakeRedis()
    redis.new_entries = [(EVENT_STREAM_KEY, [("1-0", {"payload": "{bad json"})])]
    consumer = build_consumer(redis)

    messages = asyncio.run(consumer.read_batch())

    assert messages[0].message_id == "1-0"
    assert messages[0].payload == {}


def test_redis_stream_consumer_acks_message_ids_as_one_call() -> None:
    redis = FakeRedis()
    consumer = build_consumer(redis)

    acked_count = asyncio.run(consumer.ack_many(["1-0", "2-0"]))

    assert acked_count == 2
    assert redis.acked == [
        {
            "name": EVENT_STREAM_KEY,
            "groupname": EVENT_CONSUMER_GROUP,
            "ids": ("1-0", "2-0"),
        }
    ]

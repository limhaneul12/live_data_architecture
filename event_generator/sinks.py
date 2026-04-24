"""Output sinks for generated event JSON Lines."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from redis import Redis, RedisCluster
from redis.cluster import ClusterNode

from event_generator.constants import (
    DEFAULT_REDIS_URL,
    EVENT_STREAM_KEY,
    EVENT_STREAM_MAXLEN,
    REDIS_MODE_ENV_NAME,
    REDIS_URL_ENV_NAME,
    RedisMode,
)

RedisXAddClient = Redis | RedisCluster


@dataclass(slots=True)
class StdoutEventSink:
    """Emit event JSON Lines records to stdout."""

    def emit(self, line: str) -> None:
        """Print one event JSON line.

        Args:
            line: Compact event JSON string without trailing newline.

        Returns:
            None.
        """
        print(line, flush=True)

    def close(self) -> None:
        """Stdout does not need explicit cleanup.

        Args:
            None.

        Returns:
            None.
        """


@dataclass(slots=True)
class RedisStreamEventSink:
    """Publish event JSON Lines records to the canonical Redis Stream."""

    client: RedisXAddClient

    @classmethod
    def from_environment(cls) -> RedisStreamEventSink:
        """Create a Redis stream sink from stable constants and environment URL.

        Args:
            None.

        Returns:
            Redis Stream event sink.
        """
        redis_urls = _redis_urls_from_environment()
        redis_mode = _redis_mode_from_environment()
        client = _build_redis_client(redis_urls=redis_urls, redis_mode=redis_mode)
        return cls(client=client)

    def emit(self, line: str) -> None:
        """Publish one JSON line under the Redis Stream payload field.

        Args:
            line: Compact event JSON string without trailing newline.

        Returns:
            None.
        """
        self.client.xadd(
            EVENT_STREAM_KEY,
            {"payload": line},
            id="*",
            maxlen=EVENT_STREAM_MAXLEN,
            approximate=True,
        )

    def close(self) -> None:
        """Close the Redis client connection.

        Args:
            None.

        Returns:
            None.
        """
        self.client.close()


def _redis_urls_from_environment() -> tuple[str, ...]:
    raw_value = os.environ.get(REDIS_URL_ENV_NAME, DEFAULT_REDIS_URL)
    urls = tuple(url.strip() for url in raw_value.split(",") if url.strip())
    if urls:
        return urls
    return (DEFAULT_REDIS_URL,)


def _redis_mode_from_environment() -> RedisMode:
    raw_value = os.environ.get(REDIS_MODE_ENV_NAME, RedisMode.SINGLE.value)
    if raw_value == RedisMode.CLUSTER.value:
        return RedisMode.CLUSTER
    return RedisMode.SINGLE


def _build_redis_client(
    *, redis_urls: tuple[str, ...], redis_mode: RedisMode
) -> RedisXAddClient:
    if redis_mode is RedisMode.CLUSTER:
        first_url = urlparse(redis_urls[0])
        startup_nodes = [
            ClusterNode(parsed.hostname or "localhost", parsed.port or 6379)
            for parsed in (urlparse(url) for url in redis_urls)
        ]
        return RedisCluster(
            startup_nodes=startup_nodes,
            username=first_url.username,
            password=first_url.password,
            decode_responses=True,
        )

    return Redis.from_url(redis_urls[0], decode_responses=True)

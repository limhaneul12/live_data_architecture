"""Redis client factory supporting single-node and cluster modes."""

from __future__ import annotations

from urllib.parse import urlparse

from app.platform.config import StreamConfig
from redis.asyncio import Redis, RedisCluster
from redis.asyncio.cluster import ClusterNode

AsyncRedisClient = Redis | RedisCluster


def build_async_redis_client(stream_config: StreamConfig) -> AsyncRedisClient:
    """Build a Redis client for the configured deployment mode.

    Args:
        stream_config: Runtime Redis URL and deployment mode configuration.

    Returns:
        Async Redis single-node or cluster client.
    """
    if stream_config.redis_mode == "cluster":
        first_url = urlparse(stream_config.redis_urls[0])
        startup_nodes = [
            ClusterNode(parsed.hostname or "localhost", parsed.port or 6379)
            for parsed in (urlparse(url) for url in stream_config.redis_urls)
        ]
        return RedisCluster(
            startup_nodes=startup_nodes,
            username=first_url.username,
            password=first_url.password,
            decode_responses=False,
        )

    return Redis.from_url(stream_config.redis_urls[0], decode_responses=False)

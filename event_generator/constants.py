"""Stable runtime constants for the event generator."""

from __future__ import annotations

from enum import StrEnum

EVENT_STREAM_KEY = "web.events.raw.v1"
EVENT_STREAM_MAXLEN = 100_000
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
REDIS_URL_ENV_NAME = "STREAM_REDIS_URL"
REDIS_MODE_ENV_NAME = "STREAM_REDIS_MODE"


class RedisMode(StrEnum):
    """Supported Redis deployment modes for stream publishing."""

    SINGLE = "single"
    CLUSTER = "cluster"

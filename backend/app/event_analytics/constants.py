"""Stable constants for the event analytics pipeline."""

from __future__ import annotations

from typing import Final

EVENT_STREAM_KEY = "web.events.raw.v1"
EVENT_STREAM_MAXLEN = 100_000
EVENT_CONSUMER_GROUP = "event_analytics_writer"
EVENT_CONSUMER_NAME = "app-consumer-1"
EVENT_STREAM_GROUP_START_ID = "0-0"
EVENT_STREAM_PENDING_ID = "0"
EVENT_STREAM_NEW_ID = ">"
EVENT_CONSUMER_ERROR_BACKOFF_SECONDS = 1.0
MAX_ANALYTICS_SQL_TEXT_LENGTH: Final = 4_000
MAX_ANALYTICS_CONNECTION_ADDRESS_LENGTH: Final = 1_000
ANALYTICS_CONNECTION_TEST_TIMEOUT_SECONDS: Final = 2.0

"""Stable constants for the event analytics stream pipeline."""

from __future__ import annotations

EVENT_STREAM_KEY = "web.events.raw.v1"
EVENT_STREAM_MAXLEN = 100_000
EVENT_CONSUMER_GROUP = "event_analytics_writer"
EVENT_CONSUMER_NAME = "app-consumer-1"
EVENT_STREAM_GROUP_START_ID = "0-0"
EVENT_STREAM_PENDING_ID = "0"
EVENT_STREAM_NEW_ID = ">"
EVENT_CONSUMER_ERROR_BACKOFF_SECONDS = 1.0

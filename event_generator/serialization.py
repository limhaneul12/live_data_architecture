"""JSON Lines serialization helpers for generated events."""

from __future__ import annotations

import json

from event_generator.models import GeneratedEvent


def event_to_json_line(event: GeneratedEvent) -> str:
    """Serialize an event to one compact JSON Lines record without a newline.

    Args:
        event: Generated event dataclass to serialize.

    Returns:
        Compact JSON string without a trailing newline.
    """
    return json.dumps(
        event.to_json_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
    )

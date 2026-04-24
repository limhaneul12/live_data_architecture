import json
from datetime import UTC, datetime

from event_generator.models import (
    EVENT_FIELD_NAMES,
    EVENT_SCHEMA_VERSION,
    EventType,
    GeneratedEvent,
    TrafficPhase,
)
from event_generator.serialization import event_to_json_line


def test_serializes_event_to_one_parseable_json_line() -> None:
    event = GeneratedEvent(
        event_id="evt_000000001029",
        event_type=EventType.PAGE_VIEW,
        occurred_at=datetime(2026, 4, 24, tzinfo=UTC),
        user_id="user_001",
        traffic_phase=TrafficPhase.NORMAL,
        producer_id="producer_local",
        page_path="/products",
        category_id="cat_accessory",
    )

    line = event_to_json_line(event)
    payload = json.loads(line)

    assert "\n" not in line
    assert tuple(payload) == EVENT_FIELD_NAMES
    assert payload["schema_version"] == EVENT_SCHEMA_VERSION
    assert payload["event_id"] == "evt_000000001029"
    assert payload["event_type"] == "page_view"
    assert payload["occurred_at"] == "2026-04-24T00:00:00.000Z"


def test_uses_null_for_not_applicable_fields() -> None:
    event = GeneratedEvent(
        event_id="evt_000000001029",
        event_type=EventType.PAGE_VIEW,
        occurred_at=datetime(2026, 4, 24, tzinfo=UTC),
        user_id="user_001",
        traffic_phase=TrafficPhase.NORMAL,
        producer_id="producer_local",
        page_path="/products",
    )

    payload = json.loads(event_to_json_line(event))

    expected_null_fields = {
        "category_id": None,
        "product_id": None,
        "amount": None,
        "currency": None,
        "error_code": None,
        "error_message": None,
    }
    assert {key: payload[key] for key in expected_null_fields} == expected_null_fields

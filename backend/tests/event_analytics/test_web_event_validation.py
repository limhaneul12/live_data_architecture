from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.event_analytics.interface.schemas import WebEventPayload
from pydantic import ValidationError


def valid_payload() -> dict[str, str | float | None]:
    return {
        "schema_version": "web_event.v1",
        "event_id": "evt_abc123def456",
        "event_type": "purchase",
        "occurred_at": "2026-04-24T00:00:00.000Z",
        "user_id": "user_001",
        "traffic_phase": "normal",
        "producer_id": "producer_local",
        "page_path": None,
        "category_id": "cat_smartphone",
        "product_id": "prod_iphone_15",
        "amount": 799.99,
        "currency": "USD",
        "error_code": None,
        "error_message": None,
    }


def test_web_event_accepts_v1_payload_shape() -> None:
    event = WebEventPayload.model_validate(valid_payload())

    expected = {
        "schema_version": "web_event.v1",
        "event_id": "evt_abc123def456",
        "event_type": "purchase",
        "occurred_at": datetime(2026, 4, 24, tzinfo=UTC),
        "user_id": "user_001",
        "traffic_phase": "normal",
        "producer_id": "producer_local",
        "page_path": None,
        "category_id": "cat_smartphone",
        "product_id": "prod_iphone_15",
        "amount": Decimal("799.99"),
        "currency": "USD",
        "error_code": None,
        "error_message": None,
    }
    assert event.model_dump() == expected


def test_web_event_rejects_unknown_schema_version() -> None:
    payload = valid_payload() | {"schema_version": "web_event.v2"}

    with pytest.raises(ValidationError):
        WebEventPayload.model_validate(payload)


def test_web_event_rejects_extra_session_id_field() -> None:
    payload = valid_payload() | {"session_id": "sess_001_01"}

    with pytest.raises(ValidationError):
        WebEventPayload.model_validate(payload)


def test_web_event_requires_nullable_contract_fields() -> None:
    payload = valid_payload()
    del payload["error_message"]

    with pytest.raises(ValidationError):
        WebEventPayload.model_validate(payload)

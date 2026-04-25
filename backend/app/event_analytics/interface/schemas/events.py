"""Pydantic IO schemas for event analytics stream payloads."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from app.event_analytics.domain.events import (
    EventSchemaVersion,
    EventType,
    TrafficPhase,
)
from pydantic import BaseModel, ConfigDict, StrictStr, StringConstraints

NonEmptyText = Annotated[StrictStr, StringConstraints(min_length=1)]


class WebEventPayload(BaseModel):
    """Redis stream-boundary payload schema for `web_event.v1`.

    The schema forbids unknown fields and is immutable after validation. Global
    strict mode is intentionally not enabled because Redis JSON payloads carry
    datetimes and decimals as JSON strings/numbers that must be parsed at this
    IO boundary before entering internal dataclasses.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "schema_version": "web_event.v1",
                    "event_id": "evt_7f3a9c1e2b4098ab76cd",
                    "event_type": "product_click",
                    "occurred_at": "2026-04-24T00:00:00.000Z",
                    "user_id": "user_013",
                    "traffic_phase": "normal",
                    "producer_id": "producer_local",
                    "page_path": "/products/prod_iphone_15",
                    "category_id": "cat_smartphone",
                    "product_id": "prod_iphone_15",
                    "amount": None,
                    "currency": None,
                    "error_code": None,
                    "error_message": None,
                }
            ]
        },
    )

    schema_version: EventSchemaVersion
    event_id: NonEmptyText
    event_type: EventType
    occurred_at: datetime
    user_id: NonEmptyText
    traffic_phase: TrafficPhase
    producer_id: NonEmptyText
    page_path: str | None
    category_id: str | None
    product_id: str | None
    amount: Decimal | None
    currency: str | None
    error_code: str | None
    error_message: str | None

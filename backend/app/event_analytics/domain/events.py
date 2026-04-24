"""Event analytics internal domain event models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

EventSchemaVersion = Literal["web_event.v1"]
EventType = Literal[
    "page_view",
    "product_click",
    "add_to_cart",
    "purchase",
    "checkout_error",
]
TrafficPhase = Literal["slow", "normal", "burst"]


@dataclass(frozen=True, slots=True, kw_only=True)
class WebEvent:
    """Internal validated event used by application and persistence logic."""

    schema_version: EventSchemaVersion
    event_id: str
    event_type: EventType
    occurred_at: datetime
    user_id: str
    traffic_phase: TrafficPhase
    producer_id: str
    page_path: str | None
    category_id: str | None
    product_id: str | None
    amount: Decimal | None
    currency: str | None
    error_code: str | None
    error_message: str | None

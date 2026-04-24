"""Typed event models emitted by the independent event generator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

type JsonScalar = str | int | float | None
type JsonObject = dict[str, JsonScalar]

EVENT_SCHEMA_VERSION = "web_event.v1"


class EventType(StrEnum):
    """Supported commerce web-service event types."""

    PAGE_VIEW = "page_view"
    PRODUCT_CLICK = "product_click"
    ADD_TO_CART = "add_to_cart"
    PURCHASE = "purchase"
    CHECKOUT_ERROR = "checkout_error"


class TrafficPhase(StrEnum):
    """Traffic phases used to simulate changing producer load."""

    SLOW = "slow"
    NORMAL = "normal"
    BURST = "burst"


EVENT_FIELD_NAMES: tuple[str, ...] = (
    "schema_version",
    "event_id",
    "event_type",
    "occurred_at",
    "user_id",
    "traffic_phase",
    "producer_id",
    "page_path",
    "category_id",
    "product_id",
    "amount",
    "currency",
    "error_code",
    "error_message",
)


@dataclass(frozen=True, slots=True, kw_only=True)
class GeneratedEvent:
    """Single structured event emitted as one JSON Lines record."""

    event_id: str
    event_type: EventType
    occurred_at: datetime
    user_id: str
    traffic_phase: TrafficPhase
    producer_id: str
    page_path: str | None = None
    category_id: str | None = None
    product_id: str | None = None
    amount: float | None = None
    currency: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    def to_json_dict(self) -> JsonObject:
        """Return a stable JSON-serializable dictionary for this event.

        Args:
            None.

        Returns:
            Ordered JSON-serializable event dictionary.
        """
        occurred_at = self.occurred_at.astimezone(UTC)
        occurred_at_text = occurred_at.isoformat(timespec="milliseconds").replace(
            "+00:00",
            "Z",
        )

        return {
            "schema_version": EVENT_SCHEMA_VERSION,
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "occurred_at": occurred_at_text,
            "user_id": self.user_id,
            "traffic_phase": self.traffic_phase.value,
            "producer_id": self.producer_id,
            "page_path": self.page_path,
            "category_id": self.category_id,
            "product_id": self.product_id,
            "amount": self.amount,
            "currency": self.currency,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }

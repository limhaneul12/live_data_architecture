"""Deterministic random event generation for commerce web-service events."""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

from event_generator.models import EventType, GeneratedEvent, TrafficPhase
from event_generator.traffic_profile import TrafficProfile

_EVENT_TYPES: tuple[EventType, ...] = (
    EventType.PAGE_VIEW,
    EventType.PRODUCT_CLICK,
    EventType.ADD_TO_CART,
    EventType.PURCHASE,
    EventType.CHECKOUT_ERROR,
)
_EVENT_WEIGHTS: tuple[int, ...] = (45, 25, 15, 8, 7)
_DAY_HOURS = tuple(range(24))
_HOUR_WEIGHTS_BY_PHASE: dict[TrafficPhase, tuple[int, ...]] = {
    TrafficPhase.SLOW: (
        9,
        9,
        8,
        7,
        7,
        6,
        5,
        4,
        3,
        2,
        2,
        2,
        2,
        2,
        2,
        2,
        3,
        4,
        5,
        6,
        6,
        7,
        8,
        9,
    ),
    TrafficPhase.NORMAL: (
        2,
        1,
        1,
        1,
        1,
        2,
        4,
        6,
        8,
        9,
        10,
        10,
        9,
        9,
        9,
        9,
        10,
        10,
        9,
        8,
        7,
        6,
        4,
        3,
    ),
    TrafficPhase.BURST: (
        1,
        1,
        1,
        1,
        1,
        1,
        2,
        4,
        7,
        9,
        10,
        12,
        12,
        10,
        9,
        10,
        12,
        15,
        18,
        20,
        18,
        14,
        8,
        4,
    ),
}


@dataclass(frozen=True, slots=True)
class PageTarget:
    """Page path and optional category represented by a page view."""

    path: str
    category_id: str | None = None


@dataclass(frozen=True, slots=True)
class Product:
    """Small catalog product used to generate repeatable product interactions."""

    product_id: str
    category_id: str
    price_cents: int


_PAGE_TARGETS: tuple[PageTarget, ...] = (
    PageTarget("/"),
    PageTarget("/products"),
    PageTarget("/products/new"),
    PageTarget("/products/best"),
    PageTarget("/cart"),
    PageTarget("/checkout"),
    PageTarget("/categories/smartphone", "cat_smartphone"),
    PageTarget("/categories/laptop", "cat_laptop"),
    PageTarget("/categories/audio", "cat_audio"),
    PageTarget("/categories/accessory", "cat_accessory"),
)
_PRODUCTS: tuple[Product, ...] = (
    Product("prod_iphone_15", "cat_smartphone", 99_900),
    Product("prod_galaxy_s24", "cat_smartphone", 89_900),
    Product("prod_pixel_9", "cat_smartphone", 79_900),
    Product("prod_macbook_air_m3", "cat_laptop", 129_900),
    Product("prod_thinkpad_x1", "cat_laptop", 159_900),
    Product("prod_airpods_pro", "cat_audio", 24_900),
    Product("prod_sony_wh1000xm5", "cat_audio", 39_900),
    Product("prod_magic_keyboard", "cat_accessory", 19_900),
    Product("prod_usb_c_hub", "cat_accessory", 6_900),
    Product("prod_phone_case_clear", "cat_accessory", 2_900),
)
_ERROR_MESSAGES: dict[str, str] = {
    "PAYMENT_DECLINED": "Payment was declined by the card issuer.",
    "TIMEOUT": "Checkout request timed out while waiting for the payment gateway.",
    "INVALID_COUPON": "The submitted coupon cannot be applied to this order.",
    "PG_UNAVAILABLE": "Payment gateway is temporarily unavailable.",
}
_EVENT_ID_COUNTER_MULTIPLIER = 0x9E3779B97F4A7C15
_EVENT_ID_COUNTER_MASK = (1 << 64) - 1


@dataclass(frozen=True, slots=True, kw_only=True)
class EventGeneratorConfig:
    """Configuration for deterministic event generation."""

    seed: int = 20260424
    producer_id: str = "producer_local"
    start_time: datetime = datetime(2026, 4, 24, tzinfo=UTC)


class EventGenerator:
    """Generate deterministic random commerce events for stdout streaming."""

    def __init__(
        self,
        *,
        config: EventGeneratorConfig,
        traffic_profile: TrafficProfile,
    ) -> None:
        """Create a generator with separate seeded event and traffic sources.

        Args:
            config: Deterministic generator configuration.
            traffic_profile: Seeded traffic phase profile.
        """
        self._rng = random.Random(config.seed)  # noqa: S311
        self._config = config
        self._traffic_profile = traffic_profile
        self._event_date = config.start_time.astimezone(UTC).date()
        self._event_id_prefix = self._rng.getrandbits(32)
        self._event_sequence = 0

    def iter_events(self, *, max_events: int | None = None) -> Iterator[GeneratedEvent]:
        """Yield generated events until max_events is reached or indefinitely.

        Args:
            max_events: Optional maximum number of events to emit.

        Returns:
            Iterator over generated event dataclasses.
        """
        emitted = 0
        while max_events is None or emitted < max_events:
            emitted += 1
            yield self.generate_one()

    def generate_one(self) -> GeneratedEvent:
        """Generate one structured event and advance simulated producer time.

        Args:
            None.

        Returns:
            Generated event dataclass.
        """
        phase = self._traffic_profile.next_phase()
        event_type = self._choose_event_type()
        return self._build_event(event_type=event_type, phase=phase)

    def seconds_until_next_event(self, phase: TrafficPhase) -> float:
        """Return the phase-specific delay before the next event should be emitted.

        Args:
            phase: Traffic phase for the event that was just emitted.

        Returns:
            Seconds to sleep before emitting the next event.
        """
        return self._traffic_profile.seconds_between_events(phase)

    def _choose_event_type(self) -> EventType:
        return self._rng.choices(_EVENT_TYPES, weights=_EVENT_WEIGHTS, k=1)[0]

    def _choose_event_id(self) -> str:
        self._event_sequence += 1
        permuted_counter = (
            self._event_sequence * _EVENT_ID_COUNTER_MULTIPLIER
        ) & _EVENT_ID_COUNTER_MASK
        return f"evt_{self._event_id_prefix:08x}{permuted_counter:016x}"

    def _choose_occurred_at(self, phase: TrafficPhase) -> datetime:
        weights = _HOUR_WEIGHTS_BY_PHASE[phase]
        hour = self._rng.choices(_DAY_HOURS, weights=weights, k=1)[0]
        return datetime(
            self._event_date.year,
            self._event_date.month,
            self._event_date.day,
            hour,
            self._rng.randrange(60),
            self._rng.randrange(60),
            self._rng.randrange(1_000) * 1_000,
            tzinfo=UTC,
        )

    def _build_event(
        self, *, event_type: EventType, phase: TrafficPhase
    ) -> GeneratedEvent:
        event_id = self._choose_event_id()
        user_id = self._choose_user_id()

        match event_type:
            case EventType.PAGE_VIEW:
                page_target = self._choose_page_target()
                return self._base_event(
                    event_id=event_id,
                    event_type=event_type,
                    user_id=user_id,
                    phase=phase,
                    page_path=page_target.path,
                    category_id=page_target.category_id,
                )
            case EventType.PRODUCT_CLICK:
                product = self._choose_product()
                return self._base_event(
                    event_id=event_id,
                    event_type=event_type,
                    user_id=user_id,
                    phase=phase,
                    page_path=f"/products/{product.product_id}",
                    category_id=product.category_id,
                    product_id=product.product_id,
                )
            case EventType.ADD_TO_CART:
                product = self._choose_product()
                return self._base_event(
                    event_id=event_id,
                    event_type=event_type,
                    user_id=user_id,
                    phase=phase,
                    category_id=product.category_id,
                    product_id=product.product_id,
                )
            case EventType.PURCHASE:
                product = self._choose_product()
                return self._base_event(
                    event_id=event_id,
                    event_type=event_type,
                    user_id=user_id,
                    phase=phase,
                    category_id=product.category_id,
                    product_id=product.product_id,
                    amount=self._choose_amount(product=product),
                    currency="USD",
                )
            case EventType.CHECKOUT_ERROR:
                product = self._choose_product()
                error_code = self._choose_error_code()
                return self._base_event(
                    event_id=event_id,
                    event_type=event_type,
                    user_id=user_id,
                    phase=phase,
                    category_id=product.category_id,
                    product_id=product.product_id,
                    error_code=error_code,
                    error_message=_ERROR_MESSAGES[error_code],
                )

    def _base_event(
        self,
        *,
        event_id: str,
        event_type: EventType,
        user_id: str,
        phase: TrafficPhase,
        page_path: str | None = None,
        category_id: str | None = None,
        product_id: str | None = None,
        amount: float | None = None,
        currency: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> GeneratedEvent:
        return GeneratedEvent(
            event_id=event_id,
            event_type=event_type,
            occurred_at=self._choose_occurred_at(phase),
            user_id=user_id,
            traffic_phase=phase,
            producer_id=self._config.producer_id,
            page_path=page_path,
            category_id=category_id,
            product_id=product_id,
            amount=amount,
            currency=currency,
            error_code=error_code,
            error_message=error_message,
        )

    def _choose_user_id(self) -> str:
        return f"user_{self._rng.randint(1, 200):03d}"

    def _choose_page_target(self) -> PageTarget:
        return self._rng.choice(_PAGE_TARGETS)

    def _choose_product(self) -> Product:
        return self._rng.choice(_PRODUCTS)

    def _choose_error_code(self) -> str:
        return self._rng.choice(tuple(_ERROR_MESSAGES))

    def _choose_amount(self, *, product: Product) -> float:
        discount_cents = self._rng.randint(0, product.price_cents // 5)
        cents = product.price_cents - discount_cents
        return round(cents / 100, 2)

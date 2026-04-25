import re
from collections import Counter
from datetime import UTC, datetime

from event_generator.generator import EventGenerator, EventGeneratorConfig
from event_generator.models import EventType
from event_generator.traffic_profile import (
    PhaseRates,
    TrafficProfile,
    TrafficProfileConfig,
)


def build_generator(seed: int = 20260424) -> EventGenerator:
    traffic_config = TrafficProfileConfig(rates=PhaseRates())
    return EventGenerator(
        config=EventGeneratorConfig(
            seed=seed,
            producer_id="producer_test",
            start_time=datetime(2026, 4, 24, tzinfo=UTC),
        ),
        traffic_profile=TrafficProfile(seed=seed + 1, config=traffic_config),
    )


def test_same_seed_generates_same_sequence() -> None:
    first = [
        event.to_json_dict() for event in build_generator().iter_events(max_events=20)
    ]
    second = [
        event.to_json_dict() for event in build_generator().iter_events(max_events=20)
    ]

    assert first == second


def test_different_seed_changes_sequence() -> None:
    first = [
        event.to_json_dict()
        for event in build_generator(seed=1).iter_events(max_events=20)
    ]
    second = [
        event.to_json_dict()
        for event in build_generator(seed=2).iter_events(max_events=20)
    ]

    assert first != second


def test_event_ids_are_seeded_random_codes_not_sequence() -> None:
    events = list(build_generator().iter_events(max_events=20))
    event_ids = [event.event_id for event in events]
    sequential_ids = [f"evt_{index:012x}" for index in range(1, 21)]

    assert event_ids != sequential_ids
    assert len(event_ids) == len(set(event_ids))
    assert all(re.fullmatch(r"evt_[0-9a-f]{24}", event_id) for event_id in event_ids)


def test_generates_only_allowed_event_types() -> None:
    events = list(build_generator().iter_events(max_events=100))
    allowed = {event_type.value for event_type in EventType}

    assert {event.event_type.value for event in events} <= allowed


def test_occurred_at_keeps_configured_date_but_randomizes_hours() -> None:
    events = list(build_generator().iter_events(max_events=500))
    event_dates = {event.occurred_at.date() for event in events}
    event_hours = {event.occurred_at.hour for event in events}

    assert event_dates == {datetime(2026, 4, 24, tzinfo=UTC).date()}
    assert len(event_hours) > 12


def test_occurred_at_hour_distribution_favors_active_hours() -> None:
    events = list(build_generator().iter_events(max_events=5_000))
    counts = Counter(event.occurred_at.hour for event in events)
    overnight_count = sum(counts[hour] for hour in range(6))
    active_hour_count = sum(counts[hour] for hour in range(10, 22))

    assert active_hour_count > overnight_count


def test_large_sample_contains_all_required_event_types() -> None:
    events = list(build_generator().iter_events(max_events=1_000))
    counts = Counter(event.event_type for event in events)

    assert set(counts) == set(EventType)


def test_purchase_events_have_revenue_fields() -> None:
    events = list(build_generator().iter_events(max_events=1_000))
    purchases = [event for event in events if event.event_type is EventType.PURCHASE]

    assert purchases
    assert all(event.product_id is not None for event in purchases)
    assert all(event.category_id is not None for event in purchases)
    assert all(event.amount is not None and event.amount > 0 for event in purchases)
    assert all(event.currency == "USD" for event in purchases)


def test_product_ids_are_repeatable_opaque_product_codes() -> None:
    events = list(build_generator().iter_events(max_events=1_000))
    product_ids = [event.product_id for event in events if event.product_id is not None]

    assert product_ids
    assert all(
        re.fullmatch(r"prod_[a-z0-9_]+", product_id) for product_id in product_ids
    )


def test_large_sample_uses_unique_event_ids_but_repeats_product_and_category() -> None:
    events = list(build_generator().iter_events(max_events=1_000))
    event_id_counts = Counter(event.event_id for event in events)
    product_id_counts = Counter(
        event.product_id for event in events if event.product_id is not None
    )
    category_id_counts = Counter(
        event.category_id for event in events if event.category_id is not None
    )

    assert all(count == 1 for count in event_id_counts.values())
    assert any(count > 1 for count in product_id_counts.values())
    assert any(count > 1 for count in category_id_counts.values())


def test_checkout_error_events_have_error_fields() -> None:
    events = list(build_generator().iter_events(max_events=1_000))
    checkout_errors = [
        event for event in events if event.event_type is EventType.CHECKOUT_ERROR
    ]

    assert checkout_errors
    assert all(event.product_id is not None for event in checkout_errors)
    assert all(event.category_id is not None for event in checkout_errors)
    assert all(event.error_code is not None for event in checkout_errors)
    assert all(event.error_message is not None for event in checkout_errors)

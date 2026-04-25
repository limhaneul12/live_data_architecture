import re

from event_generator.faker_catalog import FakerDataCatalog
from event_generator.generator import EventGenerator, EventGeneratorConfig
from event_generator.models import EventType
from event_generator.traffic_profile import (
    PhaseRates,
    TrafficProfile,
    TrafficProfileConfig,
)


def test_faker_catalog_is_deterministic_for_same_seed() -> None:
    first = FakerDataCatalog(seed=20260424)
    second = FakerDataCatalog(seed=20260424)

    assert first.users == second.users
    assert first.products == second.products
    assert first.page_targets == second.page_targets


def test_faker_catalog_builds_repeatable_browser_user_and_product_pools() -> None:
    catalog = FakerDataCatalog(seed=20260424)
    user_ids = [user.user_id for user in catalog.users]
    product_ids = [product.product_id for product in catalog.products]
    page_paths = [target.path for target in catalog.page_targets]

    assert len(user_ids) == 160
    assert len(user_ids) == len(set(user_ids))
    assert all(re.fullmatch(r"user_[0-9a-f]{12}", user_id) for user_id in user_ids)
    assert all(
        user.preferred_category_id
        in {category.category_id for category in catalog.categories}
        for user in catalog.users
    )
    assert len(product_ids) == 16
    assert len(product_ids) == len(set(product_ids))
    assert all(
        re.fullmatch(r"prod_[a-z0-9_]+", product_id) for product_id in product_ids
    )
    assert any(path.startswith("/search/") for path in page_paths)
    assert any(path.startswith("/collections/") for path in page_paths)
    assert any(path == "/account/orders" for path in page_paths)


def test_generator_emits_faker_backed_users_and_browser_paths() -> None:
    seed = 20260424
    traffic_config = TrafficProfileConfig(rates=PhaseRates())
    generator = EventGenerator(
        config=EventGeneratorConfig(
            seed=seed,
            producer_id="producer_test",
        ),
        traffic_profile=TrafficProfile(seed=seed + 1, config=traffic_config),
    )

    events = list(generator.iter_events(max_events=2_000))
    user_ids = [event.user_id for event in events]
    page_paths = [
        event.page_path
        for event in events
        if event.event_type is EventType.PAGE_VIEW and event.page_path is not None
    ]

    assert len(set(user_ids)) == 160
    assert all(re.fullmatch(r"user_[0-9a-f]{12}", user_id) for user_id in user_ids)
    assert any(path.startswith("/search/") for path in page_paths)
    assert any(path.startswith("/collections/") for path in page_paths)

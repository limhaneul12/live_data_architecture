import importlib.util
from pathlib import Path


def load_views_migration_module():
    migration_path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "20260425_0002_create_event_analytics_views.py"
    )
    spec = importlib.util.spec_from_file_location(
        "analytics_views_migration", migration_path
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_analytics_views_migration_declares_second_revision() -> None:
    module = load_views_migration_module()

    expected = {
        "revision": "20260425_0002",
        "down_revision": "20260424_0001",
        "branch_labels": None,
        "depends_on": None,
    }
    assert {key: getattr(module, key) for key in expected} == expected


def test_analytics_views_migration_lists_generated_views() -> None:
    module = load_views_migration_module()

    assert set(module.VIEW_NAMES) == {
        "event_type_counts",
        "user_event_counts",
        "hourly_event_counts",
        "error_event_ratio",
        "commerce_funnel_counts",
        "product_event_counts",
    }

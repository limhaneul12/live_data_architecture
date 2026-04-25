import importlib.util
import sys
from pathlib import Path

import pytest


def load_analytics_reader_migration_module():
    migration_path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "20260425_0003_create_analytics_reader_grants.py"
    )
    spec = importlib.util.spec_from_file_location(
        "analytics_reader_grants_migration",
        migration_path,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_analytics_reader_grants_migration_declares_third_revision() -> None:
    module = load_analytics_reader_migration_module()

    assert module.revision == "20260425_0003"
    assert module.down_revision == "20260425_0002"
    assert module.branch_labels is None
    assert module.depends_on is None


def test_analytics_reader_grants_migration_lists_generated_views() -> None:
    module = load_analytics_reader_migration_module()

    assert set(module.ANALYTICS_VIEW_NAMES) == {
        "event_type_counts",
        "user_event_counts",
        "hourly_event_counts",
        "error_event_ratio",
        "commerce_funnel_counts",
        "product_event_counts",
    }


def test_analytics_reader_role_is_skipped_without_analytics_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_analytics_reader_migration_module()
    monkeypatch.delenv(module.ANALYTICS_DATABASE_URL_ENV, raising=False)

    assert module.analytics_reader_role_from_env() is None


def test_analytics_reader_role_is_parsed_from_analytics_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_analytics_reader_migration_module()
    monkeypatch.setenv(
        module.ANALYTICS_DATABASE_URL_ENV,
        "postgresql://analytics_reader:analytics_reader@localhost:15432/live_data",
    )

    role = module.analytics_reader_role_from_env()

    assert role is not None
    assert role.name == "analytics_reader"
    assert role.password == role.name


def test_analytics_reader_role_requires_username(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_analytics_reader_migration_module()
    monkeypatch.setenv(
        module.ANALYTICS_DATABASE_URL_ENV,
        "postgresql://localhost:15432/live_data",
    )

    with pytest.raises(ValueError, match="must include a username"):
        module.analytics_reader_role_from_env()

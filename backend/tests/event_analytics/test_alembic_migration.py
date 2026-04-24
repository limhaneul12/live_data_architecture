import importlib.util
from pathlib import Path


def load_migration_module():
    migration_path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "20260424_0001_create_events_table.py"
    )
    spec = importlib.util.spec_from_file_location("events_migration", migration_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_events_migration_declares_initial_revision() -> None:
    module = load_migration_module()

    expected = {
        "revision": "20260424_0001",
        "down_revision": None,
        "branch_labels": None,
        "depends_on": None,
    }
    assert {key: getattr(module, key) for key in expected} == expected


def test_events_migration_has_upgrade_and_downgrade() -> None:
    module = load_migration_module()

    assert callable(module.upgrade)
    assert callable(module.downgrade)

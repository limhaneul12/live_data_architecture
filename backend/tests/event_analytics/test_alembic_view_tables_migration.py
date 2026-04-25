import importlib.util
from pathlib import Path


def load_view_tables_migration_module():
    migration_path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "20260425_0004_create_analytics_view_tables.py"
    )
    spec = importlib.util.spec_from_file_location(
        "analytics_view_tables_migration",
        migration_path,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_analytics_view_tables_migration_declares_fourth_revision() -> None:
    module = load_view_tables_migration_module()

    assert module.revision == "20260425_0004"
    assert module.down_revision == "20260425_0003"
    assert module.branch_labels is None
    assert module.depends_on is None

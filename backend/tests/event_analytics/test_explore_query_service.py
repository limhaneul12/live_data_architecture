import pytest
from app.event_analytics.application.explore_query_service import (
    ExploreQueryValidationError,
    build_explore_query,
)
from app.event_analytics.domain.explore_query import ExploreQuery


def test_build_explore_query_accepts_catalog_dataset_and_caps_limit() -> None:
    query = build_explore_query(
        dataset_name="event_type_counts",
        column_names=("event_type", "event_count"),
        order_by="event_count",
        order_direction="desc",
        row_limit=5_000,
    )

    assert query == ExploreQuery(
        dataset_name="event_type_counts",
        column_names=("event_type", "event_count"),
        order_by="event_count",
        order_direction="desc",
        row_limit=500,
    )


@pytest.mark.parametrize(
    ("dataset_name", "column_names", "order_by", "reason"),
    [
        ("missing_dataset", ("event_type",), None, "unknown_dataset"),
        ("event_type_counts", ("event_type", "pg_sleep"), None, "unknown_column"),
        ("event_type_counts", ("event_type", "event_type"), None, "duplicate_columns"),
        ("event_type_counts", ("event_type",), "pg_sleep", "unknown_order_column"),
    ],
)
def test_build_explore_query_rejects_non_catalog_shape(
    dataset_name: str,
    column_names: tuple[str, ...],
    order_by: str | None,
    reason: str,
) -> None:
    with pytest.raises(ExploreQueryValidationError) as exc_info:
        build_explore_query(
            dataset_name=dataset_name,
            column_names=column_names,
            order_by=order_by,
            order_direction="desc",
            row_limit=100,
        )

    assert exc_info.value.reason == reason

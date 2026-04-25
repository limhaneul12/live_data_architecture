import pytest
from app.event_analytics.application.analytics_catalog import get_datasets
from app.event_analytics.application.explore_query_service import (
    ExploreQueryValidationError,
    build_explore_query,
)
from app.event_analytics.domain.explore_query import (
    ExploreColumnRef,
    ExploreJoin,
    ExploreQuery,
)


def test_build_explore_query_accepts_catalog_dataset_and_caps_limit() -> None:
    query = build_explore_query(
        dataset_name="event_type_counts",
        datasets=get_datasets(),
        column_refs=(
            ExploreColumnRef(
                dataset_name="event_type_counts",
                column_name="event_type",
            ),
            ExploreColumnRef(
                dataset_name="event_type_counts",
                column_name="event_count",
            ),
        ),
        joins=(),
        order_by=ExploreColumnRef(
            dataset_name="event_type_counts",
            column_name="event_count",
        ),
        order_direction="desc",
        row_limit=5_000,
    )

    assert query == ExploreQuery(
        dataset_name="event_type_counts",
        column_refs=(
            ExploreColumnRef(
                dataset_name="event_type_counts",
                column_name="event_type",
            ),
            ExploreColumnRef(
                dataset_name="event_type_counts",
                column_name="event_count",
            ),
        ),
        joins=(),
        order_by=ExploreColumnRef(
            dataset_name="event_type_counts",
            column_name="event_count",
        ),
        order_direction="desc",
        row_limit=500,
    )


def test_build_explore_query_accepts_one_join() -> None:
    query = build_explore_query(
        dataset_name="product_event_counts",
        datasets=get_datasets(),
        column_refs=(
            ExploreColumnRef(
                dataset_name="product_event_counts",
                column_name="product_id",
            ),
            ExploreColumnRef(
                dataset_name="commerce_funnel_counts",
                column_name="funnel_step",
            ),
            ExploreColumnRef(
                dataset_name="product_event_counts",
                column_name="event_count",
            ),
        ),
        joins=(
            ExploreJoin(
                dataset_name="commerce_funnel_counts",
                left_column="event_type",
                right_column="event_type",
                join_type="inner",
            ),
        ),
        order_by=ExploreColumnRef(
            dataset_name="product_event_counts",
            column_name="event_count",
        ),
        order_direction="desc",
        row_limit=100,
    )

    assert query.joins == (
        ExploreJoin(
            dataset_name="commerce_funnel_counts",
            left_column="event_type",
            right_column="event_type",
            join_type="inner",
        ),
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
            datasets=get_datasets(),
            column_refs=tuple(
                ExploreColumnRef(
                    dataset_name=dataset_name,
                    column_name=column_name,
                )
                for column_name in column_names
            ),
            joins=(),
            order_by=(
                None
                if order_by is None
                else ExploreColumnRef(
                    dataset_name=dataset_name,
                    column_name=order_by,
                )
            ),
            order_direction="desc",
            row_limit=100,
        )

    assert exc_info.value.reason == reason

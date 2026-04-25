from app.event_analytics.application.analytics_catalog import (
    ALLOWED_DATASET_NAMES,
    get_datasets,
    get_preset_queries,
)
from app.event_analytics.application.query_policy import AnalyticsSqlPolicy


def test_datasets_expose_generated_views_only() -> None:
    datasets = get_datasets()
    names = {dataset.name for dataset in datasets}
    event_type_dataset = next(
        dataset for dataset in datasets if dataset.name == "event_type_counts"
    )

    assert "events" not in names
    assert names == ALLOWED_DATASET_NAMES
    assert {
        "event_type_counts",
        "user_event_counts",
        "hourly_event_counts",
        "error_event_ratio",
        "commerce_funnel_counts",
        "product_event_counts",
    }.issubset(names)
    assert tuple(column.name for column in event_type_dataset.columns) == (
        "event_type",
        "event_count",
    )
    assert tuple(column.kind for column in event_type_dataset.columns) == (
        "dimension",
        "metric",
    )


def test_preset_queries_are_policy_validated_selects() -> None:
    policy = AnalyticsSqlPolicy()
    presets = get_preset_queries()

    result = {
        preset.slug: policy.validate(
            sql=preset.sql, requested_row_limit=500
        ).referenced_relations
        for preset in presets
    }

    assert result == {
        "commerce-funnel": frozenset({"commerce_funnel_counts"}),
        "event-type-counts": frozenset({"event_type_counts"}),
        "hourly-event-trend": frozenset({"hourly_event_counts"}),
        "top-users": frozenset({"user_event_counts"}),
        "error-ratio": frozenset({"error_event_ratio"}),
    }

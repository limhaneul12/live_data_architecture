from app.event_analytics.application.chart_suggestion import suggest_chart
from app.event_analytics.domain.query_result import AnalyticsRows


def test_chart_suggestion_uses_bar_for_label_and_numeric_result() -> None:
    rows = AnalyticsRows(
        columns=("event_type", "event_count"),
        rows=(
            {"event_type": "page_view", "event_count": 10},
            {"event_type": "purchase", "event_count": 2},
        ),
    )

    chart = suggest_chart(rows)

    assert chart.chart_kind == "bar"
    assert chart.x_axis == "event_type"
    assert chart.y_axis == "event_count"


def test_chart_suggestion_uses_line_for_temporal_result() -> None:
    rows = AnalyticsRows(
        columns=("event_hour", "event_count"),
        rows=(
            {"event_hour": "2026-04-24T00:00:00+00:00", "event_count": 10},
            {"event_hour": "2026-04-24T01:00:00+00:00", "event_count": 20},
        ),
    )

    chart = suggest_chart(rows)

    assert chart.chart_kind == "line"
    assert chart.x_axis == "event_hour"
    assert chart.y_axis == "event_count"


def test_chart_suggestion_uses_metric_for_numeric_only_result() -> None:
    rows = AnalyticsRows(
        columns=("error_events", "total_events", "error_ratio"),
        rows=({"error_events": 2, "total_events": 10, "error_ratio": 0.2},),
    )

    chart = suggest_chart(rows)

    assert chart.chart_kind == "metric"
    assert chart.y_axis == "error_events"

"""Allowlisted generated datasets and preset analytics SQL."""

from __future__ import annotations

from app.event_analytics.domain.analytics_catalog import AnalyticsDataset, PresetQuery

DATASETS: tuple[AnalyticsDataset, ...] = (
    AnalyticsDataset(
        name="event_type_counts",
        label="Event type counts",
        description="이벤트 타입별 발생 횟수를 집계한 generated view입니다.",
    ),
    AnalyticsDataset(
        name="user_event_counts",
        label="User event counts",
        description="유저별 총 이벤트 수를 집계한 generated view입니다.",
    ),
    AnalyticsDataset(
        name="hourly_event_counts",
        label="Hourly event counts",
        description="시간대와 이벤트 타입별 이벤트 추이를 집계한 generated view입니다.",
    ),
    AnalyticsDataset(
        name="error_event_ratio",
        label="Error event ratio",
        description="checkout_error 비율을 계산한 generated view입니다.",
    ),
    AnalyticsDataset(
        name="commerce_funnel_counts",
        label="Commerce funnel counts",
        description="조회부터 결제 오류까지 커머스 funnel 단계를 집계한 generated view입니다.",
    ),
    AnalyticsDataset(
        name="product_event_counts",
        label="Product event counts",
        description="상품별 클릭/장바구니/구매 이벤트를 집계한 generated view입니다.",
    ),
)

PRESET_QUERIES: tuple[PresetQuery, ...] = (
    PresetQuery(
        slug="commerce-funnel",
        label="Commerce funnel",
        description="page_view → product_click → add_to_cart → purchase → checkout_error 흐름을 비교합니다.",
        sql="""
SELECT funnel_step, event_type, event_count
FROM commerce_funnel_counts
ORDER BY sort_order
""".strip(),
        chart_kind="bar",
    ),
    PresetQuery(
        slug="event-type-counts",
        label="Event type counts",
        description="이벤트 타입별 발생 횟수를 확인합니다.",
        sql="""
SELECT event_type, event_count
FROM event_type_counts
ORDER BY event_count DESC, event_type
""".strip(),
        chart_kind="bar",
    ),
    PresetQuery(
        slug="hourly-event-trend",
        label="Hourly event trend",
        description="시간대별 이벤트 발생 추이를 확인합니다.",
        sql="""
SELECT event_hour, event_type, event_count
FROM hourly_event_counts
ORDER BY event_hour, event_type
""".strip(),
        chart_kind="line",
    ),
    PresetQuery(
        slug="top-users",
        label="Top users",
        description="이벤트를 가장 많이 발생시킨 유저를 확인합니다.",
        sql="""
SELECT user_id, event_count
FROM user_event_counts
ORDER BY event_count DESC, user_id
LIMIT 20
""".strip(),
        chart_kind="bar",
    ),
    PresetQuery(
        slug="error-ratio",
        label="Checkout error ratio",
        description="전체 이벤트 중 checkout_error 비율을 확인합니다.",
        sql="""
SELECT error_events, total_events, error_ratio
FROM error_event_ratio
""".strip(),
        chart_kind="metric",
    ),
)

ALLOWED_DATASET_NAMES = frozenset(dataset.name for dataset in DATASETS)


def get_datasets() -> tuple[AnalyticsDataset, ...]:
    """Return generated datasets exposed to manual SQL.

    Args:
        None.

    Returns:
        Allowlisted generated dataset descriptors.
    """
    return DATASETS


def get_preset_queries() -> tuple[PresetQuery, ...]:
    """Return safe preset queries for the analytics UI.

    Args:
        None.

    Returns:
        Preset SQL query descriptors.
    """
    return PRESET_QUERIES

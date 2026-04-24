from datetime import UTC, datetime
from decimal import Decimal

from app.event_analytics.infrastructure.repositories.postgres_analytics_query_repository import (
    build_limited_select_sql,
    json_safe_value,
)


def test_postgres_query_repository_wraps_select_with_outer_limit() -> None:
    wrapped_sql = build_limited_select_sql(
        sql="SELECT event_type, event_count FROM event_type_counts"
    )

    assert wrapped_sql == (
        "SELECT * FROM (SELECT event_type, event_count FROM event_type_counts) "
        "AS analytics_query LIMIT :row_limit"
    )


def test_postgres_query_repository_converts_db_values_to_json_safe_values() -> None:
    converted_values = {
        "decimal": json_safe_value(Decimal("12.34")),
        "datetime": json_safe_value(datetime(2026, 4, 25, tzinfo=UTC)),
        "text": json_safe_value("ok"),
        "number": json_safe_value(3),
        "null": json_safe_value(None),
    }

    assert converted_values == {
        "decimal": 12.34,
        "datetime": "2026-04-25T00:00:00+00:00",
        "text": "ok",
        "number": 3,
        "null": None,
    }

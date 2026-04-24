import pytest
from app.event_analytics.application.query_policy import (
    AnalyticsSqlPolicy,
    SqlPolicyViolationError,
)


def validate_sql(sql: str, *, row_limit: int = 100) -> tuple[str, frozenset[str], int]:
    result = AnalyticsSqlPolicy().validate(sql=sql, requested_row_limit=row_limit)
    return result.sql, result.referenced_relations, result.row_limit


def assert_rejected(sql: str, reason: str) -> None:
    with pytest.raises(SqlPolicyViolationError) as exc_info:
        AnalyticsSqlPolicy().validate(sql=sql, requested_row_limit=100)
    assert exc_info.value.reason == reason


def test_query_policy_accepts_select_from_allowlisted_view() -> None:
    normalized_sql, relations, row_limit = validate_sql(
        "select event_type, event_count from event_type_counts"
    )

    assert normalized_sql == "SELECT event_type, event_count FROM event_type_counts"
    assert relations == frozenset({"event_type_counts"})
    assert row_limit == 100


def test_query_policy_accepts_read_only_cte_from_allowlisted_view() -> None:
    normalized_sql, relations, row_limit = validate_sql(
        """
        WITH ranked AS (
          SELECT event_type, event_count FROM event_type_counts
        )
        SELECT event_type FROM ranked
        """,
        row_limit=50,
    )

    assert "WITH ranked AS" in normalized_sql
    assert relations == frozenset({"event_type_counts"})
    assert row_limit == 50


def test_query_policy_caps_requested_row_limit() -> None:
    _sql, _relations, row_limit = validate_sql(
        "SELECT event_type FROM event_type_counts",
        row_limit=5_000,
    )

    assert row_limit == 500


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("INSERT INTO events(event_id) VALUES ('evt_1')", "non_select_statement"),
        ("UPDATE events SET event_type = 'x'", "non_select_statement"),
        ("DELETE FROM events", "non_select_statement"),
        ("DROP TABLE events", "non_select_statement"),
        (
            "SELECT * FROM event_type_counts; SELECT * FROM user_event_counts",
            "multiple_statements",
        ),
        ("WITH x AS (DELETE FROM events RETURNING *) SELECT * FROM x", "unsafe_cte"),
        ("SELECT * FROM events", "unknown_relation"),
        ("SELECT * FROM unknown_view", "unknown_relation"),
        ("SELECT * FROM public.event_type_counts", "cross_schema_relation"),
        ("SELECT 1", "missing_relation"),
    ],
)
def test_query_policy_rejects_unsafe_sql(sql: str, reason: str) -> None:
    assert_rejected(sql, reason)

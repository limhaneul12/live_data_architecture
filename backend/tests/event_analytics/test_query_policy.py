import pytest
from app.event_analytics.application.query_policy import (
    MAX_QUERY_TEXT_LENGTH,
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


def test_query_policy_accepts_filtering_and_ordering_on_single_allowlisted_view() -> (
    None
):
    normalized_sql, relations, row_limit = validate_sql(
        """
        SELECT event_type, event_count
        FROM event_type_counts
        WHERE event_count > 0
        ORDER BY event_count DESC, event_type
        """,
        row_limit=50,
    )

    assert normalized_sql == (
        "SELECT event_type, event_count FROM event_type_counts "
        "WHERE event_count > 0 ORDER BY event_count DESC, event_type"
    )
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


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        (
            "SELECT pg_sleep(10), event_count FROM event_type_counts",
            "disallowed_function",
        ),
        (
            "SELECT pg_advisory_lock(1), event_count FROM event_type_counts",
            "disallowed_function",
        ),
        (
            "SELECT set_config('search_path', 'public', false) FROM event_type_counts",
            "disallowed_function",
        ),
        (
            "SELECT count(*) FROM event_type_counts",
            "disallowed_function",
        ),
        (
            "SELECT * FROM event_type_counts JOIN user_event_counts USING (user_id)",
            "disallowed_join",
        ),
        (
            "SELECT * FROM event_type_counts CROSS JOIN user_event_counts",
            "disallowed_join",
        ),
        (
            "SELECT * FROM event_type_counts CROSS JOIN LATERAL (SELECT pg_sleep(1)) s",
            "disallowed_subquery",
        ),
        (
            "SELECT * FROM event_type_counts WHERE event_count = ALL(SELECT 1)",
            "disallowed_subquery",
        ),
        (
            "SELECT * FROM event_type_counts WHERE event_count = SOME(SELECT 1)",
            "disallowed_subquery",
        ),
        (
            """
            SELECT * FROM event_type_counts
            WHERE event_count IN (
              SELECT event_count FROM user_event_counts
            )
            """,
            "disallowed_subquery",
        ),
        (
            """
            WITH ranked AS (
              SELECT event_type, event_count FROM event_type_counts
            )
            SELECT event_type FROM ranked
            """,
            "disallowed_cte",
        ),
        (
            "SELECT * FROM (SELECT * FROM event_type_counts) AS nested_events",
            "disallowed_subquery",
        ),
        (
            "SELECT * INTO temp_event_counts FROM event_type_counts",
            "disallowed_select_into",
        ),
        (
            "SELECT * FROM event_type_counts FOR UPDATE",
            "disallowed_locking_read",
        ),
        (
            "SELECT event_type FROM event_type_counts OFFSET 1000000",
            "disallowed_offset",
        ),
        (
            "SELECT DISTINCT event_type FROM event_type_counts",
            "disallowed_distinct",
        ),
        (
            "SELECT DISTINCT ON (event_type) event_type FROM event_type_counts",
            "disallowed_distinct",
        ),
        (
            "SELECT * FROM event_type_counts TABLESAMPLE SYSTEM (100)",
            "disallowed_table_sample",
        ),
        (
            """
            SELECT event_type, event_count
            FROM event_type_counts
            GROUP BY event_type, event_count
            """,
            "disallowed_grouping",
        ),
        (
            "SELECT event_type, event_count FROM event_type_counts ORDER BY 2 DESC",
            "disallowed_ordinal_order",
        ),
    ],
)
def test_query_policy_rejects_read_only_attack_surfaces(
    sql: str,
    reason: str,
) -> None:
    assert_rejected(sql, reason)


def test_query_policy_rejects_oversized_sql_before_parse() -> None:
    oversized_sql = "x" * (MAX_QUERY_TEXT_LENGTH + 1)

    assert_rejected(oversized_sql, "query_too_long")

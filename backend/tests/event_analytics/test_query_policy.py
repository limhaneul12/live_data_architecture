import pytest
from app.event_analytics.application.query_policy import (
    MAX_QUERY_TEXT_LENGTH,
    AnalyticsSqlPolicy,
    SqlPolicyViolationError,
)


def validate_sql(sql: str, row_limit: int = 100) -> tuple[str, frozenset[str], int]:
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


def test_query_policy_matches_allowlisted_view_case_insensitively() -> None:
    normalized_sql, relations, row_limit = validate_sql(
        "SELECT EVENT_TYPE, EVENT_COUNT FROM EVENT_TYPE_COUNTS"
    )

    assert normalized_sql == "SELECT EVENT_TYPE, EVENT_COUNT FROM EVENT_TYPE_COUNTS"
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


def test_query_policy_accepts_join_between_allowlisted_views() -> None:
    normalized_sql, relations, row_limit = validate_sql(
        """
        SELECT e.event_type, e.event_count, f.funnel_step
        FROM event_type_counts AS e
        JOIN commerce_funnel_counts AS f
          ON e.event_type = f.event_type
        ORDER BY e.event_count DESC
        """,
        row_limit=50,
    )

    assert normalized_sql == (
        "SELECT e.event_type, e.event_count, f.funnel_step FROM event_type_counts "
        "AS e JOIN commerce_funnel_counts AS f ON e.event_type = f.event_type "
        "ORDER BY e.event_count DESC"
    )
    assert relations == frozenset({"event_type_counts", "commerce_funnel_counts"})
    assert row_limit == 50


def test_query_policy_accepts_grouping_and_allowlisted_aggregate_functions() -> None:
    normalized_sql, relations, row_limit = validate_sql(
        """
        SELECT event_type, SUM(event_count) AS total_count
        FROM product_event_counts
        GROUP BY event_type
        ORDER BY total_count DESC
        """,
        row_limit=50,
    )

    assert normalized_sql == (
        "SELECT event_type, SUM(event_count) AS total_count "
        "FROM product_event_counts GROUP BY event_type ORDER BY total_count DESC"
    )
    assert relations == frozenset({"product_event_counts"})
    assert row_limit == 50


def test_query_policy_accepts_read_only_cte_and_subquery_on_allowlisted_views() -> None:
    normalized_sql, relations, row_limit = validate_sql(
        """
        WITH high_events AS (
          SELECT event_type, event_count
          FROM event_type_counts
          WHERE event_count > (
            SELECT AVG(event_count)
            FROM event_type_counts
          )
        )
        SELECT event_type, event_count
        FROM high_events
        ORDER BY event_count DESC
        """,
        row_limit=50,
    )

    assert normalized_sql == (
        "WITH high_events AS (SELECT event_type, event_count FROM event_type_counts "
        "WHERE event_count > (SELECT AVG(event_count) FROM event_type_counts)) "
        "SELECT event_type, event_count FROM high_events ORDER BY event_count DESC"
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
            "SELECT * FROM event_type_counts CROSS JOIN LATERAL (SELECT pg_sleep(1)) s",
            "disallowed_function",
        ),
        (
            "SELECT version() FROM event_type_counts",
            "disallowed_function",
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
            "SELECT * FROM event_type_counts TABLESAMPLE SYSTEM (100)",
            "disallowed_table_sample",
        ),
        (
            "SELECT * FROM information_schema.tables",
            "disallowed_system_catalog",
        ),
        (
            "SELECT * FROM pg_catalog.pg_user",
            "disallowed_system_catalog",
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

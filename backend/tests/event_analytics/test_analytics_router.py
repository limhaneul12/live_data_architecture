import pytest
from app.container import Container
from app.event_analytics.application.analytics_catalog_service import (
    AnalyticsCatalogService,
)
from app.event_analytics.application.explore_query_service import ExploreQueryService
from app.event_analytics.application.query_policy import (
    MAX_QUERY_TEXT_LENGTH,
    AnalyticsSqlPolicy,
)
from app.event_analytics.application.sql_query_service import SqlQueryService
from app.event_analytics.application.view_table_service import ViewTableService
from app.event_analytics.domain.analytics_catalog import (
    AnalyticsDataset,
    AnalyticsDatasetColumn,
    AnalyticsViewTable,
)
from app.event_analytics.domain.explore_query import ExploreColumnRef, ExploreQuery
from app.event_analytics.domain.query_result import AnalyticsRows
from app.event_analytics.domain.repositories.analytics_dataset_repository import (
    AnalyticsDatasetRepository,
)
from app.event_analytics.domain.repositories.analytics_query_repository import (
    AnalyticsQueryRepository,
)
from app.event_analytics.infrastructure.repositories.postgres_analytics_query_repository import (
    AnalyticsQueryExecutionError,
)
from app.event_analytics.interface.router import analytics_router
from fastapi import FastAPI
from fastapi.testclient import TestClient


class FakeAnalyticsQueryRepository(
    AnalyticsQueryRepository, AnalyticsDatasetRepository
):
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.executed_sql: list[str] = []
        self.executed_row_limits: list[int] = []
        self.executed_explore_queries: list[ExploreQuery] = []
        self.created_view_tables: list[tuple[str, str, str]] = []
        self.view_tables: list[AnalyticsViewTable] = []

    async def execute_select(self, sql: str, row_limit: int) -> AnalyticsRows:
        if self.fail:
            raise AnalyticsQueryExecutionError
        self.executed_sql.append(sql)
        self.executed_row_limits.append(row_limit)
        return AnalyticsRows(
            columns=("event_type", "event_count"),
            rows=(
                {"event_type": "page_view", "event_count": 3},
                {"event_type": "purchase", "event_count": 1},
            ),
        )

    async def execute_explore_query(self, query: ExploreQuery) -> AnalyticsRows:
        if self.fail:
            raise AnalyticsQueryExecutionError
        self.executed_explore_queries.append(query)
        return AnalyticsRows(
            columns=("event_type", "event_count"),
            rows=(
                {"event_type": "page_view", "event_count": 3},
                {"event_type": "purchase", "event_count": 1},
            ),
        )

    async def list_view_table_datasets(self) -> tuple[AnalyticsDataset, ...]:
        return tuple(
            AnalyticsDataset(
                name=view_table.name,
                label=view_table.name,
                description=view_table.description,
                columns=view_table.columns,
                origin="view_table",
            )
            for view_table in self.view_tables
        )

    async def list_view_tables(self) -> tuple[AnalyticsViewTable, ...]:
        return tuple(self.view_tables)

    async def create_or_replace_view_table(
        self,
        name: str,
        description: str,
        source_sql: str,
    ) -> AnalyticsViewTable:
        self.created_view_tables.append((name, description, source_sql))
        view_table = AnalyticsViewTable(
            name=name,
            description=description,
            source_sql=source_sql,
            columns=(
                AnalyticsDatasetColumn(
                    name="user_id",
                    label="user_id",
                    kind="dimension",
                ),
                AnalyticsDatasetColumn(
                    name="event_count",
                    label="event_count",
                    kind="metric",
                ),
            ),
        )
        self.view_tables.append(view_table)
        return view_table

    async def preview_view_table_sql(
        self,
        source_sql: str,
        row_limit: int,
    ) -> AnalyticsRows:
        return await self.execute_select(source_sql, row_limit)


def build_client(
    repository: FakeAnalyticsQueryRepository | None = None,
) -> tuple[TestClient, FakeAnalyticsQueryRepository]:
    query_repository = repository or FakeAnalyticsQueryRepository()
    container = Container()
    catalog_service = AnalyticsCatalogService()
    container.event_analytics.analytics_catalog_service.override(catalog_service)
    container.event_analytics.sql_query_service.override(
        SqlQueryService(
            policy=AnalyticsSqlPolicy(),
            repository=query_repository,
            catalog_service=catalog_service,
        )
    )
    container.event_analytics.explore_query_service.override(
        ExploreQueryService(
            repository=query_repository,
            catalog_service=catalog_service,
        )
    )
    container.event_analytics.view_table_service.override(
        ViewTableService(
            repository=query_repository,
            catalog_service=catalog_service,
            policy=AnalyticsSqlPolicy(),
        )
    )
    container.wire(modules=[analytics_router])
    app = FastAPI()
    app.state.container = container
    app.include_router(analytics_router.router)
    return TestClient(app), query_repository


def test_datasets_endpoint_returns_views_only() -> None:
    client, _repository = build_client()

    response = client.get("/analytics/datasets")

    assert response.status_code == 200
    dataset_names = {item["name"] for item in response.json()}
    event_type_dataset = next(
        item for item in response.json() if item["name"] == "event_type_counts"
    )
    assert "events" not in dataset_names
    assert "event_type_counts" in dataset_names
    assert event_type_dataset["columns"] == [
        {"name": "event_type", "label": "Event type", "kind": "dimension"},
        {"name": "event_count", "label": "Event count", "kind": "metric"},
    ]
    assert event_type_dataset["origin"] == "builtin"


def test_connection_endpoints_are_not_registered() -> None:
    client, _repository = build_client()

    assert client.get("/analytics/connection").status_code == 404
    assert client.post("/analytics/connection-test", json={}).status_code == 404


def test_presets_endpoint_returns_safe_sql_presets() -> None:
    client, _repository = build_client()

    response = client.get("/analytics/presets")

    assert response.status_code == 200
    preset_slugs = {item["slug"] for item in response.json()}
    assert {
        "commerce-funnel",
        "event-type-counts",
        "hourly-event-trend",
        "top-users",
        "error-ratio",
    } == preset_slugs


def test_query_endpoint_returns_rows_and_chart_for_valid_select() -> None:
    client, repository = build_client()

    response = client.post(
        "/analytics/query",
        json={"sql": "SELECT event_type, event_count FROM event_type_counts"},
    )

    assert response.status_code == 200
    assert repository.executed_sql == [
        "SELECT event_type, event_count FROM event_type_counts"
    ]
    assert repository.executed_row_limits == [500]
    assert response.json() == {
        "columns": ["event_type", "event_count"],
        "rows": [
            {"event_type": "page_view", "event_count": 3},
            {"event_type": "purchase", "event_count": 1},
        ],
        "chart": {
            "chart_kind": "bar",
            "x_axis": "event_type",
            "y_axis": "event_count",
            "series_axis": None,
        },
    }


def test_query_endpoint_writes_audit_logs_for_valid_select(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, _repository = build_client()

    with caplog.at_level(
        "INFO", logger="app.event_analytics.application.sql_query_service"
    ):
        response = client.post(
            "/analytics/query",
            json={"sql": "SELECT event_type, event_count FROM event_type_counts"},
        )

    assert response.status_code == 200
    assert "analytics SQL accepted sql_sha256=" in caplog.text
    assert "relations=event_type_counts" in caplog.text
    assert "analytics SQL completed sql_sha256=" in caplog.text


def test_explore_query_endpoint_executes_structured_dataset_query() -> None:
    client, repository = build_client()

    response = client.post(
        "/analytics/explore-query",
        json={
            "dataset": "event_type_counts",
            "columns": ["event_type", "event_count"],
            "order_by": "event_count",
            "order_direction": "desc",
            "row_limit": 20,
        },
    )

    assert response.status_code == 200
    assert repository.executed_explore_queries == [
        ExploreQuery(
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
            row_limit=20,
        )
    ]
    assert response.json()["chart"] == {
        "chart_kind": "bar",
        "x_axis": "event_type",
        "y_axis": "event_count",
        "series_axis": None,
    }


def test_explore_query_endpoint_caps_row_limit() -> None:
    client, repository = build_client()

    response = client.post(
        "/analytics/explore-query",
        json={
            "dataset": "event_type_counts",
            "columns": ["event_type", "event_count"],
            "row_limit": 5_000,
        },
    )

    assert response.status_code == 200
    assert repository.executed_explore_queries[0].row_limit == 500


def test_explore_query_endpoint_rejects_unknown_column() -> None:
    client, _repository = build_client()

    response = client.post(
        "/analytics/explore-query",
        json={
            "dataset": "event_type_counts",
            "columns": ["event_type", "pg_sleep"],
            "row_limit": 20,
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "error_code": "explore_query_violation",
        "message": "dataset에 없는 column은 조회할 수 없습니다.",
        "rejected_reason": "unknown_column",
    }


def test_explore_query_endpoint_accepts_join_request() -> None:
    client, repository = build_client()

    response = client.post(
        "/analytics/explore-query",
        json={
            "dataset": "product_event_counts",
            "columns": [
                {"dataset": "product_event_counts", "column": "product_id"},
                {"dataset": "commerce_funnel_counts", "column": "funnel_step"},
                {"dataset": "product_event_counts", "column": "event_count"},
            ],
            "joins": [
                {
                    "dataset": "commerce_funnel_counts",
                    "left_column": "event_type",
                    "right_column": "event_type",
                    "join_type": "inner",
                }
            ],
            "order_by": {
                "dataset": "product_event_counts",
                "column": "event_count",
            },
            "order_direction": "desc",
            "row_limit": 20,
        },
    )

    assert response.status_code == 200
    assert repository.executed_explore_queries[0].joins[0].dataset_name == (
        "commerce_funnel_counts"
    )


def test_view_table_preview_endpoint_allows_events_source_select() -> None:
    client, repository = build_client()

    response = client.post(
        "/analytics/view-tables/preview",
        json={
            "source_sql": (
                "SELECT user_id, COUNT(*) AS event_count FROM events GROUP BY user_id"
            ),
            "row_limit": 20,
        },
    )

    assert response.status_code == 200
    assert repository.executed_sql == [
        "SELECT user_id, COUNT(*) AS event_count FROM events GROUP BY user_id"
    ]
    assert repository.executed_row_limits == [20]


def test_view_table_create_endpoint_saves_dataset() -> None:
    client, repository = build_client()

    response = client.post(
        "/analytics/view-tables",
        json={
            "name": "user_event_type_counts",
            "description": "유저별 이벤트 타입 발생 수",
            "source_sql": (
                "SELECT user_id, event_type, COUNT(*) AS event_count "
                "FROM events GROUP BY user_id, event_type"
            ),
        },
    )

    assert response.status_code == 200
    assert repository.created_view_tables == [
        (
            "user_event_type_counts",
            "유저별 이벤트 타입 발생 수",
            (
                "SELECT user_id, event_type, COUNT(*) AS event_count "
                "FROM events GROUP BY user_id, event_type"
            ),
        )
    ]
    assert response.json()["name"] == "user_event_type_counts"
    assert response.json()["origin"] == "view_table"


def test_query_endpoint_returns_400_for_mutation_sql() -> None:
    client, _repository = build_client()

    response = client.post("/analytics/query", json={"sql": "DROP TABLE events"})

    assert response.status_code == 400
    assert response.json() == {
        "error_code": "sql_policy_violation",
        "message": "analytics SQL은 SELECT 문만 허용합니다.",
        "rejected_reason": "non_select_statement",
    }


def test_query_endpoint_writes_audit_log_for_policy_rejection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, _repository = build_client()

    with caplog.at_level(
        "WARNING",
        logger="app.event_analytics.application.sql_query_service",
    ):
        response = client.post("/analytics/query", json={"sql": "DROP TABLE events"})

    assert response.status_code == 400
    assert "analytics SQL rejected sql_sha256=" in caplog.text
    assert "reason=non_select_statement" in caplog.text


def test_query_endpoint_returns_400_for_raw_events_table() -> None:
    client, _repository = build_client()

    response = client.post("/analytics/query", json={"sql": "SELECT * FROM events"})

    assert response.status_code == 400
    assert response.json()["rejected_reason"] == "unknown_relation"


def test_query_endpoint_returns_400_for_read_only_function_attack() -> None:
    client, _repository = build_client()

    response = client.post(
        "/analytics/query",
        json={"sql": "SELECT pg_sleep(10), event_count FROM event_type_counts"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error_code": "sql_policy_violation",
        "message": "analytics SQL에서는 허용되지 않은 함수입니다: pg_sleep",
        "rejected_reason": "disallowed_function",
    }


def test_query_endpoint_returns_422_for_oversized_sql_text() -> None:
    client, _repository = build_client()

    response = client.post(
        "/analytics/query",
        json={"sql": "x" * (MAX_QUERY_TEXT_LENGTH + 1)},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "string_too_long"
    assert response.json()["detail"][0]["ctx"] == {"max_length": MAX_QUERY_TEXT_LENGTH}


def test_query_endpoint_returns_503_when_database_execution_fails() -> None:
    client, _repository = build_client(
        repository=FakeAnalyticsQueryRepository(True),
    )

    response = client.post(
        "/analytics/query",
        json={"sql": "SELECT event_type FROM event_type_counts"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "analytics_database_unavailable",
        "message": "analytics SQL을 실행할 수 없습니다.",
        "rejected_reason": None,
    }

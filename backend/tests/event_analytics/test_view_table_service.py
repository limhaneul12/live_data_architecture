import asyncio

import pytest
from app.event_analytics.application.analytics_catalog_service import (
    AnalyticsCatalogService,
)
from app.event_analytics.application.query_policy import AnalyticsSqlPolicy
from app.event_analytics.application.view_table_service import ViewTableService
from app.event_analytics.domain.analytics_catalog import (
    AnalyticsDataset,
    AnalyticsDatasetColumn,
    AnalyticsViewTable,
)
from app.event_analytics.domain.query_result import AnalyticsRows
from app.event_analytics.domain.repositories.analytics_dataset_repository import (
    AnalyticsDatasetRepository,
)
from app.shared.exceptions import EventAnalyticsViewTableValidationError


class FakeAnalyticsDatasetRepository(AnalyticsDatasetRepository):
    def __init__(self) -> None:
        self.previewed_sql: list[str] = []
        self.created_view_tables: list[tuple[str, str, str]] = []
        self.view_tables: list[AnalyticsViewTable] = []

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

    async def delete_view_table(self, name: str) -> None:
        self.view_tables = [
            view_table for view_table in self.view_tables if view_table.name != name
        ]

    async def preview_view_table_sql(
        self,
        source_sql: str,
        row_limit: int,
    ) -> AnalyticsRows:
        self.previewed_sql.append(source_sql)
        return AnalyticsRows(
            columns=("user_id", "event_count"),
            rows=({"user_id": "user_001", "event_count": row_limit},),
        )


def build_service(
    repository: FakeAnalyticsDatasetRepository,
) -> ViewTableService:
    catalog_service = AnalyticsCatalogService(repository=repository)
    return ViewTableService(
        repository=repository,
        catalog_service=catalog_service,
        policy=AnalyticsSqlPolicy(),
    )


def test_view_table_preview_allows_events_source() -> None:
    repository = FakeAnalyticsDatasetRepository()
    service = build_service(repository)

    result = asyncio.run(
        service.preview(
            "SELECT user_id, COUNT(*) AS event_count FROM events GROUP BY user_id",
            row_limit=20,
        )
    )

    assert repository.previewed_sql == [
        "SELECT user_id, COUNT(*) AS event_count FROM events GROUP BY user_id"
    ]
    assert result.columns == ("user_id", "event_count")
    assert result.rows == ({"user_id": "user_001", "event_count": 20},)


def test_view_table_create_saves_dataset_shape() -> None:
    repository = FakeAnalyticsDatasetRepository()
    service = build_service(repository)

    dataset = asyncio.run(
        service.create(
            name="user_event_type_counts",
            description="유저별 이벤트 타입 발생 수",
            source_sql=(
                "SELECT user_id, event_type, COUNT(*) AS event_count "
                "FROM events GROUP BY user_id, event_type"
            ),
        ),
    )

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
    assert dataset.name == "user_event_type_counts"
    assert dataset.origin == "view_table"


def test_view_table_create_rejects_builtin_dataset_name() -> None:
    repository = FakeAnalyticsDatasetRepository()
    service = build_service(repository)

    with pytest.raises(EventAnalyticsViewTableValidationError) as exc_info:
        asyncio.run(
            service.create(
                name="event_type_counts",
                description="collision",
                source_sql=(
                    "SELECT event_type, COUNT(*) AS event_count "
                    "FROM events GROUP BY event_type"
                ),
            )
        )

    assert exc_info.value.reason == "reserved_view_table_name"


def test_view_table_delete_removes_saved_dataset() -> None:
    repository = FakeAnalyticsDatasetRepository()
    repository.view_tables.append(
        AnalyticsViewTable(
            name="user_event_type_counts",
            description="유저별 이벤트 타입 발생 수",
            source_sql=(
                "SELECT user_id, event_type, COUNT(*) AS event_count "
                "FROM events GROUP BY user_id, event_type"
            ),
            columns=(),
        )
    )
    service = build_service(repository)

    asyncio.run(service.delete("USER_EVENT_TYPE_COUNTS"))

    assert repository.view_tables == []


def test_view_table_delete_rejects_builtin_dataset_name() -> None:
    repository = FakeAnalyticsDatasetRepository()
    service = build_service(repository)

    with pytest.raises(EventAnalyticsViewTableValidationError) as exc_info:
        asyncio.run(service.delete("event_type_counts"))

    assert exc_info.value.reason == "reserved_view_table_name"

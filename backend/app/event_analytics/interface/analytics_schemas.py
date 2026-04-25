"""Pydantic IO schemas for analytics query endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

from app.event_analytics.constants import (
    MAX_ANALYTICS_CONNECTION_ADDRESS_LENGTH,
    MAX_ANALYTICS_SQL_TEXT_LENGTH,
)
from app.event_analytics.domain.analytics_catalog import (
    AnalyticsDataset,
    AnalyticsDatasetColumn,
    ColumnKind,
    PresetQuery,
)
from app.event_analytics.domain.analytics_connection import (
    AnalyticsConnectionInfo,
    AnalyticsConnectionSource,
    AnalyticsConnectionTestResult,
    AnalyticsDatabaseKind,
)
from app.event_analytics.domain.explore_query import ExploreSortDirection
from app.event_analytics.domain.query_result import (
    AnalyticsQueryResult,
    ChartSuggestion,
)
from app.shared.types import JSONObject
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    StringConstraints,
)

AnalyticsSqlText = Annotated[
    StrictStr,
    StringConstraints(min_length=1, max_length=MAX_ANALYTICS_SQL_TEXT_LENGTH),
]
AnalyticsConnectionAddressText = Annotated[
    StrictStr,
    StringConstraints(min_length=1, max_length=MAX_ANALYTICS_CONNECTION_ADDRESS_LENGTH),
]
ChartKindPayload = Literal["bar", "line", "table", "metric", "pie"]
ColumnKindPayload = ColumnKind
ExploreSortDirectionPayload = ExploreSortDirection
AnalyticsDatabaseKindPayload = AnalyticsDatabaseKind
AnalyticsConnectionSourcePayload = AnalyticsConnectionSource


class AnalyticsPayloadModel(BaseModel):
    """Base configuration for analytics endpoint schemas."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class AnalyticsDatasetColumnPayload(AnalyticsPayloadModel):
    """Column descriptor returned with a generated dataset."""

    name: StrictStr
    label: StrictStr
    kind: ColumnKindPayload

    @classmethod
    def from_domain(
        cls,
        column: AnalyticsDatasetColumn,
    ) -> AnalyticsDatasetColumnPayload:
        """Build an API payload from an internal dataset column.

        Args:
            column: Internal generated-view column descriptor.

        Returns:
            Dataset column payload for API serialization.
        """
        return cls(name=column.name, label=column.label, kind=column.kind)


class AnalyticsDatasetPayload(AnalyticsPayloadModel):
    """Generated dataset descriptor returned to the frontend."""

    name: StrictStr
    label: StrictStr
    description: StrictStr
    columns: tuple[AnalyticsDatasetColumnPayload, ...]

    @classmethod
    def from_domain(cls, dataset: AnalyticsDataset) -> AnalyticsDatasetPayload:
        """Build an API payload from an internal dataset model.

        Args:
            dataset: Internal generated dataset descriptor.

        Returns:
            Dataset payload for API serialization.
        """
        return cls(
            name=dataset.name,
            label=dataset.label,
            description=dataset.description,
            columns=tuple(
                AnalyticsDatasetColumnPayload.from_domain(column)
                for column in dataset.columns
            ),
        )


class PresetQueryPayload(AnalyticsPayloadModel):
    """Preset SQL descriptor returned to the frontend."""

    slug: StrictStr
    label: StrictStr
    description: StrictStr
    sql: StrictStr
    chart_kind: ChartKindPayload

    @classmethod
    def from_domain(cls, preset: PresetQuery) -> PresetQueryPayload:
        """Build an API payload from an internal preset query.

        Args:
            preset: Internal preset query descriptor.

        Returns:
            Preset query payload for API serialization.
        """
        return cls(
            slug=preset.slug,
            label=preset.label,
            description=preset.description,
            sql=preset.sql,
            chart_kind=preset.chart_kind,
        )


class AnalyticsConnectionPayload(AnalyticsPayloadModel):
    """Safe analytics database connection metadata returned to the frontend."""

    database: AnalyticsDatabaseKindPayload
    address: StrictStr
    source: AnalyticsConnectionSourcePayload
    editable: StrictBool
    supported_databases: tuple[AnalyticsDatabaseKindPayload, ...]
    message: StrictStr

    @classmethod
    def from_domain(
        cls,
        connection: AnalyticsConnectionInfo,
    ) -> AnalyticsConnectionPayload:
        """Build an API payload from internal analytics connection metadata.

        Args:
            connection: Internal password-masked connection metadata.

        Returns:
            Analytics connection payload for UI rendering.
        """
        return cls(
            database=connection.database,
            address=connection.address,
            source=connection.source,
            editable=connection.editable,
            supported_databases=connection.supported_databases,
            message=connection.message,
        )


class AnalyticsConnectionTestRequest(AnalyticsPayloadModel):
    """User-submitted database address connectivity check request."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    database: AnalyticsDatabaseKindPayload = "postgresql"
    address: AnalyticsConnectionAddressText


class AnalyticsConnectionTestResponse(AnalyticsPayloadModel):
    """Result of a database address connectivity check."""

    database: AnalyticsDatabaseKindPayload
    address: StrictStr
    reachable: StrictBool
    message: StrictStr

    @classmethod
    def from_domain(
        cls,
        result: AnalyticsConnectionTestResult,
    ) -> AnalyticsConnectionTestResponse:
        """Build an API payload from a connection test result.

        Args:
            result: Internal connection test result.

        Returns:
            Password-masked connectivity check result for UI rendering.
        """
        return cls(
            database=result.database,
            address=result.address,
            reachable=result.reachable,
            message=result.message,
        )


class AnalyticsQueryRequest(AnalyticsPayloadModel):
    """Manual analytics SQL execution request."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    sql: AnalyticsSqlText
    row_limit: StrictInt = Field(default=500, ge=1)


class ExploreQueryRequest(AnalyticsPayloadModel):
    """Structured Explore execution request."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    dataset: StrictStr
    columns: list[StrictStr] = Field(min_length=1)
    order_by: StrictStr | None = None
    order_direction: ExploreSortDirectionPayload = "desc"
    row_limit: StrictInt = Field(default=100, ge=1)


class ChartSuggestionPayload(AnalyticsPayloadModel):
    """Chart suggestion returned with query results."""

    chart_kind: ChartKindPayload
    x_axis: StrictStr | None
    y_axis: StrictStr | None
    series_axis: StrictStr | None

    @classmethod
    def from_domain(cls, chart: ChartSuggestion) -> ChartSuggestionPayload:
        """Build an API payload from an internal chart suggestion.

        Args:
            chart: Internal chart suggestion.

        Returns:
            Chart suggestion payload for API serialization.
        """
        return cls(
            chart_kind=chart.chart_kind,
            x_axis=chart.x_axis,
            y_axis=chart.y_axis,
            series_axis=chart.series_axis,
        )


class AnalyticsQueryResponse(AnalyticsPayloadModel):
    """Successful analytics SQL execution response."""

    columns: tuple[StrictStr, ...]
    rows: tuple[JSONObject, ...]
    chart: ChartSuggestionPayload

    @classmethod
    def from_domain(cls, result: AnalyticsQueryResult) -> AnalyticsQueryResponse:
        """Build an API payload from an internal query result.

        Args:
            result: Internal query result.

        Returns:
            Query response payload for API serialization.
        """
        return cls(
            columns=result.columns,
            rows=result.rows,
            chart=ChartSuggestionPayload.from_domain(result.chart),
        )


class AnalyticsQueryErrorPayload(AnalyticsPayloadModel):
    """Structured analytics query error response."""

    error_code: StrictStr
    message: StrictStr
    rejected_reason: StrictStr | None

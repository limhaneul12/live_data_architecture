"""Pydantic IO schemas for analytics query endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

from app.event_analytics.constants import MAX_ANALYTICS_SQL_TEXT_LENGTH
from app.event_analytics.domain.analytics_catalog import (
    AnalyticsDataset,
    AnalyticsDatasetColumn,
    AnalyticsViewTable,
    ColumnKind,
    DatasetOrigin,
    PresetQuery,
)
from app.event_analytics.domain.explore_query import (
    ExploreColumnRef,
    ExploreJoin,
    ExploreJoinType,
    ExploreSortDirection,
)
from app.event_analytics.domain.query_result import (
    AnalyticsQueryResult,
    ChartSuggestion,
)
from app.shared.exceptions import EventAnalyticsRouteError
from app.shared.types import JSONObject
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    StringConstraints,
)

AnalyticsSqlText = Annotated[
    StrictStr,
    StringConstraints(min_length=1, max_length=MAX_ANALYTICS_SQL_TEXT_LENGTH),
]
ChartKindPayload = Literal["bar", "line", "table", "metric", "pie"]
ColumnKindPayload = ColumnKind
DatasetOriginPayload = DatasetOrigin
ExploreJoinTypePayload = ExploreJoinType
ExploreSortDirectionPayload = ExploreSortDirection


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
    origin: DatasetOriginPayload

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
            origin=dataset.origin,
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


class AnalyticsQueryRequest(AnalyticsPayloadModel):
    """Manual analytics SQL execution request."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    sql: AnalyticsSqlText
    row_limit: StrictInt = Field(default=500, ge=1)


class ExploreColumnRefPayload(AnalyticsPayloadModel):
    """Qualified dataset column selected by Chart Builder."""

    dataset: StrictStr
    column: StrictStr

    def to_domain(self) -> ExploreColumnRef:
        """Convert this IO payload into an internal column reference.

        Args:
            None.

        Returns:
            Internal Explore column reference.
        """
        return ExploreColumnRef(dataset_name=self.dataset, column_name=self.column)


class ExploreJoinPayload(AnalyticsPayloadModel):
    """1-hop JOIN selected by Chart Builder."""

    dataset: StrictStr
    left_column: StrictStr
    right_column: StrictStr
    join_type: ExploreJoinTypePayload = "inner"

    def to_domain(self) -> ExploreJoin:
        """Convert this IO payload into an internal join reference.

        Args:
            None.

        Returns:
            Internal Explore join.
        """
        return ExploreJoin(
            dataset_name=self.dataset,
            left_column=self.left_column,
            right_column=self.right_column,
            join_type=self.join_type,
        )


type ExploreColumnSelectorPayload = StrictStr | ExploreColumnRefPayload


class ExploreQueryRequest(AnalyticsPayloadModel):
    """Structured Explore execution request."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    dataset: StrictStr
    columns: list[ExploreColumnSelectorPayload] = Field(min_length=1)
    joins: list[ExploreJoinPayload] = Field(default_factory=list)
    order_by: ExploreColumnSelectorPayload | None = None
    order_direction: ExploreSortDirectionPayload = "desc"
    row_limit: StrictInt = Field(default=100, ge=1)

    def column_refs(self) -> tuple[ExploreColumnRef, ...]:
        """Return selected columns as internal qualified references.

        Args:
            None.

        Returns:
            Internal Explore column references.
        """
        return tuple(
            column_selector_to_ref(self.dataset, column) for column in self.columns
        )

    def join_refs(self) -> tuple[ExploreJoin, ...]:
        """Return selected joins as internal join references.

        Args:
            None.

        Returns:
            Internal Explore joins.
        """
        return tuple(join.to_domain() for join in self.joins)

    def order_by_ref(self) -> ExploreColumnRef | None:
        """Return the selected ordering column as an internal reference.

        Args:
            None.

        Returns:
            Internal Explore column reference or None.
        """
        if self.order_by is None:
            return None
        return column_selector_to_ref(self.dataset, self.order_by)


class ViewTablePreviewRequest(AnalyticsPayloadModel):
    """Preview request for a user-created analytics view table."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_sql: AnalyticsSqlText
    row_limit: StrictInt = Field(default=50, ge=1)


class ViewTableCreateRequest(AnalyticsPayloadModel):
    """Create-or-replace request for a user-created analytics view table."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: StrictStr
    description: StrictStr = ""
    source_sql: AnalyticsSqlText


class ViewTablePayload(AnalyticsPayloadModel):
    """User-created analytics view table metadata returned to the frontend."""

    name: StrictStr
    description: StrictStr
    source_sql: StrictStr
    columns: tuple[AnalyticsDatasetColumnPayload, ...]

    @classmethod
    def from_domain(cls, view_table: AnalyticsViewTable) -> ViewTablePayload:
        """Build an API payload from an internal view table model.

        Args:
            view_table: Internal user-created view table metadata.

        Returns:
            View table payload for API serialization.
        """
        return cls(
            name=view_table.name,
            description=view_table.description,
            source_sql=view_table.source_sql,
            columns=tuple(
                AnalyticsDatasetColumnPayload.from_domain(column)
                for column in view_table.columns
            ),
        )


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


class AnalyticsErrorPayload(AnalyticsPayloadModel):
    """Structured analytics error response."""

    error_code: StrictStr
    message: StrictStr
    rejected_reason: StrictStr | None

    @classmethod
    def from_exception(cls, error: EventAnalyticsRouteError) -> AnalyticsErrorPayload:
        """Build an API error payload from a route-mapped exception.

        Args:
            error: Event analytics exception with public API error metadata.

        Returns:
            Structured analytics error payload for API serialization.
        """
        return cls(
            error_code=error.error_code,
            message=error.message,
            rejected_reason=error.rejected_reason,
        )


def column_selector_to_ref(
    base_dataset: str,
    selector: ExploreColumnSelectorPayload,
) -> ExploreColumnRef:
    """Convert a legacy or qualified column selector into a domain reference.

    Args:
        base_dataset: Base dataset selected by the Chart Builder request.
        selector: Legacy column name, `dataset.column` selector, or object payload.

    Returns:
        Internal Explore column reference.
    """
    if isinstance(selector, ExploreColumnRefPayload):
        return selector.to_domain()
    if "." not in selector:
        return ExploreColumnRef(dataset_name=base_dataset, column_name=selector)
    dataset_name, column_name = selector.split(".", maxsplit=1)
    return ExploreColumnRef(dataset_name=dataset_name, column_name=column_name)

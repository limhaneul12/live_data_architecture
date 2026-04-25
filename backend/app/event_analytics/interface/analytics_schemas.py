"""Pydantic IO schemas for analytics query endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

from app.event_analytics.constants import MAX_ANALYTICS_SQL_TEXT_LENGTH
from app.event_analytics.domain.analytics_catalog import AnalyticsDataset, PresetQuery
from app.event_analytics.domain.query_result import (
    AnalyticsQueryResult,
    ChartSuggestion,
)
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
ChartKindPayload = Literal["bar", "line", "table", "metric"]


class AnalyticsPayloadModel(BaseModel):
    """Base configuration for analytics endpoint schemas."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class AnalyticsDatasetPayload(AnalyticsPayloadModel):
    """Generated dataset descriptor returned to the frontend."""

    name: StrictStr
    label: StrictStr
    description: StrictStr

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

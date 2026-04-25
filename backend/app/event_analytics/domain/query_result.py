"""Internal analytics query result read models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.shared.types import JSONObject

ChartKind = Literal["bar", "line", "table", "metric", "pie"]


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalyticsRows:
    """Raw row set returned by a validated analytics SQL query."""

    columns: tuple[str, ...]
    rows: tuple[JSONObject, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ChartSuggestion:
    """Chart shape inferred from a SQL result set."""

    chart_kind: ChartKind
    x_axis: str | None
    y_axis: str | None
    series_axis: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalyticsQueryResult:
    """Column/row result returned by a safe analytics SQL query."""

    columns: tuple[str, ...]
    rows: tuple[JSONObject, ...]
    chart: ChartSuggestion

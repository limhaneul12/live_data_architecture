"""Internal read models for analytics datasets and preset SQL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ChartKind = Literal["bar", "line", "table", "metric", "pie"]
ColumnKind = Literal["dimension", "metric", "temporal"]


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalyticsDatasetColumn:
    """Column exposed by an allowlisted generated analytics view."""

    name: str
    label: str
    kind: ColumnKind


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalyticsDataset:
    """Allowlisted generated view exposed to the SQL UI."""

    name: str
    label: str
    description: str
    columns: tuple[AnalyticsDatasetColumn, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class PresetQuery:
    """Safe preset SQL query shown by the analytics UI."""

    slug: str
    label: str
    description: str
    sql: str
    chart_kind: ChartKind

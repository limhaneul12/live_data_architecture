"""Internal read models for analytics datasets and preset SQL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ChartKind = Literal["bar", "line", "table", "metric"]


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalyticsDataset:
    """Allowlisted generated view exposed to the SQL UI."""

    name: str
    label: str
    description: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PresetQuery:
    """Safe preset SQL query shown by the analytics UI."""

    slug: str
    label: str
    description: str
    sql: str
    chart_kind: ChartKind

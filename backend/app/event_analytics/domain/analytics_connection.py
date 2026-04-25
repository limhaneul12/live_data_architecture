"""Internal analytics database connection metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AnalyticsDatabaseKind = Literal["postgresql"]
AnalyticsConnectionSource = Literal["analytics_read_only_dsn", "writer_fallback_dsn"]


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalyticsConnectionInfo:
    """Safe metadata describing the configured analytics database connection."""

    database: AnalyticsDatabaseKind
    address: str
    source: AnalyticsConnectionSource
    editable: bool
    supported_databases: tuple[AnalyticsDatabaseKind, ...]
    message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalyticsConnectionTestResult:
    """Result of a user-submitted analytics database connectivity check."""

    database: AnalyticsDatabaseKind
    address: str
    reachable: bool
    message: str

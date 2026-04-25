"""Internal structured query model for Superset-style Explore requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ExploreSortDirection = Literal["asc", "desc"]


@dataclass(frozen=True, slots=True, kw_only=True)
class ExploreQuery:
    """Validated structured query for one generated analytics dataset."""

    dataset_name: str
    column_names: tuple[str, ...]
    order_by: str | None
    order_direction: ExploreSortDirection
    row_limit: int

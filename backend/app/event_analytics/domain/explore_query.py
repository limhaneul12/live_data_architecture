"""Internal structured query model for Superset-style Explore requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ExploreSortDirection = Literal["asc", "desc"]
ExploreJoinType = Literal["inner", "left"]


@dataclass(frozen=True, slots=True, kw_only=True)
class ExploreColumnRef:
    """Column reference selected from one Explore dataset."""

    dataset_name: str
    column_name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExploreJoin:
    """Validated 1-hop join from the base dataset to another dataset."""

    dataset_name: str
    left_column: str
    right_column: str
    join_type: ExploreJoinType


@dataclass(frozen=True, slots=True, kw_only=True)
class ExploreQuery:
    """Validated structured query for one generated analytics dataset."""

    dataset_name: str
    column_refs: tuple[ExploreColumnRef, ...]
    joins: tuple[ExploreJoin, ...]
    order_by: ExploreColumnRef | None
    order_direction: ExploreSortDirection
    row_limit: int

    @property
    def column_names(self) -> tuple[str, ...]:
        """Return legacy unqualified column names for single-dataset queries.

        Args:
            None.

        Returns:
            Selected column names without dataset qualification.
        """
        return tuple(column_ref.column_name for column_ref in self.column_refs)

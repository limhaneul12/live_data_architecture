"""Chart suggestion policy for analytics SQL results."""

from __future__ import annotations

from app.event_analytics.domain.query_result import AnalyticsRows, ChartSuggestion
from app.shared.types import JSONValue

_TIME_COLUMN_HINTS = ("hour", "time", "date", "occurred")


def suggest_chart(rows: AnalyticsRows) -> ChartSuggestion:
    """Infer a small chart shape from returned SQL columns and values.

    Args:
        rows: SQL result columns and JSON-safe row values.

    Returns:
        Chart suggestion for the frontend preview panel.
    """
    if not rows.columns:
        return ChartSuggestion(
            chart_kind="table",
            x_axis=None,
            y_axis=None,
            series_axis=None,
        )

    numeric_columns = _numeric_columns(rows)
    if len(rows.columns) == 1 or len(numeric_columns) == len(rows.columns):
        return ChartSuggestion(
            chart_kind="metric",
            x_axis=None,
            y_axis=numeric_columns[0] if numeric_columns else rows.columns[0],
            series_axis=None,
        )
    if not numeric_columns:
        return ChartSuggestion(
            chart_kind="table",
            x_axis=None,
            y_axis=None,
            series_axis=None,
        )

    x_axis = _first_non_numeric_column(
        columns=rows.columns, numeric_columns=numeric_columns
    )
    y_axis = numeric_columns[0]
    series_axis = _series_axis(
        columns=rows.columns,
        x_axis=x_axis,
        y_axis=y_axis,
    )
    chart_kind = "line" if _looks_temporal(x_axis) else "bar"
    return ChartSuggestion(
        chart_kind=chart_kind,
        x_axis=x_axis,
        y_axis=y_axis,
        series_axis=series_axis,
    )


def _numeric_columns(rows: AnalyticsRows) -> tuple[str, ...]:
    """Find columns whose returned values are all numeric.

    Args:
        rows: SQL result columns and rows.

    Returns:
        Column names that can be used as numeric measures.
    """
    return tuple(
        column
        for column in rows.columns
        if rows.rows and all(_is_numeric(row.get(column)) for row in rows.rows)
    )


def _is_numeric(value: JSONValue) -> bool:
    """Check whether a JSON value is a chartable number.

    Args:
        value: JSON-safe value from a query row.

    Returns:
        True when the value is int/float but not bool.
    """
    return isinstance(value, int | float) and not isinstance(value, bool)


def _first_non_numeric_column(
    *,
    columns: tuple[str, ...],
    numeric_columns: tuple[str, ...],
) -> str:
    """Find the first dimension column.

    Args:
        columns: Result column names.
        numeric_columns: Columns already classified as numeric.

    Returns:
        First non-numeric column, or the first column as a fallback.
    """
    numeric_set = set(numeric_columns)
    for column in columns:
        if column not in numeric_set:
            return column
    return columns[0]


def _series_axis(
    *,
    columns: tuple[str, ...],
    x_axis: str,
    y_axis: str,
) -> str | None:
    """Find an optional series/grouping column for grouped charts.

    Args:
        columns: Result column names.
        x_axis: Chosen x-axis column.
        y_axis: Chosen y-axis column.

    Returns:
        Optional series column name.
    """
    for column in columns:
        if column not in {x_axis, y_axis}:
            return column
    return None


def _looks_temporal(column: str) -> bool:
    """Detect whether a column name likely represents time.

    Args:
        column: Result column name.

    Returns:
        True when the column name has a time-like hint.
    """
    lowered = column.lower()
    return any(hint in lowered for hint in _TIME_COLUMN_HINTS)

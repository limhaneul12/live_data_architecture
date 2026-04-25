"""Server-side policy for manual analytics SQL execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

import sqlglot
from app.event_analytics.application.analytics_catalog import ALLOWED_DATASET_NAMES
from app.event_analytics.constants import MAX_ANALYTICS_SQL_TEXT_LENGTH
from sqlglot import exp
from sqlglot.errors import ParseError

MAX_QUERY_ROW_LIMIT = 500
MAX_QUERY_TEXT_LENGTH: Final = MAX_ANALYTICS_SQL_TEXT_LENGTH

SqlPolicyRejectionReason = Literal[
    "query_too_long",
    "parse_error",
    "multiple_statements",
    "non_select_statement",
    "unsafe_cte",
    "disallowed_cte",
    "disallowed_subquery",
    "disallowed_join",
    "disallowed_function",
    "disallowed_select_into",
    "disallowed_locking_read",
    "disallowed_offset",
    "disallowed_distinct",
    "disallowed_table_sample",
    "disallowed_grouping",
    "disallowed_ordinal_order",
    "cross_schema_relation",
    "unknown_relation",
    "missing_relation",
]

_MUTATING_EXPRESSIONS = (
    exp.Alter,
    exp.Command,
    exp.Create,
    exp.Delete,
    exp.Drop,
    exp.Insert,
    exp.Merge,
    exp.TruncateTable,
    exp.Update,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidatedSqlQuery:
    """SQL query accepted by the analytics policy."""

    sql: str
    referenced_relations: frozenset[str]
    row_limit: int


class SqlPolicyViolationError(Exception):
    """Raised when manual SQL violates the analytics safety policy."""

    def __init__(self, reason: SqlPolicyRejectionReason, message: str) -> None:
        """Initialize a SQL policy violation.

        Args:
            reason: Stable machine-readable rejection reason.
            message: Human-readable rejection detail.

        Returns:
            None.
        """
        super().__init__(message)
        self.reason = reason
        self.message = message


class AnalyticsSqlPolicy:
    """Validate manual SQL against the generated-dataset allowlist."""

    def __init__(
        self,
        *,
        allowed_relations: frozenset[str] = ALLOWED_DATASET_NAMES,
        max_row_limit: int = MAX_QUERY_ROW_LIMIT,
    ) -> None:
        """Initialize the SQL policy.

        Args:
            allowed_relations: Generated view names accepted in manual SQL.
            max_row_limit: Maximum rows returned by any accepted query.

        Returns:
            None.
        """
        self._allowed_relations = allowed_relations
        self._max_row_limit = max_row_limit

    def validate(self, sql: str, requested_row_limit: int) -> ValidatedSqlQuery:
        """Validate SQL and return its normalized execution contract.

        Args:
            sql: Manual SQL submitted by a user or preset.
            requested_row_limit: User-requested maximum row count.

        Returns:
            Validated query with capped row limit and referenced relation set.
        """
        _ensure_query_length(sql)
        expressions = _parse_one_statement(sql)
        expression = expressions[0]
        _ensure_select_only(expression)
        _ensure_bounded_select_shape(expression)
        referenced_relations = _extract_referenced_relations(expression)
        _ensure_relations_are_allowlisted(
            referenced_relations=referenced_relations,
            allowed_relations=self._allowed_relations,
        )
        return ValidatedSqlQuery(
            sql=expression.sql(dialect="postgres"),
            referenced_relations=frozenset(referenced_relations),
            row_limit=min(requested_row_limit, self._max_row_limit),
        )


def _ensure_query_length(sql: str) -> None:
    """Reject oversized SQL before parser work begins.

    Args:
        sql: Manual SQL text.

    Returns:
        None.
    """
    if len(sql) > MAX_QUERY_TEXT_LENGTH:
        raise SqlPolicyViolationError(
            reason="query_too_long",
            message=f"analytics SQL은 {MAX_QUERY_TEXT_LENGTH}자 이하만 허용합니다.",
        )


def _parse_one_statement(sql: str) -> list[exp.Expression]:
    """Parse SQL and require exactly one statement.

    Args:
        sql: Manual SQL text.

    Returns:
        Parsed sqlglot expression list containing one expression.
    """
    try:
        expressions = sqlglot.parse(sql, read="postgres")
    except ParseError as exc:
        raise SqlPolicyViolationError(
            reason="parse_error",
            message="SQL을 PostgreSQL SELECT 문으로 해석할 수 없습니다.",
        ) from exc

    parsed_expressions = [expression for expression in expressions if expression]
    if len(parsed_expressions) != 1:
        raise SqlPolicyViolationError(
            reason="multiple_statements",
            message="SQL은 한 번에 하나의 SELECT 문만 실행할 수 있습니다.",
        )
    return parsed_expressions


def _ensure_select_only(expression: exp.Expression) -> None:
    """Reject non-SELECT roots and data-changing child expressions.

    Args:
        expression: Parsed SQL expression.

    Returns:
        None.
    """
    if not isinstance(expression, exp.Select):
        raise SqlPolicyViolationError(
            reason="non_select_statement",
            message="analytics SQL은 SELECT 문만 허용합니다.",
        )
    if any(expression.find_all(*_MUTATING_EXPRESSIONS)):
        raise SqlPolicyViolationError(
            reason="unsafe_cte",
            message="SELECT 내부에서도 데이터 변경 구문은 허용하지 않습니다.",
        )


def _ensure_bounded_select_shape(expression: exp.Expression) -> None:
    """Reject read-only SQL shapes that can bypass the simple analytics boundary.

    Args:
        expression: Parsed SELECT expression.

    Returns:
        None.
    """
    if any(expression.find_all(exp.CTE)):
        raise SqlPolicyViolationError(
            reason="disallowed_cte",
            message="analytics SQL에서는 CTE를 허용하지 않습니다.",
        )

    if any(expression.find_all(exp.Subquery, exp.Lateral)):
        raise SqlPolicyViolationError(
            reason="disallowed_subquery",
            message="analytics SQL에서는 subquery/lateral query를 허용하지 않습니다.",
        )

    nested_selects = (
        nested_select
        for nested_select in expression.find_all(exp.Select)
        if nested_select is not expression
    )
    if any(nested_selects):
        raise SqlPolicyViolationError(
            reason="disallowed_subquery",
            message="analytics SQL에서는 subquery/lateral query를 허용하지 않습니다.",
        )

    if any(expression.find_all(exp.Join)):
        raise SqlPolicyViolationError(
            reason="disallowed_join",
            message="analytics SQL에서는 join을 허용하지 않습니다.",
        )

    if any(expression.find_all(exp.Into)):
        raise SqlPolicyViolationError(
            reason="disallowed_select_into",
            message="analytics SQL에서는 SELECT INTO를 허용하지 않습니다.",
        )

    if any(expression.find_all(exp.Lock)):
        raise SqlPolicyViolationError(
            reason="disallowed_locking_read",
            message="analytics SQL에서는 locking read를 허용하지 않습니다.",
        )

    if any(expression.find_all(exp.Offset)):
        raise SqlPolicyViolationError(
            reason="disallowed_offset",
            message="analytics SQL에서는 OFFSET을 허용하지 않습니다.",
        )

    if any(expression.find_all(exp.Distinct)):
        raise SqlPolicyViolationError(
            reason="disallowed_distinct",
            message="analytics SQL에서는 DISTINCT를 허용하지 않습니다.",
        )

    if any(expression.find_all(exp.TableSample)):
        raise SqlPolicyViolationError(
            reason="disallowed_table_sample",
            message="analytics SQL에서는 TABLESAMPLE을 허용하지 않습니다.",
        )

    if any(expression.find_all(exp.Group)):
        raise SqlPolicyViolationError(
            reason="disallowed_grouping",
            message="analytics SQL에서는 GROUP BY를 허용하지 않습니다.",
        )

    for ordered in expression.find_all(exp.Ordered):
        if isinstance(ordered.this, exp.Literal):
            raise SqlPolicyViolationError(
                reason="disallowed_ordinal_order",
                message="analytics SQL에서는 ordinal ORDER BY를 허용하지 않습니다.",
            )

    if any(expression.find_all(exp.Func)):
        raise SqlPolicyViolationError(
            reason="disallowed_function",
            message="analytics SQL에서는 함수 호출을 허용하지 않습니다.",
        )


def _extract_referenced_relations(expression: exp.Expression) -> set[str]:
    """Extract physical table/view references from a parsed SELECT.

    Args:
        expression: Parsed SQL expression.

    Returns:
        Lowercase relation names referenced by the query, excluding CTE aliases.
    """
    cte_names = {
        cte.alias_or_name.lower()
        for cte in expression.find_all(exp.CTE)
        if cte.alias_or_name
    }
    referenced_relations: set[str] = set()
    for table in expression.find_all(exp.Table):
        relation_name = table.name.lower()
        if relation_name in cte_names:
            continue
        if table.db or table.catalog:
            raise SqlPolicyViolationError(
                reason="cross_schema_relation",
                message="schema/catalog qualified relation은 허용하지 않습니다.",
            )
        referenced_relations.add(relation_name)
    return referenced_relations


def _ensure_relations_are_allowlisted(
    *,
    referenced_relations: set[str],
    allowed_relations: frozenset[str],
) -> None:
    """Verify referenced relations are present and allowlisted.

    Args:
        referenced_relations: Physical relation names found in the query.
        allowed_relations: Generated view names allowed by policy.

    Returns:
        None.
    """
    if not referenced_relations:
        raise SqlPolicyViolationError(
            reason="missing_relation",
            message="allowlist에 등록된 generated view를 하나 이상 조회해야 합니다.",
        )

    unknown_relations = referenced_relations - allowed_relations
    if unknown_relations:
        unknown_list = ", ".join(sorted(unknown_relations))
        raise SqlPolicyViolationError(
            reason="unknown_relation",
            message=f"허용되지 않은 relation입니다: {unknown_list}",
        )

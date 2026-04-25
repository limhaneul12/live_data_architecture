"""FastAPI router for event analytics datasets, presets, and SQL queries."""

from __future__ import annotations

from app.event_analytics.application.analytics_catalog import (
    get_datasets,
    get_preset_queries,
)
from app.event_analytics.application.explore_query_service import (
    ExploreQueryService,
    ExploreQueryValidationError,
)
from app.event_analytics.application.query_policy import SqlPolicyViolationError
from app.event_analytics.application.sql_query_service import SqlQueryService
from app.event_analytics.domain.analytics_connection import AnalyticsConnectionInfo
from app.event_analytics.infrastructure.repositories.postgres_analytics_query_repository import (
    AnalyticsQueryExecutionError,
)
from app.event_analytics.interface.analytics_schemas import (
    AnalyticsConnectionPayload,
    AnalyticsDatasetPayload,
    AnalyticsQueryErrorPayload,
    AnalyticsQueryRequest,
    AnalyticsQueryResponse,
    ExploreQueryRequest,
    PresetQueryPayload,
)
from fastapi import APIRouter, FastAPI, status
from fastapi.responses import JSONResponse


def install_analytics_routes(
    app: FastAPI,
    query_service: SqlQueryService,
    explore_query_service: ExploreQueryService,
    connection_info: AnalyticsConnectionInfo,
) -> None:
    """Install analytics API routes into the FastAPI application.

    Args:
        app: FastAPI application that owns the routes.
        query_service: Application service for validated analytics SQL execution.
        explore_query_service: Application service for structured Explore queries.
        connection_info: Password-masked analytics database connection metadata.

    Returns:
        None.
    """
    router = APIRouter(prefix="/analytics", tags=["analytics"])

    @router.get("/connection")
    def get_connection() -> AnalyticsConnectionPayload:
        """Return the configured analytics database connection metadata.

        Args:
            None.

        Returns:
            Password-masked database connection metadata for UI display.
        """
        return AnalyticsConnectionPayload.from_domain(connection_info)

    @router.get("/datasets")
    def list_datasets() -> tuple[AnalyticsDatasetPayload, ...]:
        """Return generated datasets that manual SQL may reference.

        Args:
            None.

        Returns:
            Allowlisted generated dataset descriptors.
        """
        return tuple(
            AnalyticsDatasetPayload.from_domain(dataset) for dataset in get_datasets()
        )

    @router.get("/presets")
    def list_presets() -> tuple[PresetQueryPayload, ...]:
        """Return safe preset SQL queries for the frontend.

        Args:
            None.

        Returns:
            Preset SQL descriptors.
        """
        return tuple(
            PresetQueryPayload.from_domain(preset) for preset in get_preset_queries()
        )

    @router.post("/query", response_model=None)
    async def run_query(
        request: AnalyticsQueryRequest,
    ) -> AnalyticsQueryResponse | JSONResponse:
        """Execute one validated analytics SQL query.

        Args:
            request: Manual SQL request payload.

        Returns:
            Query result payload, policy rejection, or database-unavailable error.
        """
        try:
            result = await query_service.execute(
                sql=request.sql,
                row_limit=request.row_limit,
            )
        except SqlPolicyViolationError as exc:
            return _query_error_response(
                status.HTTP_400_BAD_REQUEST,
                payload=AnalyticsQueryErrorPayload(
                    error_code="sql_policy_violation",
                    message=exc.message,
                    rejected_reason=exc.reason,
                ),
            )
        except AnalyticsQueryExecutionError:
            return _query_error_response(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                payload=AnalyticsQueryErrorPayload(
                    error_code="analytics_database_unavailable",
                    message="analytics SQL을 실행할 수 없습니다.",
                    rejected_reason=None,
                ),
            )
        return AnalyticsQueryResponse.from_domain(result)

    @router.post("/explore-query", response_model=None)
    async def run_explore_query(
        request: ExploreQueryRequest,
    ) -> AnalyticsQueryResponse | JSONResponse:
        """Execute one structured Explore query.

        Args:
            request: Dataset/columns/order controls selected by the frontend.

        Returns:
            Query result payload, validation rejection, or database error.
        """
        try:
            result = await explore_query_service.execute(
                dataset_name=request.dataset,
                column_names=tuple(request.columns),
                order_by=request.order_by,
                order_direction=request.order_direction,
                row_limit=request.row_limit,
            )
        except ExploreQueryValidationError as exc:
            return _query_error_response(
                status.HTTP_400_BAD_REQUEST,
                payload=AnalyticsQueryErrorPayload(
                    error_code="explore_query_violation",
                    message=exc.message,
                    rejected_reason=exc.reason,
                ),
            )
        except AnalyticsQueryExecutionError:
            return _query_error_response(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                payload=AnalyticsQueryErrorPayload(
                    error_code="analytics_database_unavailable",
                    message="analytics Explore query를 실행할 수 없습니다.",
                    rejected_reason=None,
                ),
            )
        return AnalyticsQueryResponse.from_domain(result)

    app.include_router(router)


def _query_error_response(
    status_code: int,
    payload: AnalyticsQueryErrorPayload,
) -> JSONResponse:
    """Build a structured analytics query error response.

    Args:
        status_code: HTTP status code for the error.
        payload: Structured query error payload.

    Returns:
        JSON response containing the error payload.
    """
    return JSONResponse(status_code=status_code, content=payload.model_dump())

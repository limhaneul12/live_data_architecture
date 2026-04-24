"""FastAPI router for event analytics datasets, presets, and SQL queries."""

from __future__ import annotations

from app.event_analytics.application.analytics_catalog import (
    get_datasets,
    get_preset_queries,
)
from app.event_analytics.application.query_policy import SqlPolicyViolationError
from app.event_analytics.application.sql_query_service import SqlQueryService
from app.event_analytics.infrastructure.repositories.postgres_analytics_query_repository import (
    AnalyticsQueryExecutionError,
)
from app.event_analytics.interface.analytics_schemas import (
    AnalyticsDatasetPayload,
    AnalyticsQueryErrorPayload,
    AnalyticsQueryRequest,
    AnalyticsQueryResponse,
    PresetQueryPayload,
)
from fastapi import APIRouter, FastAPI, status
from fastapi.responses import JSONResponse


def install_analytics_routes(app: FastAPI, *, query_service: SqlQueryService) -> None:
    """Install analytics API routes into the FastAPI application.

    Args:
        app: FastAPI application that owns the routes.
        query_service: Application service for validated analytics SQL execution.

    Returns:
        None.
    """
    router = APIRouter(prefix="/analytics", tags=["analytics"])

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
                status_code=status.HTTP_400_BAD_REQUEST,
                payload=AnalyticsQueryErrorPayload(
                    error_code="sql_policy_violation",
                    message=exc.message,
                    rejected_reason=exc.reason,
                ),
            )
        except AnalyticsQueryExecutionError:
            return _query_error_response(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                payload=AnalyticsQueryErrorPayload(
                    error_code="analytics_database_unavailable",
                    message="analytics SQL을 실행할 수 없습니다.",
                    rejected_reason=None,
                ),
            )
        return AnalyticsQueryResponse.from_domain(result)

    app.include_router(router)


def _query_error_response(
    *,
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

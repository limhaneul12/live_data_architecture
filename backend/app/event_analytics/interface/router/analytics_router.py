"""FastAPI router for event analytics datasets, presets, and SQL queries."""

from __future__ import annotations

from typing import Any

from app.container import Container
from app.event_analytics.application.analytics_catalog import get_preset_queries
from app.event_analytics.application.analytics_catalog_service import (
    AnalyticsCatalogService,
)
from app.event_analytics.application.explore_query_service import (
    ExploreQueryService,
)
from app.event_analytics.application.sql_query_service import SqlQueryService
from app.event_analytics.application.view_table_service import ViewTableService
from app.event_analytics.interface.schemas import (
    AnalyticsDatasetPayload,
    AnalyticsErrorPayload,
    AnalyticsQueryRequest,
    AnalyticsQueryResponse,
    ExploreQueryRequest,
    PresetQueryPayload,
    ViewTableCreateRequest,
    ViewTablePayload,
    ViewTablePreviewRequest,
)
from app.shared.exceptions import (
    EventAnalyticsRouteError,
    map_event_analytics_route_errors,
)
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

# Broad type justified: FastAPI's `responses` parameter is typed as dict[str, Any].
SQL_QUERY_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {
        "model": AnalyticsErrorPayload,
        "description": "SQL Lab query was rejected by the server-side SQL policy.",
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "model": AnalyticsErrorPayload,
        "description": "Analytics database is unavailable for SQL Lab execution.",
    },
}
# Broad type justified: FastAPI's `responses` parameter is typed as dict[str, Any].
EXPLORE_QUERY_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {
        "model": AnalyticsErrorPayload,
        "description": "Structured Explore query failed dataset or column validation.",
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "model": AnalyticsErrorPayload,
        "description": "Analytics database is unavailable for Explore execution.",
    },
}
# Broad type justified: FastAPI's `responses` parameter is typed as dict[str, Any].
VIEW_TABLE_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {
        "model": AnalyticsErrorPayload,
        "description": "View table SQL or metadata failed validation.",
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "model": AnalyticsErrorPayload,
        "description": "Analytics database is unavailable for view table requests.",
    },
}

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
)


def analytics_error_payload(error: EventAnalyticsRouteError) -> dict[str, str | None]:
    """Serialize one event analytics route exception with the API error schema.

    Args:
        error: Event analytics exception with public API error metadata.

    Returns:
        JSON-ready analytics error payload.
    """
    return AnalyticsErrorPayload.from_exception(error).model_dump()


@router.get(
    "/datasets",
    response_model=tuple[AnalyticsDatasetPayload, ...],
    status_code=status.HTTP_200_OK,
    summary="List generated analytics datasets",
    description=(
        "Returns the allowlisted generated views that Chart Builder and SQL Lab "
        "may query."
    ),
)
@map_event_analytics_route_errors(analytics_error_payload)
@inject
async def list_datasets(
    service: AnalyticsCatalogService = Depends(
        Provide[Container.event_analytics.analytics_catalog_service],
    ),
) -> tuple[AnalyticsDatasetPayload, ...] | JSONResponse:
    """Return generated datasets that manual SQL may reference.

    Args:
        service: Dataset catalog service resolved by FastAPI DI.

    Returns:
        Allowlisted generated dataset descriptors.
    """
    return tuple(
        AnalyticsDatasetPayload.from_domain(dataset)
        for dataset in await service.list_datasets()
    )


@router.get(
    "/presets",
    response_model=tuple[PresetQueryPayload, ...],
    status_code=status.HTTP_200_OK,
    summary="List preset analytics SQL queries",
    description="Returns safe preset SELECT queries for frontend examples.",
)
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


@router.post(
    "/query",
    response_model=AnalyticsQueryResponse,
    status_code=status.HTTP_200_OK,
    responses=SQL_QUERY_ERROR_RESPONSES,
    summary="Run SQL Lab query",
    description=(
        "Executes a server-validated read-only SQL Lab query against generated "
        "analytics views."
    ),
)
@map_event_analytics_route_errors(analytics_error_payload)
@inject
async def run_query(
    request: AnalyticsQueryRequest,
    service: SqlQueryService = Depends(
        Provide[Container.event_analytics.sql_query_service],
    ),
) -> AnalyticsQueryResponse | JSONResponse:
    """Execute one validated analytics SQL query.

    Args:
        request: Manual SQL request payload.
        service: SQL Lab application service resolved by FastAPI DI.

    Returns:
        Query result payload, policy rejection, or database-unavailable error.
    """
    result = await service.execute(
        sql=request.sql,
        row_limit=request.row_limit,
    )
    return AnalyticsQueryResponse.from_domain(result)


@router.post(
    "/explore-query",
    response_model=AnalyticsQueryResponse,
    status_code=status.HTTP_200_OK,
    responses=EXPLORE_QUERY_ERROR_RESPONSES,
    summary="Run structured Explore query",
    description=(
        "Executes a structured Chart Builder query generated by backend "
        "allowlisted datasets and columns."
    ),
)
@map_event_analytics_route_errors(analytics_error_payload)
@inject
async def run_explore_query(
    request: ExploreQueryRequest,
    service: ExploreQueryService = Depends(
        Provide[Container.event_analytics.explore_query_service],
    ),
) -> AnalyticsQueryResponse | JSONResponse:
    """Execute one structured Explore query.

    Args:
        request: Dataset/columns/order controls selected by the frontend.
        service: Structured Explore service resolved by FastAPI DI.

    Returns:
        Query result payload, validation rejection, or database error.
    """
    result = await service.execute(
        dataset_name=request.dataset,
        column_refs=request.column_refs(),
        joins=request.join_refs(),
        order_by=request.order_by_ref(),
        order_direction=request.order_direction,
        row_limit=request.row_limit,
    )
    return AnalyticsQueryResponse.from_domain(result)


@router.get(
    "/view-tables",
    response_model=tuple[ViewTablePayload, ...],
    status_code=status.HTTP_200_OK,
    responses=VIEW_TABLE_ERROR_RESPONSES,
    summary="List user-created analytics view tables",
    description="Returns user-created view tables saved as chartable datasets.",
)
@map_event_analytics_route_errors(analytics_error_payload)
@inject
async def list_view_tables(
    service: AnalyticsCatalogService = Depends(
        Provide[Container.event_analytics.analytics_catalog_service],
    ),
) -> tuple[ViewTablePayload, ...] | JSONResponse:
    """Return user-created analytics view tables.

    Args:
        service: Dataset catalog service resolved by FastAPI DI.

    Returns:
        User-created view table metadata.
    """
    return tuple(
        ViewTablePayload.from_domain(view_table)
        for view_table in await service.list_view_tables()
    )


@router.post(
    "/view-tables/preview",
    response_model=AnalyticsQueryResponse,
    status_code=status.HTTP_200_OK,
    responses=VIEW_TABLE_ERROR_RESPONSES,
    summary="Preview a view table source query",
    description=(
        "Validates a SELECT intended for a user-created view table and returns "
        "a small preview result."
    ),
)
@map_event_analytics_route_errors(analytics_error_payload)
@inject
async def preview_view_table(
    request: ViewTablePreviewRequest,
    service: ViewTableService = Depends(
        Provide[Container.event_analytics.view_table_service],
    ),
) -> AnalyticsQueryResponse | JSONResponse:
    """Preview one user-created view table SELECT.

    Args:
        request: View table preview payload.
        service: View table service resolved by FastAPI DI.

    Returns:
        Preview query result or structured validation error.
    """
    result = await service.preview(
        source_sql=request.source_sql,
        row_limit=request.row_limit,
    )
    return AnalyticsQueryResponse.from_domain(result)


@router.post(
    "/view-tables",
    response_model=AnalyticsDatasetPayload,
    status_code=status.HTTP_200_OK,
    responses=VIEW_TABLE_ERROR_RESPONSES,
    summary="Save a user-created analytics view table",
    description=(
        "Creates or replaces a PostgreSQL view from a validated SELECT and "
        "saves it as a Chart Builder dataset."
    ),
)
@map_event_analytics_route_errors(analytics_error_payload)
@inject
async def create_view_table(
    request: ViewTableCreateRequest,
    service: ViewTableService = Depends(
        Provide[Container.event_analytics.view_table_service],
    ),
) -> AnalyticsDatasetPayload | JSONResponse:
    """Create or replace one analytics view table.

    Args:
        request: View table create-or-replace payload.
        service: View table service resolved by FastAPI DI.

    Returns:
        Dataset descriptor for the saved view table or structured error.
    """
    dataset = await service.create(
        name=request.name,
        description=request.description,
        source_sql=request.source_sql,
    )
    return AnalyticsDatasetPayload.from_domain(dataset)

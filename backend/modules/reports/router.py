"""Reports & Analytics API router.

Phase 0 mounted this router empty. Phase 1 (T045) added only the Saved
Report View **persistence** endpoints (list/create/update/delete). Phase
3 adds discovery, the unified ``GET /{report_key}`` execution endpoint,
and saved-view ``load()`` — every route dispatches only through
``ReportExecutionService``/``SavedViewService``/``registry_service``,
never ``ADAPTER_REGISTRY`` directly (T129). Phase 6 adds
``GET /{report_key}/export``, which dispatches only through
``ReportExportService`` (T212).
"""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth.dependencies import require_authenticated, require_user_id
from core.auth.interfaces import CurrentUser
from core.database.session import get_db
from core.logging.setup import REQUEST_ID_CONTEXT
from core.schemas.pagination import PaginatedData, PaginatedResponse
from core.schemas.response import ResponseMeta, StandardResponse
from core.utils.datetime import utcnow
from core.utils.pagination import calculate_pages
from modules.companies.repositories.company_repository import CompanyRepository
from modules.reports.dependencies import get_saved_report_view_repo
from modules.reports.exceptions import (
    FilterValidationError,
    ReportPermissionDeniedError,
)
from modules.reports.registry.definitions import ExportFormat
from modules.reports.repositories.saved_report_view import SavedReportViewRepository
from modules.reports.schemas.common import (
    ComparisonRequest,
    ComparisonType,
    PeriodPreset,
)
from modules.reports.schemas.customer_360 import Customer360Response
from modules.reports.schemas.dashboard import ExecutiveDashboardResponse
from modules.reports.schemas.discovery import (
    ReportDiscoveryItem,
    ReportDiscoveryResponse,
)
from modules.reports.schemas.envelope import (
    ReportCursorResponse,
    ReportPaginatedResponse,
    ReportStandardResponse,
)
from modules.reports.schemas.pagination import CursorPage
from modules.reports.schemas.saved_view import (
    SavedReportViewCreate,
    SavedReportViewRead,
    SavedReportViewUpdate,
)
from modules.reports.services import registry_service, saved_view_service
from modules.reports.services.adapters.base import (
    AggregateReportResult,
    CursorReportResult,
    PaginatedReportResult,
)
from modules.reports.services.customer_360_service import get_customer_360
from modules.reports.services.dashboard_service import get_dashboard
from modules.reports.services.date_range_service import resolve_period
from modules.reports.services.execution_service import ReportExecutionService
from modules.reports.services.export_service import ReportExportService
from modules.reports.services.permission_check import user_has_reports_permission

router = APIRouter(tags=["reports"])

_SAVED_VIEW_MANAGE_PERMISSION = "reports.saved_view.manage"
_DASHBOARD_PERMISSION = "reports.executive.view"
_execution_service = ReportExecutionService()
_export_service = ReportExportService(execution_service=_execution_service)
_DEEP_OBJECT_FILTER_KEY = re.compile(r"^filters\[(?P<field>[^\]]+)\]$")


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow())


def _parse_deep_object_filters(request: Request) -> dict[str, str]:
    """Parses OpenAPI ``style: deepObject`` query params
    (``filters[field]=value``) into a flat dict, per
    ``contracts/reports-api.yaml``'s documented ``GET /{report_key}``
    contract. Query param values are always strings at this stage —
    ``definition.supported_filters(**raw_filters)`` (step 4,
    ``_authorize_and_validate``) is what actually coerces each one to
    its declared type."""
    raw_filters: dict[str, str] = {}
    for key, value in request.query_params.multi_items():
        match = _DEEP_OBJECT_FILTER_KEY.match(key)
        if match:
            raw_filters[match.group("field")] = value
    return raw_filters


def _parse_comparison(report_key: str, compare: str | None) -> ComparisonRequest | None:
    if compare is None:
        return None
    try:
        return ComparisonRequest(comparison_type=ComparisonType(compare))
    except ValueError as exc:
        raise FilterValidationError(
            report_key, f"invalid compare value: {compare}"
        ) from exc


def _require_saved_view_permission(
    db: Session, company_id: UUID, current_user: CurrentUser
) -> None:
    if not user_has_reports_permission(
        db,
        company_id,
        require_user_id(current_user),
        _SAVED_VIEW_MANAGE_PERMISSION,
        user_roles=current_user.roles,
    ):
        raise ReportPermissionDeniedError(_SAVED_VIEW_MANAGE_PERMISSION)


@router.get(
    "/saved-views",
    response_model=PaginatedResponse[SavedReportViewRead],
    summary="List the caller's own saved report views",
)
async def list_saved_views(
    company_id: UUID = Path(..., description="Company identifier"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    repo: SavedReportViewRepository = Depends(get_saved_report_view_repo),
) -> PaginatedResponse[SavedReportViewRead]:
    _require_saved_view_permission(db, company_id, current_user)
    items, total = saved_view_service.list_views(
        repo,
        company_id=company_id,
        user_id=require_user_id(current_user),
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    return PaginatedResponse(
        data=PaginatedData(
            items=[SavedReportViewRead.model_validate(v) for v in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=calculate_pages(total, page_size),
        ),
        message=f"{total} saved view(s) found.",
        meta=_meta(),
    )


@router.post(
    "/saved-views",
    response_model=StandardResponse[SavedReportViewRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a private saved report view",
)
async def create_saved_view(
    body: SavedReportViewCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    repo: SavedReportViewRepository = Depends(get_saved_report_view_repo),
) -> StandardResponse[SavedReportViewRead]:
    _require_saved_view_permission(db, company_id, current_user)
    view = saved_view_service.save(
        repo, company_id=company_id, user_id=require_user_id(current_user), payload=body
    )
    return StandardResponse(
        data=SavedReportViewRead.model_validate(view),
        message="Saved report view created.",
        meta=_meta(),
    )


@router.get(
    "/saved-views/{view_id}",
    response_model=StandardResponse[SavedReportViewRead],
    summary="Load a saved report view — re-validated against current state",
)
async def load_saved_view(
    view_id: UUID = Path(..., description="Saved report view identifier"),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    repo: SavedReportViewRepository = Depends(get_saved_report_view_repo),
) -> StandardResponse[SavedReportViewRead]:
    _require_saved_view_permission(db, company_id, current_user)
    view = saved_view_service.load(
        db,
        repo,
        _execution_service,
        view_id=view_id,
        company_id=company_id,
        user_id=require_user_id(current_user),
        user_roles=current_user.roles,
    )
    return StandardResponse(
        data=SavedReportViewRead.model_validate(view),
        message="Saved report view loaded.",
        meta=_meta(),
    )


@router.patch(
    "/saved-views/{view_id}",
    response_model=StandardResponse[SavedReportViewRead],
    summary="Update a private saved report view",
)
async def update_saved_view(
    body: SavedReportViewUpdate,
    view_id: UUID = Path(..., description="Saved report view identifier"),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    repo: SavedReportViewRepository = Depends(get_saved_report_view_repo),
) -> StandardResponse[SavedReportViewRead]:
    _require_saved_view_permission(db, company_id, current_user)
    view = saved_view_service.update(
        repo,
        view_id=view_id,
        company_id=company_id,
        user_id=require_user_id(current_user),
        payload=body,
    )
    return StandardResponse(
        data=SavedReportViewRead.model_validate(view),
        message="Saved report view updated.",
        meta=_meta(),
    )


@router.delete(
    "/saved-views/{view_id}",
    response_model=StandardResponse[None],
    summary="Delete (soft-delete) a private saved report view",
)
async def delete_saved_view(
    view_id: UUID = Path(..., description="Saved report view identifier"),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    repo: SavedReportViewRepository = Depends(get_saved_report_view_repo),
) -> StandardResponse[None]:
    _require_saved_view_permission(db, company_id, current_user)
    saved_view_service.delete(
        repo,
        view_id=view_id,
        company_id=company_id,
        user_id=require_user_id(current_user),
    )
    return StandardResponse(
        data=None,
        message="Saved report view deleted.",
        meta=_meta(),
    )


@router.get(
    "/discovery",
    response_model=StandardResponse[ReportDiscoveryResponse],
    summary="List Report Definitions the current user may currently reach",
)
async def discover_reports(
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
) -> StandardResponse[ReportDiscoveryResponse]:
    definitions = registry_service.list_discoverable_reports(
        db, company_id, require_user_id(current_user)
    )
    return StandardResponse(
        data=ReportDiscoveryResponse(
            reports=[ReportDiscoveryItem.from_definition(d) for d in definitions]
        ),
        message=f"{len(definitions)} report(s) discoverable.",
        meta=_meta(),
    )


@router.get(
    "/customer-360/{customer_id}",
    response_model=StandardResponse[Customer360Response],
    summary="Customer 360 — one customer's Sales/AR/CRM/Installments exposure",
)
async def get_customer_360_route(
    customer_id: UUID = Path(..., description="Sales customer identifier"),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
) -> StandardResponse[Customer360Response]:
    data = get_customer_360(
        db,
        company_id=company_id,
        user_id=require_user_id(current_user),
        customer_id=customer_id,
        user_roles=current_user.roles,
    )
    return StandardResponse(
        data=data,
        message="Customer 360 view rendered.",
        meta=_meta(),
    )


@router.get(
    "/dashboard",
    response_model=StandardResponse[ExecutiveDashboardResponse],
    summary="Executive Dashboard — curated cross-module KPI overview",
)
async def get_dashboard_route(
    company_id: UUID = Path(..., description="Company identifier"),
    period: PeriodPreset = Query(PeriodPreset.THIS_MONTH),
    custom_start: str | None = Query(None),
    custom_end: str | None = Query(None),
    compare: str | None = Query(None),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
) -> StandardResponse[ExecutiveDashboardResponse]:
    user_id = require_user_id(current_user)
    if not user_has_reports_permission(
        db, company_id, user_id, _DASHBOARD_PERMISSION, user_roles=current_user.roles
    ):
        raise ReportPermissionDeniedError(_DASHBOARD_PERMISSION)

    company = CompanyRepository(db).get_by_id(company_id)
    timezone = company.default_timezone if company is not None else None
    resolved_period = resolve_period(
        period, timezone, custom_start=custom_start, custom_end=custom_end
    )
    comparison = _parse_comparison("exec.dashboard", compare)

    data = get_dashboard(
        db,
        company_id=company_id,
        user_id=user_id,
        period=resolved_period,
        comparison=comparison,
        user_roles=current_user.roles,
    )
    return StandardResponse(
        data=data,
        message="Executive dashboard rendered.",
        meta=_meta(),
    )


@router.get(
    "/{report_key}/export",
    summary="Export a report in the exact filter scope of its online view",
    response_class=Response,
    responses={
        200: {
            "description": "File download (Content-Disposition: attachment)",
            "content": {
                "text/csv": {},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
                "application/pdf": {},
            },
        }
    },
)
async def export_report(
    request: Request,
    report_key: str = Path(..., description="Stable report key"),
    company_id: UUID = Path(..., description="Company identifier"),
    export_format: ExportFormat = Query(..., alias="format"),
    sort: str | None = Query(None),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
) -> Response:
    """The file bytes reach this handler only after
    ``ReportExportService`` has durably committed the export's audit row
    (§21.8) — any failure before that point surfaces as a typed error
    envelope, never a partial file."""
    result = _export_service.export(
        db,
        company_id=company_id,
        user_id=require_user_id(current_user),
        report_key=report_key,
        raw_filters=_parse_deep_object_filters(request),
        sort=sort,
        export_format=export_format,
        user_roles=current_user.roles,
    )
    return Response(
        content=result.content,
        media_type=result.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/{report_key}",
    summary='Execute any registered "Now" report by its stable key',
)
async def execute_report(
    request: Request,
    report_key: str = Path(..., description="Stable report key"),
    company_id: UUID = Path(..., description="Company identifier"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str | None = Query(None),
    compare: str | None = Query(None),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
) -> (
    ReportStandardResponse[BaseModel]
    | ReportPaginatedResponse[BaseModel]
    | ReportCursorResponse[BaseModel]
):
    raw_filters = _parse_deep_object_filters(request)
    comparison = _parse_comparison(report_key, compare)
    result = _execution_service.execute(
        db,
        company_id=company_id,
        user_id=require_user_id(current_user),
        report_key=report_key,
        raw_filters=raw_filters,
        page=page,
        page_size=page_size,
        sort=sort,
        comparison=comparison,
        user_roles=current_user.roles,
    )
    if isinstance(result, PaginatedReportResult):
        return ReportPaginatedResponse[BaseModel](
            data=PaginatedData[BaseModel](
                items=result.items,
                total=result.total,
                page=page,
                page_size=page_size,
                pages=calculate_pages(result.total, page_size),
            ),
            report_meta=result.meta,
            message=f"Report '{report_key}' executed.",
            meta=_meta(),
        )
    if isinstance(result, CursorReportResult):
        return ReportCursorResponse[BaseModel](
            data=CursorPage[BaseModel](
                items=result.items,
                has_more=result.has_more,
                next_cursor=result.next_cursor,
            ),
            report_meta=result.meta,
            message=f"Report '{report_key}' executed.",
            meta=_meta(),
        )
    assert isinstance(result, AggregateReportResult)
    return ReportStandardResponse[BaseModel](
        data=result.data,
        report_meta=result.meta,
        message=f"Report '{report_key}' executed.",
        meta=_meta(),
    )

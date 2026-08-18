"""CRM module API router — Phase 3 (Lead + LeadSource) + Phase 4 (convert)
+ Phase 5 (Pipeline/Stage + Opportunity) + Phase 6 (Activity) + Phase 7
(Customer 360) + Phase 8 (RBAC).

Not yet mounted into ``api/v1/router.py`` — that happens in Phase 9
(tasks.md T079), alongside the ``require_crm_enabled`` feature-flag gate.
Every endpoint here now enforces its documented ``crm.*`` permission
(spec.md §38's per-endpoint table) inline via ``user_has_crm_permission()``,
in addition to ``require_authenticated`` (base auth) — RBAC enforcement
completed in Phase 8 (tasks.md T065), closing out the TODOs left by every
earlier phase.

Endpoints:
    GET    /crm/lead-sources           — list lead sources
    POST   /crm/lead-sources           — create a lead source
    PATCH  /crm/lead-sources/{id}      — update a lead source

    POST   /crm/leads                  — capture a Lead
    GET    /crm/leads                  — list/filter Leads (paginated)
    GET    /crm/leads/{id}             — get a Lead
    PATCH  /crm/leads/{id}             — update a Lead (incl. qualify/
                                          disqualify via the status field)
    DELETE /crm/leads/{id}             — soft-delete a Lead
    POST   /crm/leads/{id}/assign      — reassign a Lead's owner
    POST   /crm/leads/{id}/convert     — convert a QUALIFIED Lead (Phase 4)

    GET    /crm/pipelines                        — list Pipelines
    POST   /crm/pipelines                         — create a Pipeline
    PATCH  /crm/pipelines/{id}                    — update a Pipeline
    GET    /crm/pipelines/{id}/stages             — list a Pipeline's stages
    POST   /crm/pipelines/{id}/stages             — create a Stage
    PATCH  /crm/pipeline-stages/{id}              — update a Stage (BR-007)

    POST   /crm/opportunities                     — create an Opportunity
    GET    /crm/opportunities                     — list/filter (paginated)
    GET    /crm/opportunities/{id}                — get an Opportunity
    PATCH  /crm/opportunities/{id}                — update metadata (BR-003)
    DELETE /crm/opportunities/{id}                — soft-delete (OPEN only)
    POST   /crm/opportunities/{id}/assign         — reassign owner
    POST   /crm/opportunities/{id}/stage          — change stage (INV-004)
    POST   /crm/opportunities/{id}/win            — mark WON
    POST   /crm/opportunities/{id}/lose           — mark LOST (BR-004)

    POST   /crm/activities                        — log an Activity
    GET    /crm/activities                        — list/filter (paginated)
    GET    /crm/activities/{id}                   — get an Activity
    PATCH  /crm/activities/{id}                   — update an Activity
    DELETE /crm/activities/{id}                   — soft-delete an Activity
    POST   /crm/activities/{id}/complete          — complete (Lead-cascade)

    GET    /crm/customers/{customer_id}/360       — Customer 360 (Phase 7)

    GET    /crm/dashboard                         — dashboard KPIs (Phase 9)
    GET    /crm/reports/pipeline                  — pipeline report (Phase 9)
    GET    /crm/reports/leads                     — lead report (Phase 9)
    GET    /crm/reports/activities                — activity report (Phase 9)

Spec ref: specs/009-crm/spec.md §38.1-38.6, §40, §41; plan.md §21.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from core.auth.dependencies import require_authenticated
from core.auth.interfaces import CurrentUser
from core.database.session import get_db
from core.logging.setup import REQUEST_ID_CONTEXT
from core.schemas.pagination import PaginatedData, PaginatedResponse
from core.schemas.response import ResponseMeta, StandardResponse
from core.utils.datetime import utcnow
from modules.companies.dependencies import require_admin_or_above
from modules.companies.models.company import Company
from modules.crm.constants import ALL_CRM_PERMISSION_CODES
from modules.crm.dependencies import (
    get_activity_service,
    get_crm_feature_flag_service,
    get_crm_reporting_service,
    get_customer_360_service,
    get_lead_conversion_service,
    get_lead_service,
    get_lead_source_service,
    get_opportunity_service,
    get_pipeline_service,
)
from modules.crm.exceptions import CrmPermissionDeniedError
from modules.crm.schemas.activity import ActivityCreate, ActivityRead, ActivityUpdate
from modules.crm.schemas.base import CrmMyPermissions, CrmStatusRead
from modules.crm.schemas.customer_360 import (
    Customer360,
    CustomerSummary,
    FinancialSummary,
    SalesHistorySummary,
)
from modules.crm.schemas.lead import (
    ConversionResult,
    LeadAssignRequest,
    LeadCreate,
    LeadRead,
    LeadSourceCreate,
    LeadSourceRead,
    LeadSourceUpdate,
    LeadUpdate,
)
from modules.crm.schemas.opportunity import (
    OpportunityAssignRequest,
    OpportunityCreate,
    OpportunityLoseRequest,
    OpportunityRead,
    OpportunityStageChangeRequest,
    OpportunityUpdate,
)
from modules.crm.schemas.pipeline import (
    PipelineCreate,
    PipelineRead,
    PipelineStageCreate,
    PipelineStageRead,
    PipelineStageUpdate,
    PipelineUpdate,
)
from modules.crm.schemas.reports import (
    ActivityReport,
    CrmDashboard,
    LeadReport,
    PipelineReport,
)
from modules.crm.services.activity_service import ActivityService
from modules.crm.services.customer_360_service import Customer360Service
from modules.crm.services.feature_flag_service import CrmFeatureFlagService
from modules.crm.services.lead_conversion_service import LeadConversionService
from modules.crm.services.lead_service import LeadService
from modules.crm.services.lead_source_service import LeadSourceService
from modules.crm.services.opportunity_service import OpportunityService
from modules.crm.services.permission_check import user_has_crm_permission
from modules.crm.services.pipeline_service import PipelineService
from modules.crm.services.reporting_service import CrmReportingService
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)
from modules.users_roles.repositories.role_permission_repository import (
    RolePermissionRepository,
)

router = APIRouter(tags=["crm"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow())


# ---------------------------------------------------------------------------
# Current user's CRM permissions — lets the frontend hide (not just
# disable) actions the user can't perform, rather than showing every
# action to everyone and only revealing a 403 after the fact.
# ---------------------------------------------------------------------------


@router.get(
    "/my-permissions",
    response_model=StandardResponse[CrmMyPermissions],
    summary="The current user's granted crm.* permission codes in this company",
)
async def get_my_crm_permissions(
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
) -> StandardResponse[CrmMyPermissions]:
    if current_user.roles and "super_admin" in current_user.roles:
        permissions = sorted(ALL_CRM_PERMISSION_CODES)
    elif current_user.user_id is None:
        permissions = []
    else:
        member = CompanyMemberRepository(db).get_by_user_id(
            user_id=current_user.user_id, company_id=company_id
        )
        if member is None or member.status != "active":
            permissions = []
        else:
            role_permissions = RolePermissionRepository(db).get_permissions_for_role(
                member.role_id
            )
            permissions = sorted(
                rp.permission_id
                for rp in role_permissions
                if rp.permission_id.startswith("crm.")
            )
    return StandardResponse(
        data=CrmMyPermissions(permissions=permissions),
        message="Current user's CRM permissions retrieved.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Lead Sources (spec.md §38.2)
# ---------------------------------------------------------------------------


@router.get(
    "/lead-sources",
    response_model=PaginatedResponse[LeadSourceRead],
    summary="List lead sources",
)
async def list_lead_sources(
    company_id: UUID = Path(..., description="Company identifier"),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: LeadSourceService = Depends(get_lead_source_service),
) -> PaginatedResponse[LeadSourceRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.leads.view"
    ):
        raise CrmPermissionDeniedError("crm.leads.view")
    items = svc.list(company_id, is_active=is_active)
    total = len(items)
    page_items = items[(page - 1) * page_size : (page - 1) * page_size + page_size]
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        data=PaginatedData(
            items=[LeadSourceRead.model_validate(s) for s in page_items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        ),
        message=f"{total} lead source(s) found.",
        meta=_meta(),
    )


@router.post(
    "/lead-sources",
    response_model=StandardResponse[LeadSourceRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a lead source",
)
async def create_lead_source(
    body: LeadSourceCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: LeadSourceService = Depends(get_lead_source_service),
) -> StandardResponse[LeadSourceRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.pipeline.manage"
    ):
        raise CrmPermissionDeniedError("crm.pipeline.manage")
    source = svc.create(
        company_id,
        code=body.code,
        name=body.name,
        is_active=body.is_active,
        created_by=current_user.user_id,
    )
    return StandardResponse(
        data=LeadSourceRead.model_validate(source),
        message="Lead source created.",
        meta=_meta(),
    )


@router.patch(
    "/lead-sources/{source_id}",
    response_model=StandardResponse[LeadSourceRead],
    summary="Update a lead source",
)
async def update_lead_source(
    body: LeadSourceUpdate,
    source_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: LeadSourceService = Depends(get_lead_source_service),
) -> StandardResponse[LeadSourceRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.pipeline.manage"
    ):
        raise CrmPermissionDeniedError("crm.pipeline.manage")
    source = svc.update(
        source_id,
        company_id,
        **body.model_dump(exclude_unset=True),
    )
    return StandardResponse(
        data=LeadSourceRead.model_validate(source),
        message="Lead source updated.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Leads (spec.md §38.1)
# ---------------------------------------------------------------------------


@router.post(
    "/leads",
    response_model=StandardResponse[LeadRead],
    status_code=status.HTTP_201_CREATED,
    summary="Capture a new Lead",
)
async def create_lead(
    body: LeadCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: LeadService = Depends(get_lead_service),
) -> StandardResponse[LeadRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.leads.create"
    ):
        raise CrmPermissionDeniedError("crm.leads.create")
    lead = svc.create(company_id, body, created_by=current_user.user_id)
    return StandardResponse(
        data=LeadRead.model_validate(lead),
        message="Lead created.",
        meta=_meta(),
    )


@router.get(
    "/leads",
    response_model=PaginatedResponse[LeadRead],
    summary="List / filter Leads",
)
async def list_leads(
    company_id: UUID = Path(..., description="Company identifier"),
    status_filter: str | None = Query(None, alias="status"),
    source_id: UUID | None = Query(None),
    owner_id: UUID | None = Query(None),
    created_from: str | None = Query(None, description="ISO datetime, inclusive"),
    created_to: str | None = Query(None, description="ISO datetime, inclusive"),
    search: str | None = Query(
        None, description="Matches name, company name, email, or phone"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: LeadService = Depends(get_lead_service),
) -> PaginatedResponse[LeadRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.leads.view"
    ):
        raise CrmPermissionDeniedError("crm.leads.view")
    items, total = svc.list_filtered(
        company_id,
        status=status_filter,
        source_id=source_id,
        owner_id=owner_id,
        created_from=datetime.fromisoformat(created_from) if created_from else None,
        created_to=datetime.fromisoformat(created_to) if created_to else None,
        search=search,
        page=page,
        page_size=page_size,
    )
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        data=PaginatedData(
            items=[LeadRead.model_validate(lead) for lead in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        ),
        message=f"{total} lead(s) found.",
        meta=_meta(),
    )


@router.get(
    "/leads/{lead_id}",
    response_model=StandardResponse[LeadRead],
    summary="Get a Lead",
)
async def get_lead(
    lead_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: LeadService = Depends(get_lead_service),
) -> StandardResponse[LeadRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.leads.view"
    ):
        raise CrmPermissionDeniedError("crm.leads.view")
    lead = svc.get(lead_id, company_id)
    return StandardResponse(
        data=LeadRead.model_validate(lead),
        message="Lead retrieved.",
        meta=_meta(),
    )


@router.patch(
    "/leads/{lead_id}",
    response_model=StandardResponse[LeadRead],
    summary="Update a Lead (including qualify/disqualify via status)",
)
async def update_lead(
    body: LeadUpdate,
    lead_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: LeadService = Depends(get_lead_service),
) -> StandardResponse[LeadRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.leads.update"
    ):
        raise CrmPermissionDeniedError("crm.leads.update")
    lead = svc.update(
        lead_id, company_id, body, actor_user_id=cast(UUID, current_user.user_id)
    )
    return StandardResponse(
        data=LeadRead.model_validate(lead),
        message="Lead updated.",
        meta=_meta(),
    )


@router.delete(
    "/leads/{lead_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a Lead",
)
async def delete_lead(
    lead_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: LeadService = Depends(get_lead_service),
) -> None:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.leads.delete"
    ):
        raise CrmPermissionDeniedError("crm.leads.delete")
    svc.soft_delete(lead_id, company_id)


@router.post(
    "/leads/{lead_id}/assign",
    response_model=StandardResponse[LeadRead],
    summary="Reassign a Lead's owner",
)
async def assign_lead(
    body: LeadAssignRequest,
    lead_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: LeadService = Depends(get_lead_service),
) -> StandardResponse[LeadRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.leads.assign"
    ):
        raise CrmPermissionDeniedError("crm.leads.assign")
    lead = svc.assign(
        lead_id,
        company_id,
        body.owner_id,
        actor_user_id=cast(UUID, current_user.user_id),
    )
    return StandardResponse(
        data=LeadRead.model_validate(lead),
        message="Lead reassigned.",
        meta=_meta(),
    )


@router.post(
    "/leads/{lead_id}/convert",
    response_model=StandardResponse[ConversionResult],
    summary="Convert a QUALIFIED Lead into a Customer + Opportunity",
)
async def convert_lead(
    lead_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: LeadConversionService = Depends(get_lead_conversion_service),
) -> StandardResponse[ConversionResult]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.leads.convert"
    ):
        raise CrmPermissionDeniedError("crm.leads.convert")
    # 200, not 201 — idempotent by design (spec.md §16.3): a repeat call
    # against an already-CONVERTED Lead returns the existing result, not a
    # newly "created" one.
    result = svc.convert(lead_id, company_id, cast(UUID, current_user.user_id))
    return StandardResponse(
        data=ConversionResult(
            lead_id=result.lead_id,
            customer_id=result.customer_id,
            opportunity_id=result.opportunity_id,
            customer_matched=result.customer_matched,
        ),
        message="Lead converted.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Pipelines & Stages (spec.md §38.3)
# ---------------------------------------------------------------------------


@router.get(
    "/pipelines",
    response_model=StandardResponse[list[PipelineRead]],
    summary="List pipelines",
)
async def list_pipelines(
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PipelineService = Depends(get_pipeline_service),
) -> StandardResponse[list[PipelineRead]]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.pipeline.view"
    ):
        raise CrmPermissionDeniedError("crm.pipeline.view")
    pipelines = svc.list_pipelines(company_id)
    return StandardResponse(
        data=[PipelineRead.model_validate(p) for p in pipelines],
        message=f"{len(pipelines)} pipeline(s) found.",
        meta=_meta(),
    )


@router.post(
    "/pipelines",
    response_model=StandardResponse[PipelineRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a pipeline",
)
async def create_pipeline(
    body: PipelineCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PipelineService = Depends(get_pipeline_service),
) -> StandardResponse[PipelineRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.pipeline.manage"
    ):
        raise CrmPermissionDeniedError("crm.pipeline.manage")
    pipeline = svc.create_pipeline(
        company_id,
        name=body.name,
        is_default=body.is_default,
        is_active=body.is_active,
        created_by=cast(UUID, current_user.user_id),
    )
    return StandardResponse(
        data=PipelineRead.model_validate(pipeline),
        message="Pipeline created.",
        meta=_meta(),
    )


@router.patch(
    "/pipelines/{pipeline_id}",
    response_model=StandardResponse[PipelineRead],
    summary="Update a pipeline",
)
async def update_pipeline(
    body: PipelineUpdate,
    pipeline_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PipelineService = Depends(get_pipeline_service),
) -> StandardResponse[PipelineRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.pipeline.manage"
    ):
        raise CrmPermissionDeniedError("crm.pipeline.manage")
    pipeline = svc.update_pipeline(
        pipeline_id, company_id, **body.model_dump(exclude_unset=True)
    )
    return StandardResponse(
        data=PipelineRead.model_validate(pipeline),
        message="Pipeline updated.",
        meta=_meta(),
    )


@router.get(
    "/pipelines/{pipeline_id}/stages",
    response_model=StandardResponse[list[PipelineStageRead]],
    summary="List a pipeline's stages",
)
async def list_pipeline_stages(
    pipeline_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PipelineService = Depends(get_pipeline_service),
) -> StandardResponse[list[PipelineStageRead]]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.pipeline.view"
    ):
        raise CrmPermissionDeniedError("crm.pipeline.view")
    stages = svc.list_stages(pipeline_id, company_id)
    return StandardResponse(
        data=[PipelineStageRead.model_validate(s) for s in stages],
        message=f"{len(stages)} stage(s) found.",
        meta=_meta(),
    )


@router.post(
    "/pipelines/{pipeline_id}/stages",
    response_model=StandardResponse[PipelineStageRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a pipeline stage",
)
async def create_pipeline_stage(
    body: PipelineStageCreate,
    pipeline_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PipelineService = Depends(get_pipeline_service),
) -> StandardResponse[PipelineStageRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.pipeline.manage"
    ):
        raise CrmPermissionDeniedError("crm.pipeline.manage")
    stage = svc.create_stage(
        pipeline_id,
        company_id,
        name=body.name,
        sequence=body.sequence,
        probability=body.probability,
        is_won_stage=body.is_won_stage,
        is_lost_stage=body.is_lost_stage,
        is_active=body.is_active,
        created_by=cast(UUID, current_user.user_id),
    )
    return StandardResponse(
        data=PipelineStageRead.model_validate(stage),
        message="Pipeline stage created.",
        meta=_meta(),
    )


@router.patch(
    "/pipeline-stages/{stage_id}",
    response_model=StandardResponse[PipelineStageRead],
    summary="Update a pipeline stage",
)
async def update_pipeline_stage(
    body: PipelineStageUpdate,
    stage_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PipelineService = Depends(get_pipeline_service),
) -> StandardResponse[PipelineStageRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.pipeline.manage"
    ):
        raise CrmPermissionDeniedError("crm.pipeline.manage")
    # BR-007 (stage deactivation blocked while an OPEN Opportunity occupies
    # it) is enforced inside the service and surfaces as a 409.
    stage = svc.update_stage(
        stage_id, company_id, **body.model_dump(exclude_unset=True)
    )
    return StandardResponse(
        data=PipelineStageRead.model_validate(stage),
        message="Pipeline stage updated.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Opportunities (spec.md §38.4)
# ---------------------------------------------------------------------------


@router.post(
    "/opportunities",
    response_model=StandardResponse[OpportunityRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create an Opportunity directly against an existing Customer",
)
async def create_opportunity(
    body: OpportunityCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: OpportunityService = Depends(get_opportunity_service),
) -> StandardResponse[OpportunityRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.opportunities.create"
    ):
        raise CrmPermissionDeniedError("crm.opportunities.create")
    opportunity = svc.create(
        company_id, body, created_by=cast(UUID, current_user.user_id)
    )
    return StandardResponse(
        data=OpportunityRead.model_validate(opportunity),
        message="Opportunity created.",
        meta=_meta(),
    )


@router.get(
    "/opportunities",
    response_model=PaginatedResponse[OpportunityRead],
    summary="List / filter Opportunities",
)
async def list_opportunities(
    company_id: UUID = Path(..., description="Company identifier"),
    status_filter: str | None = Query(None, alias="status"),
    stage_id: UUID | None = Query(None),
    owner_id: UUID | None = Query(None),
    customer_id: UUID | None = Query(None),
    expected_close_from: date | None = Query(None),
    expected_close_to: date | None = Query(None),
    min_value: Decimal | None = Query(None),
    max_value: Decimal | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: OpportunityService = Depends(get_opportunity_service),
) -> PaginatedResponse[OpportunityRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.opportunities.view"
    ):
        raise CrmPermissionDeniedError("crm.opportunities.view")
    items, total = svc.list_filtered(
        company_id,
        status=status_filter,
        stage_id=stage_id,
        owner_id=owner_id,
        customer_id=customer_id,
        expected_close_from=expected_close_from,
        expected_close_to=expected_close_to,
        min_value=min_value,
        max_value=max_value,
        page=page,
        page_size=page_size,
    )
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        data=PaginatedData(
            items=[OpportunityRead.model_validate(o) for o in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        ),
        message=f"{total} opportunity(ies) found.",
        meta=_meta(),
    )


@router.get(
    "/opportunities/{opportunity_id}",
    response_model=StandardResponse[OpportunityRead],
    summary="Get an Opportunity",
)
async def get_opportunity(
    opportunity_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: OpportunityService = Depends(get_opportunity_service),
) -> StandardResponse[OpportunityRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.opportunities.view"
    ):
        raise CrmPermissionDeniedError("crm.opportunities.view")
    opportunity = svc.get(opportunity_id, company_id)
    return StandardResponse(
        data=OpportunityRead.model_validate(opportunity),
        message="Opportunity retrieved.",
        meta=_meta(),
    )


@router.patch(
    "/opportunities/{opportunity_id}",
    response_model=StandardResponse[OpportunityRead],
    summary="Update an Opportunity's metadata",
)
async def update_opportunity(
    body: OpportunityUpdate,
    opportunity_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: OpportunityService = Depends(get_opportunity_service),
) -> StandardResponse[OpportunityRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.opportunities.update"
    ):
        raise CrmPermissionDeniedError("crm.opportunities.update")
    # BR-003 (no edits once WON/LOST) is enforced inside the service (409).
    opportunity = svc.update(opportunity_id, company_id, body)
    return StandardResponse(
        data=OpportunityRead.model_validate(opportunity),
        message="Opportunity updated.",
        meta=_meta(),
    )


@router.delete(
    "/opportunities/{opportunity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete an Opportunity (only while OPEN)",
)
async def delete_opportunity(
    opportunity_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: OpportunityService = Depends(get_opportunity_service),
) -> None:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.opportunities.delete"
    ):
        raise CrmPermissionDeniedError("crm.opportunities.delete")
    svc.soft_delete(opportunity_id, company_id)


@router.post(
    "/opportunities/{opportunity_id}/assign",
    response_model=StandardResponse[OpportunityRead],
    summary="Reassign an Opportunity's owner",
)
async def assign_opportunity(
    body: OpportunityAssignRequest,
    opportunity_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: OpportunityService = Depends(get_opportunity_service),
) -> StandardResponse[OpportunityRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.opportunities.assign"
    ):
        raise CrmPermissionDeniedError("crm.opportunities.assign")
    opportunity = svc.assign(
        opportunity_id,
        company_id,
        body.owner_id,
        actor_user_id=cast(UUID, current_user.user_id),
    )
    return StandardResponse(
        data=OpportunityRead.model_validate(opportunity),
        message="Opportunity reassigned.",
        meta=_meta(),
    )


@router.post(
    "/opportunities/{opportunity_id}/stage",
    response_model=StandardResponse[OpportunityRead],
    summary="Change an Opportunity's pipeline stage",
)
async def change_opportunity_stage(
    body: OpportunityStageChangeRequest,
    opportunity_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: OpportunityService = Depends(get_opportunity_service),
) -> StandardResponse[OpportunityRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.opportunities.update"
    ):
        raise CrmPermissionDeniedError("crm.opportunities.update")
    opportunity = svc.change_stage(
        opportunity_id,
        company_id,
        body.stage_id,
        body.probability,
        actor_user_id=cast(UUID, current_user.user_id),
    )
    return StandardResponse(
        data=OpportunityRead.model_validate(opportunity),
        message="Opportunity stage changed.",
        meta=_meta(),
    )


@router.post(
    "/opportunities/{opportunity_id}/win",
    response_model=StandardResponse[OpportunityRead],
    summary="Mark an Opportunity WON",
)
async def win_opportunity(
    opportunity_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: OpportunityService = Depends(get_opportunity_service),
) -> StandardResponse[OpportunityRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.opportunities.close"
    ):
        raise CrmPermissionDeniedError("crm.opportunities.close")
    opportunity = svc.win(
        opportunity_id, company_id, actor_user_id=cast(UUID, current_user.user_id)
    )
    return StandardResponse(
        data=OpportunityRead.model_validate(opportunity),
        message="Opportunity marked WON.",
        meta=_meta(),
    )


@router.post(
    "/opportunities/{opportunity_id}/lose",
    response_model=StandardResponse[OpportunityRead],
    summary="Mark an Opportunity LOST",
)
async def lose_opportunity(
    body: OpportunityLoseRequest,
    opportunity_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: OpportunityService = Depends(get_opportunity_service),
) -> StandardResponse[OpportunityRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.opportunities.close"
    ):
        raise CrmPermissionDeniedError("crm.opportunities.close")
    opportunity = svc.lose(
        opportunity_id,
        company_id,
        body.lost_reason,
        actor_user_id=cast(UUID, current_user.user_id),
    )
    return StandardResponse(
        data=OpportunityRead.model_validate(opportunity),
        message="Opportunity marked LOST.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Activities (spec.md §38.5)
# ---------------------------------------------------------------------------


@router.post(
    "/activities",
    response_model=StandardResponse[ActivityRead],
    status_code=status.HTTP_201_CREATED,
    summary="Log a new Activity",
)
async def create_activity(
    body: ActivityCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ActivityService = Depends(get_activity_service),
) -> StandardResponse[ActivityRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.activities.create"
    ):
        raise CrmPermissionDeniedError("crm.activities.create")
    activity = svc.create(company_id, body, created_by=cast(UUID, current_user.user_id))
    return StandardResponse(
        data=ActivityRead.model_validate(activity),
        message="Activity created.",
        meta=_meta(),
    )


@router.get(
    "/activities",
    response_model=PaginatedResponse[ActivityRead],
    summary="List / filter Activities",
)
async def list_activities(
    company_id: UUID = Path(..., description="Company identifier"),
    activity_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    assigned_to: UUID | None = Query(None),
    lead_id: UUID | None = Query(None),
    customer_id: UUID | None = Query(None),
    opportunity_id: UUID | None = Query(None),
    due_from: datetime | None = Query(None),
    due_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ActivityService = Depends(get_activity_service),
) -> PaginatedResponse[ActivityRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.activities.view"
    ):
        raise CrmPermissionDeniedError("crm.activities.view")
    items, total = svc.list_filtered(
        company_id,
        activity_type=activity_type,
        status=status_filter,
        assigned_to=assigned_to,
        lead_id=lead_id,
        customer_id=customer_id,
        opportunity_id=opportunity_id,
        due_from=due_from,
        due_to=due_to,
        page=page,
        page_size=page_size,
    )
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        data=PaginatedData(
            items=[ActivityRead.model_validate(a) for a in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        ),
        message=f"{total} activity(ies) found.",
        meta=_meta(),
    )


@router.get(
    "/activities/{activity_id}",
    response_model=StandardResponse[ActivityRead],
    summary="Get an Activity",
)
async def get_activity(
    activity_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ActivityService = Depends(get_activity_service),
) -> StandardResponse[ActivityRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.activities.view"
    ):
        raise CrmPermissionDeniedError("crm.activities.view")
    activity = svc.get(activity_id, company_id)
    return StandardResponse(
        data=ActivityRead.model_validate(activity),
        message="Activity retrieved.",
        meta=_meta(),
    )


@router.patch(
    "/activities/{activity_id}",
    response_model=StandardResponse[ActivityRead],
    summary="Update an Activity",
)
async def update_activity(
    body: ActivityUpdate,
    activity_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ActivityService = Depends(get_activity_service),
) -> StandardResponse[ActivityRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.activities.update"
    ):
        raise CrmPermissionDeniedError("crm.activities.update")
    activity = svc.update(activity_id, company_id, body)
    return StandardResponse(
        data=ActivityRead.model_validate(activity),
        message="Activity updated.",
        meta=_meta(),
    )


@router.delete(
    "/activities/{activity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete an Activity",
)
async def delete_activity(
    activity_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ActivityService = Depends(get_activity_service),
) -> None:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.activities.delete"
    ):
        raise CrmPermissionDeniedError("crm.activities.delete")
    svc.soft_delete(activity_id, company_id)


@router.post(
    "/activities/{activity_id}/complete",
    response_model=StandardResponse[ActivityRead],
    summary="Complete an Activity (cascades Lead last_contact_date/status)",
)
async def complete_activity(
    activity_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ActivityService = Depends(get_activity_service),
) -> StandardResponse[ActivityRead]:
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.activities.update"
    ):
        raise CrmPermissionDeniedError("crm.activities.update")
    # 200, idempotent — completing an already-COMPLETED Activity is a no-op
    # (spec.md §43), not an error.
    activity = svc.complete(
        activity_id, company_id, actor_user_id=cast(UUID, current_user.user_id)
    )
    return StandardResponse(
        data=ActivityRead.model_validate(activity),
        message="Activity completed.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Customer 360 (spec.md §20, §38.6) — Phase 7
# ---------------------------------------------------------------------------


@router.get(
    "/customers/{customer_id}/360",
    response_model=StandardResponse[Customer360],
    summary="Customer 360 — composed CRM + Sales + Accounting view",
)
async def get_customer_360(
    customer_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: Customer360Service = Depends(get_customer_360_service),
) -> StandardResponse[Customer360]:
    # spec.md §38.6: BOTH permissions are required — a partial-permission
    # user gets a partial 403, not a silently incomplete view.
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.opportunities.view"
    ):
        raise CrmPermissionDeniedError("crm.opportunities.view")
    if not user_has_crm_permission(
        svc.db, company_id, current_user.user_id, "crm.activities.view"
    ):
        raise CrmPermissionDeniedError("crm.activities.view")
    result = svc.get_customer_360(company_id, customer_id)
    return StandardResponse(
        data=Customer360(
            customer=CustomerSummary.model_validate(result.customer),
            converted_leads=[
                LeadRead.model_validate(lead) for lead in result.converted_leads
            ],
            opportunities=[
                OpportunityRead.model_validate(o) for o in result.opportunities
            ],
            activities=[ActivityRead.model_validate(a) for a in result.activities],
            sales_history=SalesHistorySummary(
                quotation_count=result.sales_history.quotation_count,
                order_count=result.sales_history.order_count,
                invoice_count=result.sales_history.invoice_count,
                delivery_count=result.sales_history.delivery_count,
            ),
            financial_summary=FinancialSummary(
                total_outstanding_base=result.financial_summary.total_outstanding_base,
                credit_limit=result.financial_summary.credit_limit,
                credit_status=result.financial_summary.credit_status,
                as_of_date=result.financial_summary.as_of_date,
                current=result.financial_summary.current,
                days_1_30=result.financial_summary.days_1_30,
                days_31_60=result.financial_summary.days_31_60,
                days_61_90=result.financial_summary.days_61_90,
                days_91_120=result.financial_summary.days_91_120,
                days_120_plus=result.financial_summary.days_120_plus,
            ),
            last_interaction=result.last_interaction,
            next_follow_up=result.next_follow_up,
        ),
        message="Customer 360 retrieved.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Dashboard & Reports (spec.md §38.6, §40, §41) — Phase 9
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard",
    response_model=StandardResponse[CrmDashboard],
    summary="CRM dashboard — current-month KPI summary",
)
async def get_dashboard(
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: CrmReportingService = Depends(get_crm_reporting_service),
) -> StandardResponse[CrmDashboard]:
    if not user_has_crm_permission(
        db, company_id, current_user.user_id, "crm.reports.view"
    ):
        raise CrmPermissionDeniedError("crm.reports.view")
    dashboard = svc.get_dashboard(company_id)
    return StandardResponse(
        data=dashboard,
        message="Dashboard retrieved.",
        meta=_meta(),
    )


@router.get(
    "/reports/pipeline",
    response_model=StandardResponse[PipelineReport],
    summary="Pipeline report — value by stage/owner/source, win rate, cycle time",
)
async def get_pipeline_report(
    company_id: UUID = Path(..., description="Company identifier"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: CrmReportingService = Depends(get_crm_reporting_service),
) -> StandardResponse[PipelineReport]:
    if not user_has_crm_permission(
        db, company_id, current_user.user_id, "crm.reports.view"
    ):
        raise CrmPermissionDeniedError("crm.reports.view")
    report = svc.get_pipeline_report(company_id, date_from, date_to)
    return StandardResponse(
        data=report,
        message="Pipeline report retrieved.",
        meta=_meta(),
    )


@router.get(
    "/reports/leads",
    response_model=StandardResponse[LeadReport],
    summary="Lead report — counts by status/source, conversion rate",
)
async def get_lead_report(
    company_id: UUID = Path(..., description="Company identifier"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: CrmReportingService = Depends(get_crm_reporting_service),
) -> StandardResponse[LeadReport]:
    if not user_has_crm_permission(
        db, company_id, current_user.user_id, "crm.reports.view"
    ):
        raise CrmPermissionDeniedError("crm.reports.view")
    report = svc.get_lead_report(company_id, date_from, date_to)
    return StandardResponse(
        data=report,
        message="Lead report retrieved.",
        meta=_meta(),
    )


@router.get(
    "/reports/activities",
    response_model=StandardResponse[ActivityReport],
    summary="Activity report — completed by type, overdue by owner",
)
async def get_activity_report(
    company_id: UUID = Path(..., description="Company identifier"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: CrmReportingService = Depends(get_crm_reporting_service),
) -> StandardResponse[ActivityReport]:
    if not user_has_crm_permission(
        db, company_id, current_user.user_id, "crm.reports.view"
    ):
        raise CrmPermissionDeniedError("crm.reports.view")
    report = svc.get_activity_report(company_id, date_from, date_to)
    return StandardResponse(
        data=report,
        message="Activity report retrieved.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Module administration (enable/disable) — mounted separately in
# api/v1/router.py, WITHOUT require_crm_enabled: unlike every other endpoint
# in this file, these must be reachable while the module is still disabled
# (a company can't enable CRM through an endpoint that requires CRM to
# already be enabled). Gated instead by company-admin authority
# (require_admin_or_above) since "which modules does this company use" is a
# company-administration decision, not a CRM-domain permission — CRM's own
# crm.* permissions are meaningless to check before the module is active.
# ---------------------------------------------------------------------------

admin_router = APIRouter(tags=["crm-admin"])


@admin_router.get(
    "/status",
    response_model=StandardResponse[CrmStatusRead],
    summary="Whether the CRM module is enabled for this company",
)
async def get_crm_module_status(
    company_id: UUID = Path(..., description="Company identifier"),
    _current_user: CurrentUser = Depends(require_authenticated),
    flag_service: CrmFeatureFlagService = Depends(get_crm_feature_flag_service),
) -> StandardResponse[CrmStatusRead]:
    enabled = flag_service.is_enabled(company_id)
    return StandardResponse(
        data=CrmStatusRead(enabled=enabled),
        message="CRM module status retrieved.",
        meta=_meta(),
    )


@admin_router.post(
    "/enable",
    response_model=StandardResponse[CrmStatusRead],
    summary="Enable the CRM module for this company (owner/admin only)",
)
async def enable_crm_module(
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    _company: Company = Depends(require_admin_or_above()),
    flag_service: CrmFeatureFlagService = Depends(get_crm_feature_flag_service),
) -> StandardResponse[CrmStatusRead]:
    flag_service.enable(company_id, actor_id=current_user.user_id)
    return StandardResponse(
        data=CrmStatusRead(enabled=True),
        message="CRM module enabled.",
        meta=_meta(),
    )


@admin_router.post(
    "/disable",
    response_model=StandardResponse[CrmStatusRead],
    summary="Disable the CRM module for this company (owner/admin only)",
)
async def disable_crm_module(
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    _company: Company = Depends(require_admin_or_above()),
    flag_service: CrmFeatureFlagService = Depends(get_crm_feature_flag_service),
) -> StandardResponse[CrmStatusRead]:
    flag_service.disable(company_id, actor_id=current_user.user_id)
    return StandardResponse(
        data=CrmStatusRead(enabled=False),
        message="CRM module disabled.",
        meta=_meta(),
    )

"""Installments module API router.

Phase 2 (Configuration & Plans): Configuration and Plan/Template endpoint
groups, plus the module admin status/enable/disable group. Phase 3
(Contract Persistence) adds the Contracts and Eligibility endpoint
groups. Endpoint groups are added incrementally in later phases,
mirroring ``modules/crm/router.py``'s own incremental-growth convention.
Not yet mounted into ``api/v1/router.py`` — mounting (with
``dependencies=[Depends(get_current_company_member)]`` only, no blanket
entitlement dependency, per plan.md §15.2) is tasks.md T190 (Phase 11).

Every endpoint enforces its documented ``installments.*`` permission
(plan.md §16.1's per-endpoint table) inline via
``user_has_installments_permission()`` — entitlement
(``InstallmentAccessPolicy``) is threaded into service methods starting
Phase 11 (T188/T189), not this phase.

Endpoints:
    GET  /config                       — effective configuration (?branch_id=)
    PUT  /config                       — upsert company-default or branch-override

    GET    /plans                      — list active plan templates
    POST   /plans                      — create a plan template
    PATCH  /plans/{planId}             — edit a plan template
    POST   /plans/{planId}/deactivate  — deactivate a plan template

    GET  /contracts                    — list contracts (paginated)
    GET  /contracts/{contractId}       — get full contract detail
    POST /contracts                    — create a DRAFT contract

    GET  /eligibility?sales_invoice_id= — evaluate installment-offer eligibility

    GET  /status   (admin_router)      — module toggle status
    POST /enable   (admin_router)      — enable the module
    POST /disable  (admin_router)      — disable the module

Spec ref: specs/010-installments/plan.md §23;
specs/010-installments/contracts/installments-api.yaml.
"""

from __future__ import annotations

import math
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from core.auth.dependencies import require_authenticated
from core.auth.interfaces import CurrentUser
from core.database.session import get_db
from core.exceptions.base import ForbiddenException
from core.logging.setup import REQUEST_ID_CONTEXT
from core.schemas.pagination import PaginatedData, PaginatedResponse
from core.schemas.response import ResponseMeta, StandardResponse
from core.utils.datetime import utcnow
from modules.installments.dependencies import (
    get_installment_configuration_service,
    get_installment_contract_service,
    get_installment_eligibility_service,
    get_installment_plan_template_service,
    get_installments_feature_flag_service,
)
from modules.installments.exceptions import InstallmentNotFoundError
from modules.installments.schemas.base import InstallmentsStatusRead
from modules.installments.schemas.configuration import (
    InstallmentConfigurationRead,
    InstallmentConfigurationUpsert,
)
from modules.installments.schemas.contract import (
    InstallmentContractCreate,
    InstallmentContractRead,
    InstallmentContractSummary,
)
from modules.installments.schemas.eligibility import EligibilityResultRead
from modules.installments.schemas.plan_template import (
    InstallmentPlanTemplateCreate,
    InstallmentPlanTemplateRead,
    InstallmentPlanTemplateUpdate,
)
from modules.installments.services.configuration_service import (
    InstallmentConfigurationService,
)
from modules.installments.services.contract_service import InstallmentContractService
from modules.installments.services.eligibility_service import (
    InstallmentEligibilityService,
)
from modules.installments.services.feature_flag_service import (
    InstallmentsFeatureFlagService,
)
from modules.installments.services.permission_check import (
    user_has_installments_permission,
)
from modules.installments.services.plan_template_service import (
    InstallmentPlanTemplateService,
)
from modules.users_roles.constants import ADMIN_RANK
from modules.users_roles.dependencies import require_rank

router = APIRouter(tags=["installments"])
admin_router = APIRouter(tags=["installments-admin"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow())


def _require_permission(
    db: Session, company_id: UUID, current_user: CurrentUser, code: str
) -> None:
    if not user_has_installments_permission(
        db, company_id, current_user.user_id, code, user_roles=current_user.roles
    ):
        raise ForbiddenException(message=f"You do not have the '{code}' permission.")


# ---------------------------------------------------------------------------
# Configuration (plan.md §16.1: installments.config.manage, ADMIN)
# ---------------------------------------------------------------------------


@router.get(
    "/config",
    response_model=StandardResponse[InstallmentConfigurationRead],
    summary="Get effective installment configuration (company + branch override)",
)
async def get_installment_configuration(
    company_id: UUID = Path(..., description="Company identifier"),
    branch_id: UUID | None = Query(
        None, description="Resolve the effective config for this branch"
    ),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentConfigurationService = Depends(
        get_installment_configuration_service
    ),
) -> StandardResponse[InstallmentConfigurationRead]:
    _require_permission(db, company_id, current_user, "installments.config.manage")
    config = svc.get_effective_config(company_id, branch_id)
    if config is None:
        raise InstallmentNotFoundError("InstallmentConfiguration")
    return StandardResponse(
        data=InstallmentConfigurationRead.model_validate(config),
        message="Effective installment configuration retrieved.",
        meta=_meta(),
    )


@router.put(
    "/config",
    response_model=StandardResponse[InstallmentConfigurationRead],
    summary="Update tenant-level (or branch-override) installment configuration",
)
async def upsert_installment_configuration(
    body: InstallmentConfigurationUpsert,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentConfigurationService = Depends(
        get_installment_configuration_service
    ),
) -> StandardResponse[InstallmentConfigurationRead]:
    _require_permission(db, company_id, current_user, "installments.config.manage")
    fields = body.model_dump(exclude={"branch_id"})
    config = svc.upsert_config(
        company_id=company_id,
        branch_id=body.branch_id,
        actor_id=current_user.user_id,
        **fields,
    )
    return StandardResponse(
        data=InstallmentConfigurationRead.model_validate(config),
        message="Installment configuration updated.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Plans / Templates
# ---------------------------------------------------------------------------


@router.get(
    "/plans",
    response_model=PaginatedResponse[InstallmentPlanTemplateRead],
    summary="List installment plan templates",
)
async def list_plan_templates(
    company_id: UUID = Path(..., description="Company identifier"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentPlanTemplateService = Depends(
        get_installment_plan_template_service
    ),
) -> PaginatedResponse[InstallmentPlanTemplateRead]:
    _require_permission(db, company_id, current_user, "installments.contract.view")
    items = svc.list_active(company_id)
    total = len(items)
    page_items = items[(page - 1) * page_size : (page - 1) * page_size + page_size]
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        data=PaginatedData(
            items=[InstallmentPlanTemplateRead.model_validate(t) for t in page_items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        ),
        message=f"{total} plan template(s) found.",
        meta=_meta(),
    )


@router.post(
    "/plans",
    response_model=StandardResponse[InstallmentPlanTemplateRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a plan template",
)
async def create_plan_template(
    body: InstallmentPlanTemplateCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentPlanTemplateService = Depends(
        get_installment_plan_template_service
    ),
) -> StandardResponse[InstallmentPlanTemplateRead]:
    _require_permission(db, company_id, current_user, "installments.plan.manage")
    template = svc.create(
        company_id=company_id,
        actor_id=current_user.user_id,
        **body.model_dump(),
    )
    return StandardResponse(
        data=InstallmentPlanTemplateRead.model_validate(template),
        message="Plan template created.",
        meta=_meta(),
    )


@router.patch(
    "/plans/{planId}",
    response_model=StandardResponse[InstallmentPlanTemplateRead],
    summary="Edit a plan template (never mutates contracts already created from it)",
)
async def update_plan_template(
    body: InstallmentPlanTemplateUpdate,
    company_id: UUID = Path(..., description="Company identifier"),
    plan_id: UUID = Path(..., alias="planId"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentPlanTemplateService = Depends(
        get_installment_plan_template_service
    ),
) -> StandardResponse[InstallmentPlanTemplateRead]:
    _require_permission(db, company_id, current_user, "installments.plan.manage")
    template = svc.update(
        company_id=company_id,
        template_id=plan_id,
        **body.model_dump(exclude_unset=True),
    )
    return StandardResponse(
        data=InstallmentPlanTemplateRead.model_validate(template),
        message="Plan template updated.",
        meta=_meta(),
    )


@router.post(
    "/plans/{planId}/deactivate",
    response_model=StandardResponse[InstallmentPlanTemplateRead],
    summary="Deactivate a template (blocks new use only)",
)
async def deactivate_plan_template(
    company_id: UUID = Path(..., description="Company identifier"),
    plan_id: UUID = Path(..., alias="planId"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentPlanTemplateService = Depends(
        get_installment_plan_template_service
    ),
) -> StandardResponse[InstallmentPlanTemplateRead]:
    _require_permission(db, company_id, current_user, "installments.plan.manage")
    template = svc.deactivate(company_id=company_id, template_id=plan_id)
    return StandardResponse(
        data=InstallmentPlanTemplateRead.model_validate(template),
        message="Plan template deactivated.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Contracts (plan.md §16.1: installments.contract.view/READ,
# installments.contract.create/ORIGINATION)
# ---------------------------------------------------------------------------


@router.get(
    "/contracts",
    response_model=PaginatedResponse[InstallmentContractSummary],
    summary="List/search contracts",
)
async def list_contracts(
    company_id: UUID = Path(..., description="Company identifier"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentContractService = Depends(get_installment_contract_service),
) -> PaginatedResponse[InstallmentContractSummary]:
    _require_permission(db, company_id, current_user, "installments.contract.view")
    items, total = svc.list(company_id, skip=(page - 1) * page_size, limit=page_size)
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        data=PaginatedData(
            items=[InstallmentContractSummary.model_validate(c) for c in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        ),
        message=f"{total} contract(s) found.",
        meta=_meta(),
    )


@router.get(
    "/contracts/{contractId}",
    response_model=StandardResponse[InstallmentContractRead],
    summary="Get full contract detail",
)
async def get_contract(
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentContractService = Depends(get_installment_contract_service),
) -> StandardResponse[InstallmentContractRead]:
    _require_permission(db, company_id, current_user, "installments.contract.view")
    contract = svc.get(company_id, contract_id)
    return StandardResponse(
        data=InstallmentContractRead.model_validate(contract),
        message="Contract retrieved.",
        meta=_meta(),
    )


@router.post(
    "/contracts",
    response_model=StandardResponse[InstallmentContractRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a DRAFT contract (from template or custom terms)",
)
async def create_contract(
    body: InstallmentContractCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentContractService = Depends(get_installment_contract_service),
) -> StandardResponse[InstallmentContractRead]:
    _require_permission(db, company_id, current_user, "installments.contract.create")
    contract = svc.create_draft(
        company_id=company_id,
        actor_id=current_user.user_id,
        **body.model_dump(),
    )
    return StandardResponse(
        data=InstallmentContractRead.model_validate(contract),
        message="Installment contract created.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Eligibility (plan.md §16.1: installments.contract.create, ORIGINATION)
# ---------------------------------------------------------------------------


@router.get(
    "/eligibility",
    response_model=StandardResponse[EligibilityResultRead],
    summary="Evaluate customer/invoice eligibility for an installment offer",
)
async def check_eligibility(
    company_id: UUID = Path(..., description="Company identifier"),
    sales_invoice_id: UUID = Query(..., description="Sales invoice to evaluate"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentEligibilityService = Depends(get_installment_eligibility_service),
) -> StandardResponse[EligibilityResultRead]:
    _require_permission(db, company_id, current_user, "installments.contract.create")
    result = svc.check_invoice_eligibility(company_id, sales_invoice_id)
    return StandardResponse(
        data=EligibilityResultRead.model_validate(result),
        message="Invoice/customer eligible for an installment offer.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Module administration (status/enable/disable) — rank-gated (ADMIN_RANK),
# reachable regardless of entitlement state (mirrors CRM's admin_router;
# ADMIN-class operations bypass InstallmentAccessPolicy entirely per
# plan.md §15.2, wired in Phase 11).
# ---------------------------------------------------------------------------


@admin_router.get(
    "/status",
    response_model=StandardResponse[InstallmentsStatusRead],
    summary="Whether the Installments module is enabled for this company",
)
async def get_installments_module_status(
    company_id: UUID = Path(..., description="Company identifier"),
    _current_user: CurrentUser = Depends(require_authenticated),
    flag_service: InstallmentsFeatureFlagService = Depends(
        get_installments_feature_flag_service
    ),
) -> StandardResponse[InstallmentsStatusRead]:
    enabled = flag_service.is_enabled(company_id)
    return StandardResponse(
        data=InstallmentsStatusRead(enabled=enabled),
        message="Installments module status retrieved.",
        meta=_meta(),
    )


@admin_router.post(
    "/enable",
    response_model=StandardResponse[InstallmentsStatusRead],
    summary="Enable the Installments module for this company (admin rank required)",
)
async def enable_installments_module(
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    _rank: int = Depends(require_rank(ADMIN_RANK)),
    flag_service: InstallmentsFeatureFlagService = Depends(
        get_installments_feature_flag_service
    ),
) -> StandardResponse[InstallmentsStatusRead]:
    flag_service.enable(company_id, actor_id=current_user.user_id)
    return StandardResponse(
        data=InstallmentsStatusRead(enabled=True),
        message="Installments module enabled.",
        meta=_meta(),
    )


@admin_router.post(
    "/disable",
    response_model=StandardResponse[InstallmentsStatusRead],
    summary="Disable the Installments module for this company (admin rank required)",
)
async def disable_installments_module(
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    _rank: int = Depends(require_rank(ADMIN_RANK)),
    flag_service: InstallmentsFeatureFlagService = Depends(
        get_installments_feature_flag_service
    ),
) -> StandardResponse[InstallmentsStatusRead]:
    flag_service.disable(company_id, actor_id=current_user.user_id)
    return StandardResponse(
        data=InstallmentsStatusRead(enabled=False),
        message="Installments module disabled.",
        meta=_meta(),
    )

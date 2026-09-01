"""Installments module API router.

Phase 2 (Configuration & Plans): Configuration and Plan/Template endpoint
groups, plus the module admin status/enable/disable group. Phase 3
(Contract Persistence) adds the Contracts and Eligibility endpoint
groups. Phase 4 (Schedule Engine) adds the Quote/Preview endpoint group.
Phase 5 (Contract Lifecycle) adds the Submission/Approval/Rejection
endpoint group. Endpoint groups are added incrementally in later phases,
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

    POST /quotes                       — generate a non-persisting quote/preview

    GET  /contracts                    — list contracts (paginated)
    GET  /contracts/{contractId}       — get full contract detail
    POST /contracts                    — create a DRAFT contract

    POST /contracts/{contractId}/submit  — DRAFT -> PENDING_APPROVAL|APPROVED
    POST /contracts/{contractId}/approve — PENDING_APPROVAL -> APPROVED
    POST /contracts/{contractId}/reject  — PENDING_APPROVAL -> DRAFT

    GET  /eligibility?sales_invoice_id= — evaluate installment-offer eligibility

    GET  /status   (admin_router)      — module toggle status
    POST /enable   (admin_router)      — enable the module
    POST /disable  (admin_router)      — disable the module

Spec ref: specs/010-installments/plan.md §23;
specs/010-installments/contracts/installments-api.yaml.
"""

from __future__ import annotations

import math
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Query, status
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
    get_installment_collection_service,
    get_installment_configuration_service,
    get_installment_contract_service,
    get_installment_document_service,
    get_installment_eligibility_service,
    get_installment_plan_template_service,
    get_installment_quote_service,
    get_installment_reporting_service,
    get_installment_rescheduling_service,
    get_installment_settlement_service,
    get_installments_feature_flag_service,
)
from modules.installments.exceptions import InstallmentNotFoundError
from modules.installments.schemas.base import InstallmentsStatusRead
from modules.installments.schemas.collection import (
    InstallmentCollectionCreate,
    InstallmentCollectionResultRead,
    InstallmentCollectionReverseRequest,
)
from modules.installments.schemas.configuration import (
    InstallmentConfigurationRead,
    InstallmentConfigurationUpsert,
)
from modules.installments.schemas.contract import (
    InstallmentContractCreate,
    InstallmentContractRead,
    InstallmentContractRejectRequest,
    InstallmentContractSummary,
)
from modules.installments.schemas.eligibility import EligibilityResultRead
from modules.installments.schemas.lifecycle import (
    InstallmentCancelRequest,
    InstallmentCureRequest,
    InstallmentDefaultRequest,
    InstallmentRescheduleRequest,
    InstallmentWriteoffRequest,
)
from modules.installments.schemas.plan_template import (
    InstallmentPlanTemplateCreate,
    InstallmentPlanTemplateRead,
    InstallmentPlanTemplateUpdate,
)
from modules.installments.schemas.reports import (
    InstallmentAgreementView,
    InstallmentCustomerStatement,
    InstallmentCustomerStatementContract,
    InstallmentDashboard,
    InstallmentReportRow,
    InstallmentScheduleDocument,
    InstallmentScheduleDocumentLine,
)
from modules.installments.schemas.schedule import (
    InstallmentQuotePreviewRead,
    InstallmentQuoteRequest,
    InstallmentScheduleRead,
)
from modules.installments.schemas.settlement import (
    InstallmentSettlementExecuteRequest,
    InstallmentSettlementQuoteRead,
    InstallmentSettlementQuoteRequest,
)
from modules.installments.services.collection_service import (
    InstallmentCollectionService,
)
from modules.installments.services.configuration_service import (
    InstallmentConfigurationService,
)
from modules.installments.services.contract_service import InstallmentContractService
from modules.installments.services.document_service import InstallmentDocumentService
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
from modules.installments.services.quote_service import InstallmentQuoteService
from modules.installments.services.reporting_service import (
    InstallmentDashboardData,
    InstallmentReportingService,
)
from modules.installments.services.rescheduling_service import (
    InstallmentReschedulingService,
    RescheduleTerms,
)
from modules.installments.services.settlement_service import (
    InstallmentSettlementService,
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
# Quote / Preview (plan.md §16.1: installments.contract.create, ORIGINATION)
# ---------------------------------------------------------------------------


@router.post(
    "/quotes",
    response_model=StandardResponse[InstallmentQuotePreviewRead],
    summary="Generate a deterministic, non-persisting installment quote/preview",
)
async def preview_quote(
    body: InstallmentQuoteRequest,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentQuoteService = Depends(get_installment_quote_service),
) -> StandardResponse[InstallmentQuotePreviewRead]:
    _require_permission(db, company_id, current_user, "installments.contract.create")
    preview = svc.preview(company_id, **body.model_dump())
    return StandardResponse(
        data=InstallmentQuotePreviewRead.model_validate(preview),
        message="Installment quote preview generated.",
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
# Submission / Approval / Rejection (plan.md §16.1: installments.contract
# .create for submit, installments.contract.approve for approve/reject,
# operation class ORIGINATION). ``cancel()``/``mark_defaulted()`` exist on
# the service (Phase 5) but are not wired to any endpoint here — cancel's
# endpoint is Phase 10's T174 (idempotency-protected), and
# mark_defaulted() is internal-only, never reachable from router.py.
# ---------------------------------------------------------------------------


@router.post(
    "/contracts/{contractId}/submit",
    response_model=StandardResponse[InstallmentContractRead],
    summary="DRAFT -> PENDING_APPROVAL (or directly -> APPROVED if no threshold applies)",
)
async def submit_contract(
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentContractService = Depends(get_installment_contract_service),
) -> StandardResponse[InstallmentContractRead]:
    _require_permission(db, company_id, current_user, "installments.contract.create")
    contract = svc.submit(company_id, contract_id, current_user.user_id)
    return StandardResponse(
        data=InstallmentContractRead.model_validate(contract),
        message="Installment contract submitted.",
        meta=_meta(),
    )


@router.post(
    "/contracts/{contractId}/approve",
    response_model=StandardResponse[InstallmentContractRead],
    summary="PENDING_APPROVAL -> APPROVED",
)
async def approve_contract(
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentContractService = Depends(get_installment_contract_service),
) -> StandardResponse[InstallmentContractRead]:
    _require_permission(db, company_id, current_user, "installments.contract.approve")
    contract = svc.approve(company_id, contract_id, current_user.user_id)
    return StandardResponse(
        data=InstallmentContractRead.model_validate(contract),
        message="Installment contract approved.",
        meta=_meta(),
    )


@router.post(
    "/contracts/{contractId}/reject",
    response_model=StandardResponse[InstallmentContractRead],
    summary="PENDING_APPROVAL -> DRAFT (rejection is an event, not a persisted status)",
)
async def reject_contract(
    body: InstallmentContractRejectRequest,
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentContractService = Depends(get_installment_contract_service),
) -> StandardResponse[InstallmentContractRead]:
    _require_permission(db, company_id, current_user, "installments.contract.approve")
    contract = svc.reject(company_id, contract_id, body.reason, current_user.user_id)
    return StandardResponse(
        data=InstallmentContractRead.model_validate(contract),
        message="Installment contract rejected.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Activation / Collections / Reversals (Phase 7, plan.md §16.1:
# installments.contract.activate/ORIGINATION,
# installments.collection.create/SERVICING,
# installments.collection.reverse/SERVICING). All three are idempotency-
# protected (plan.md §20) via the client-supplied ``Idempotency-Key``
# header.
# ---------------------------------------------------------------------------


@router.post(
    "/contracts/{contractId}/activate",
    response_model=StandardResponse[InstallmentContractRead],
    summary="APPROVED -> ACTIVE (generates the authoritative schedule; "
    "requires down payment if configured)",
)
async def activate_contract(
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentContractService = Depends(get_installment_contract_service),
) -> StandardResponse[InstallmentContractRead]:
    _require_permission(db, company_id, current_user, "installments.contract.activate")
    contract = svc.activate(
        company_id, contract_id, idempotency_key, current_user.user_id
    )
    return StandardResponse(
        data=InstallmentContractRead.model_validate(contract),
        message="Installment contract activated.",
        meta=_meta(),
    )


@router.post(
    "/contracts/{contractId}/collections",
    response_model=StandardResponse[InstallmentCollectionResultRead],
    status_code=status.HTTP_201_CREATED,
    summary="Record a collection (exact/partial/multi-installment/advance), "
    "oldest-due-first allocation",
)
async def record_collection(
    body: InstallmentCollectionCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentCollectionService = Depends(get_installment_collection_service),
) -> StandardResponse[InstallmentCollectionResultRead]:
    # FR-INST-356: permitted even when Installments entitlement is
    # disabled — servicing continuity for existing contracts.
    _require_permission(db, company_id, current_user, "installments.collection.create")
    result = svc.record_collection(
        company_id,
        contract_id,
        amount=body.amount,
        payment_method=body.payment_method,
        idempotency_key=idempotency_key,
        actor_id=current_user.user_id,
        bank_account_id=body.bank_account_id,
        cash_account_id=body.cash_account_id,
    )
    return StandardResponse(
        data=InstallmentCollectionResultRead.model_validate(result),
        message="Installment collection recorded.",
        meta=_meta(),
    )


@router.post(
    "/collections/{collectionId}/reverse",
    response_model=StandardResponse[InstallmentCollectionResultRead],
    summary="Reverse a previously recorded collection",
)
async def reverse_collection(
    body: InstallmentCollectionReverseRequest,
    company_id: UUID = Path(..., description="Company identifier"),
    collection_id: UUID = Path(..., alias="collectionId"),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentCollectionService = Depends(get_installment_collection_service),
) -> StandardResponse[InstallmentCollectionResultRead]:
    _require_permission(db, company_id, current_user, "installments.collection.reverse")
    result = svc.reverse_collection(
        company_id,
        collection_id,
        reason=body.reason,
        idempotency_key=idempotency_key,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=InstallmentCollectionResultRead.model_validate(result),
        message="Installment collection reversed.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Settlement (Phase 9, plan.md §16.1: installments.settlement.execute,
# SERVICING). Quote generation is read-only/non-idempotent (FR-INST-192);
# execution is idempotency-protected (plan.md §20) via the client-supplied
# ``Idempotency-Key`` header, same as Activation/Collections.
# ---------------------------------------------------------------------------


@router.post(
    "/contracts/{contractId}/settlement/quote",
    response_model=StandardResponse[InstallmentSettlementQuoteRead],
    summary="Generate a reproducible early-settlement quote (non-mutating, still audited)",
)
async def generate_settlement_quote(
    body: InstallmentSettlementQuoteRequest,
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentSettlementService = Depends(get_installment_settlement_service),
) -> StandardResponse[InstallmentSettlementQuoteRead]:
    _require_permission(db, company_id, current_user, "installments.settlement.execute")
    quote = svc.generate_quote(
        company_id,
        contract_id,
        body.as_of_date or date.today(),
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=InstallmentSettlementQuoteRead.model_validate(quote),
        message="Installment settlement quote generated.",
        meta=_meta(),
    )


@router.post(
    "/contracts/{contractId}/settlement/execute",
    response_model=StandardResponse[InstallmentContractRead],
    summary="Execute settlement against an authoritative payment already recorded",
)
async def execute_settlement(
    body: InstallmentSettlementExecuteRequest,
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentSettlementService = Depends(get_installment_settlement_service),
) -> StandardResponse[InstallmentContractRead]:
    _require_permission(db, company_id, current_user, "installments.settlement.execute")
    contract = svc.execute(
        company_id,
        contract_id,
        body.quoted_amount,
        body.quoted_as_of_date,
        idempotency_key,
        current_user.user_id,
        payment_method=body.payment_method,
        bank_account_id=body.bank_account_id,
        cash_account_id=body.cash_account_id,
    )
    return StandardResponse(
        data=InstallmentContractRead.model_validate(contract),
        message="Installment settlement executed.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Advanced Lifecycle (Phase 10, plan.md §16.1: installments.contract.
# reschedule/cancel/default/cure/writeoff). Reschedule/cancel/default/
# writeoff are idempotency-protected (plan.md §20) via the client-
# supplied ``Idempotency-Key`` header; cure is a discrete state
# transition with no financial posting (no idempotency key required).
# ---------------------------------------------------------------------------


@router.post(
    "/contracts/{contractId}/reschedule",
    response_model=StandardResponse[InstallmentContractRead],
    summary="Controlled due-date-only amendment; creates a new schedule version",
)
async def reschedule_contract(
    body: InstallmentRescheduleRequest,
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentReschedulingService = Depends(get_installment_rescheduling_service),
) -> StandardResponse[InstallmentContractRead]:
    _require_permission(
        db, company_id, current_user, "installments.contract.reschedule"
    )
    contract = svc.reschedule(
        company_id,
        contract_id,
        RescheduleTerms(
            first_due_date=body.first_due_date,
            frequency=body.frequency,
            principal_amount=body.principal_amount,
            markup_amount=body.markup_amount,
            installment_count=body.installment_count,
        ),
        body.reason,
        idempotency_key,
        current_user.user_id,
        requested_by=body.requested_by,
    )
    return StandardResponse(
        data=InstallmentContractRead.model_validate(contract),
        message="Installment contract rescheduled.",
        meta=_meta(),
    )


@router.post(
    "/contracts/{contractId}/cancel",
    response_model=StandardResponse[InstallmentContractRead],
    summary="Cancel per lifecycle-stage rules",
)
async def cancel_contract(
    body: InstallmentCancelRequest,
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentContractService = Depends(get_installment_contract_service),
) -> StandardResponse[InstallmentContractRead]:
    _require_permission(db, company_id, current_user, "installments.contract.cancel")
    contract = svc.cancel(
        company_id,
        contract_id,
        body.reason,
        idempotency_key,
        current_user.user_id,
        payment_id=body.payment_id,
    )
    return StandardResponse(
        data=InstallmentContractRead.model_validate(contract),
        message="Installment contract cancelled.",
        meta=_meta(),
    )


@router.post(
    "/contracts/{contractId}/default",
    response_model=StandardResponse[InstallmentContractRead],
    summary="Explicitly mark ACTIVE -> DEFAULTED (never automatic, never posts to Accounting)",
)
async def default_contract(
    body: InstallmentDefaultRequest,
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentContractService = Depends(get_installment_contract_service),
) -> StandardResponse[InstallmentContractRead]:
    _require_permission(db, company_id, current_user, "installments.contract.default")
    contract = svc.default_command(
        company_id, contract_id, body.reason, idempotency_key, current_user.user_id
    )
    return StandardResponse(
        data=InstallmentContractRead.model_validate(contract),
        message="Installment contract marked defaulted.",
        meta=_meta(),
    )


@router.post(
    "/contracts/{contractId}/cure",
    response_model=StandardResponse[InstallmentContractRead],
    summary="DEFAULTED -> ACTIVE (policy-gated; distinct permission from collection)",
)
async def cure_contract(
    body: InstallmentCureRequest,
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentContractService = Depends(get_installment_contract_service),
) -> StandardResponse[InstallmentContractRead]:
    _require_permission(db, company_id, current_user, "installments.contract.cure")
    contract = svc.cure(company_id, contract_id, body.reason, current_user.user_id)
    return StandardResponse(
        data=InstallmentContractRead.model_validate(contract),
        message="Installment contract cured.",
        meta=_meta(),
    )


@router.post(
    "/contracts/{contractId}/writeoff",
    response_model=StandardResponse[InstallmentContractRead],
    summary="Write off a DEFAULTED contract's remaining balance",
)
async def writeoff_contract(
    body: InstallmentWriteoffRequest,
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentContractService = Depends(get_installment_contract_service),
) -> StandardResponse[InstallmentContractRead]:
    _require_permission(db, company_id, current_user, "installments.contract.writeoff")
    contract = svc.writeoff(
        company_id, contract_id, body.reason, idempotency_key, current_user.user_id
    )
    return StandardResponse(
        data=InstallmentContractRead.model_validate(contract),
        message="Installment contract written off.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Schedules (plan.md §16.1: installments.contract.view, READ)
# ---------------------------------------------------------------------------


@router.get(
    "/contracts/{contractId}/schedule",
    response_model=StandardResponse[InstallmentScheduleRead],
    summary="Current (active) schedule version and lines",
)
async def get_active_schedule(
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentContractService = Depends(get_installment_contract_service),
) -> StandardResponse[InstallmentScheduleRead]:
    _require_permission(db, company_id, current_user, "installments.contract.view")
    contract, version, lines = svc.get_active_schedule(company_id, contract_id)
    return StandardResponse(
        data=InstallmentScheduleRead(
            contract_id=contract.id,
            version_number=version.version_number,
            status=version.status,
            generated_at=version.generated_at,
            lines=list(lines),
        ),
        message="Active installment schedule retrieved.",
        meta=_meta(),
    )


@router.get(
    "/contracts/{contractId}/schedule/versions/{versionNumber}",
    response_model=StandardResponse[InstallmentScheduleRead],
    summary="A specific (possibly superseded) schedule version",
)
async def get_schedule_version(
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    version_number: int = Path(..., alias="versionNumber"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentContractService = Depends(get_installment_contract_service),
) -> StandardResponse[InstallmentScheduleRead]:
    _require_permission(db, company_id, current_user, "installments.contract.view")
    contract, version, lines = svc.get_schedule_version(
        company_id, contract_id, version_number
    )
    return StandardResponse(
        data=InstallmentScheduleRead(
            contract_id=contract.id,
            version_number=version.version_number,
            status=version.status,
            generated_at=version.generated_at,
            lines=list(lines),
        ),
        message="Installment schedule version retrieved.",
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
# Reports / Dashboard (plan.md §16.1: installments.report.view, READ)
# ---------------------------------------------------------------------------

_REPORT_TYPES = (
    "contract-register",
    "collection",
    "due",
    "overdue",
    "aging",
    "settlement",
    "default-writeoff",
    "plan-performance",
)


@router.get(
    "/reports/{reportType}",
    response_model=PaginatedResponse[InstallmentReportRow],
    summary=(
        "contract-register | collection | due | overdue | aging | settlement | "
        "default-writeoff | plan-performance"
    ),
)
async def get_report(
    company_id: UUID = Path(..., description="Company identifier"),
    report_type: str = Path(..., alias="reportType"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentReportingService = Depends(get_installment_reporting_service),
) -> PaginatedResponse[InstallmentReportRow]:
    _require_permission(db, company_id, current_user, "installments.report.view")
    if report_type not in _REPORT_TYPES:
        raise InstallmentNotFoundError("ReportType", report_type)

    skip = (page - 1) * page_size
    if report_type == "contract-register":
        rows, total = svc.get_contract_register(
            company_id, status=status_filter, skip=skip, limit=page_size
        )
    elif report_type == "collection":
        rows, total = svc.get_collection_report(company_id, skip=skip, limit=page_size)
    elif report_type == "due":
        rows, total = svc.get_due_report(company_id, skip=skip, limit=page_size)
    elif report_type == "overdue":
        rows, total = svc.get_overdue_report(company_id, skip=skip, limit=page_size)
    elif report_type == "aging":
        rows, total = svc.get_aging_report(company_id, skip=skip, limit=page_size)
    elif report_type == "settlement":
        rows, total = svc.get_settlement_report(company_id, skip=skip, limit=page_size)
    elif report_type == "default-writeoff":
        rows, total = svc.get_default_writeoff_report(
            company_id, skip=skip, limit=page_size
        )
    else:  # plan-performance
        rows, total = svc.get_plan_performance_report(company_id)

    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        data=PaginatedData(
            items=[InstallmentReportRow(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        ),
        message=f"{total} {report_type} report row(s) found.",
        meta=_meta(),
    )


@router.get(
    "/dashboard",
    response_model=StandardResponse[InstallmentDashboard],
    summary=(
        "KPI summary (active contracts, outstanding, due today/this month, "
        "overdue, collection rate, aging distribution)"
    ),
)
async def get_dashboard(
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentReportingService = Depends(get_installment_reporting_service),
) -> StandardResponse[InstallmentDashboard]:
    _require_permission(db, company_id, current_user, "installments.report.view")
    data: InstallmentDashboardData = svc.get_dashboard(company_id)
    return StandardResponse(
        data=InstallmentDashboard(
            active_contract_count=data.active_contract_count,
            outstanding_amount=data.outstanding_amount,
            due_today_amount=data.due_today_amount,
            due_this_month_amount=data.due_this_month_amount,
            collected_today_amount=data.collected_today_amount,
            collected_this_month_amount=data.collected_this_month_amount,
            overdue_amount=data.overdue_amount,
            overdue_count=data.overdue_count,
            collection_rate=data.collection_rate,
            aging_distribution=data.aging_distribution,
            defaulted_balance=data.defaulted_balance,
            written_off_balance=data.written_off_balance,
            upcoming_receivables_amount=data.upcoming_receivables_amount,
        ),
        message="Installments dashboard KPIs retrieved.",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Documents / Statements (plan.md §16.1: installments.contract.view, READ)
# ---------------------------------------------------------------------------


@router.get(
    "/contracts/{contractId}/documents/agreement",
    response_model=StandardResponse[InstallmentAgreementView],
    summary="Installment agreement document (read-only JSON)",
)
async def get_agreement_document(
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentDocumentService = Depends(get_installment_document_service),
) -> StandardResponse[InstallmentAgreementView]:
    _require_permission(db, company_id, current_user, "installments.contract.view")
    result = svc.get_agreement(company_id, contract_id)
    return StandardResponse(
        data=InstallmentAgreementView.model_validate(result),
        message="Installment agreement document retrieved.",
        meta=_meta(),
    )


@router.get(
    "/contracts/{contractId}/documents/schedule",
    response_model=StandardResponse[InstallmentScheduleDocument],
    summary="Payment schedule document",
)
async def get_schedule_document(
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentDocumentService = Depends(get_installment_document_service),
) -> StandardResponse[InstallmentScheduleDocument]:
    _require_permission(db, company_id, current_user, "installments.contract.view")
    result = svc.get_schedule_document(company_id, contract_id)
    return StandardResponse(
        data=InstallmentScheduleDocument(
            document_type=result["document_type"],
            contract_id=result["contract_id"],
            contract_number=result["contract_number"],
            version_number=result["version_number"],
            generated_at=result["generated_at"],
            lines=[
                InstallmentScheduleDocumentLine.model_validate(line)
                for line in result["lines"]
            ],
        ),
        message="Installment schedule document retrieved.",
        meta=_meta(),
    )


@router.get(
    "/contracts/{contractId}/documents/settlement-quote",
    response_model=StandardResponse[InstallmentSettlementQuoteRead],
    summary="Latest settlement quotation document",
)
async def get_settlement_quote_document(
    company_id: UUID = Path(..., description="Company identifier"),
    contract_id: UUID = Path(..., alias="contractId"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentSettlementService = Depends(get_installment_settlement_service),
) -> StandardResponse[InstallmentSettlementQuoteRead]:
    """Reuses ``InstallmentSettlementService.generate_quote()``'s output
    directly (plan.md §27) — already a structured, non-mutating read; no
    second, competing document-generation code path exists for it."""
    _require_permission(db, company_id, current_user, "installments.contract.view")
    quote = svc.generate_quote(company_id, contract_id, date.today(), actor_id=None)
    return StandardResponse(
        data=InstallmentSettlementQuoteRead.model_validate(quote),
        message="Installment settlement quotation document retrieved.",
        meta=_meta(),
    )


@router.get(
    "/customers/{customerId}/statement",
    response_model=StandardResponse[InstallmentCustomerStatement],
    summary="Cross-contract customer installment statement",
)
async def get_customer_statement(
    company_id: UUID = Path(..., description="Company identifier"),
    customer_id: UUID = Path(..., alias="customerId"),
    current_user: CurrentUser = Depends(require_authenticated),
    db: Session = Depends(get_db),
    svc: InstallmentDocumentService = Depends(get_installment_document_service),
) -> StandardResponse[InstallmentCustomerStatement]:
    _require_permission(db, company_id, current_user, "installments.contract.view")
    result = svc.get_customer_statement(company_id, customer_id)
    return StandardResponse(
        data=InstallmentCustomerStatement(
            document_type=result["document_type"],
            customer_id=result["customer_id"],
            contracts=[
                InstallmentCustomerStatementContract.model_validate(c)
                for c in result["contracts"]
            ],
        ),
        message="Customer installment statement retrieved.",
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

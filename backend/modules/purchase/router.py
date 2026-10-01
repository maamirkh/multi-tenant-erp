"""Purchase module API router — Phase 0 + Phase 1 + Phase 2 + Phase 3 endpoints.

Phase 2 (Supplier enrichment):
    GET  /suppliers/{id}/credit-limit          — get credit limit
    PUT  /suppliers/{id}/credit-limit          — set/update credit limit

    GET  /suppliers/{id}/bank-details          — list bank details (Finance Manager)
    POST /suppliers/{id}/bank-details          — add bank details (Finance Manager)
    PUT  /suppliers/{id}/bank-details/{bd_id}  — update bank details (Finance Manager)
    DELETE /suppliers/{id}/bank-details/{bd_id} — delete bank details (Finance Manager)

    GET  /suppliers/{id}/rating                — get supplier rating
    POST /suppliers/{id}/rating/override       — manual override (Purchase Manager)
    DELETE /suppliers/{id}/rating/override     — clear manual override (Purchase Manager)
    POST /suppliers/{id}/rating/recompute      — trigger recompute from raw metrics

    GET  /suppliers/{id}/documents             — list documents
    POST /suppliers/{id}/documents             — add document
    DELETE /suppliers/{id}/documents/{doc_id}  — delete document

    GET  /suppliers/{id}/lead-times            — list lead times
    POST /suppliers/{id}/lead-times            — set lead time
    PUT  /suppliers/{id}/lead-times/{lt_id}    — update lead time

    POST /suppliers/{id}/preferred             — set preferred flag (Purchase Manager)
    GET  /suppliers/expiring-documents         — documents expiring within N days

Spec ref: specs/006-purchase-management/spec.md §23 Functional Requirements
Task: T064
"""

from __future__ import annotations

import logging
from typing import Any, NoReturn
from uuid import UUID

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from core.auth.dependencies import require_authenticated, require_user_id
from core.auth.interfaces import CurrentUser
from core.database.session import get_db
from core.exceptions.base import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from core.logging.setup import REQUEST_ID_CONTEXT
from core.schemas.response import ResponseMeta, StandardResponse
from core.utils.datetime import utcnow
from modules.platform_admin.exceptions import CapabilityNotEntitledError
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)
from modules.purchase.constants import (
    MODULE_NAME,
    MODULE_VERSION,
    PURCHASE_FLAG_BY_KEY,
    PURCHASE_SETTINGS_MANAGE_PERMISSION,
)
from modules.purchase.dependencies import (
    get_approval_service,
    get_bank_details_repo,
    get_cost_service,
    get_credit_limit_repo,
    get_gr_service,
    get_kpi_service,
    get_payment_terms_service,
    get_po_service,
    get_pr_service,
    get_purchase_feature_flag_service,
    get_purchase_policy_service,
    get_purchase_reason_code_service,
    get_report_export_service,
    get_report_service,
    get_rma_service,
    get_supplier_category_service,
    get_supplier_document_service,
    get_supplier_import_service,
    get_supplier_lead_time_repo,
    get_supplier_rating_service,
    get_supplier_service,
)
from modules.purchase.repositories.supplier_enrichment import (
    BankDetailsRepository,
    CreditLimitRepository,
    SupplierLeadTimeRepository,
)
from modules.purchase.schemas.approval import (
    ApprovalDelegateCreate,
    ApprovalDelegateRead,
    ApprovalDelegateUpdate,
    ApprovalLevelCreate,
    ApprovalLevelRead,
    ApprovalLevelUpdate,
    ApprovalMatrixCreate,
    ApprovalMatrixRead,
    ApprovalMatrixUpdate,
    ApprovalRecordRead,
    ApprovalStatusRead,
    ApproveAction,
    EmergencyBypassAction,
    MatrixRuleCreate,
    MatrixRuleRead,
    MatrixRuleUpdate,
    RejectAction,
    RouteForApprovalResult,
)
from modules.purchase.schemas.cost import (
    GRCostSummary,
    POCostSummary,
    PurchaseCostEntryRead,
)
from modules.purchase.schemas.goods_receipt import (
    GoodsReceiptCreate,
    GoodsReceiptListRead,
    GoodsReceiptRead,
    GoodsReceiptUpdate,
    GRLineCreate,
    GROpenQuantity,
)
from modules.purchase.schemas.master import (
    PaymentTermsCreate,
    PaymentTermsRead,
    PaymentTermsUpdate,
    PurchaseFeatureFlagRead,
    PurchaseFeatureFlagUpdate,
    PurchasePolicyRead,
    PurchasePolicyUpdate,
    PurchaseReasonCodeCreate,
    PurchaseReasonCodeRead,
    PurchaseReasonCodeUpdate,
    SupplierCategoryCreate,
    SupplierCategoryList,
    SupplierCategoryRead,
    SupplierCategoryUpdate,
)
from modules.purchase.schemas.purchase_order import (
    POAdditionalChargeCreate,
    POAdditionalChargeUpdate,
    POAmendRequest,
    POCancelRequest,
    POLineCreate,
    POLineUpdate,
    PurchaseOrderCreate,
    PurchaseOrderListRead,
    PurchaseOrderRead,
    PurchaseOrderUpdate,
)
from modules.purchase.schemas.purchase_request import (
    PRCancelRequest,
    PRLineCreate,
    PRLineRead,
    PRLineUpdate,
    PurchaseRequestCreate,
    PurchaseRequestListRead,
    PurchaseRequestRead,
    PurchaseRequestUpdate,
)
from modules.purchase.schemas.supplier import (
    BulkImportResult,
    SupplierActivateRequest,
    SupplierAddressCreate,
    SupplierAddressRead,
    SupplierAddressUpdate,
    SupplierArchiveRequest,
    SupplierBlockRequest,
    SupplierContactCreate,
    SupplierContactRead,
    SupplierContactUpdate,
    SupplierCreate,
    SupplierDeactivateRequest,
    SupplierList,
    SupplierReactivateRequest,
    SupplierRead,
    SupplierUpdate,
)
from modules.purchase.schemas.supplier_enrichment import (
    BankDetailsCreate,
    BankDetailsRead,
    BankDetailsUpdate,
    CreditLimitCreate,
    CreditLimitRead,
    ExpiringDocumentsResponse,
    SupplierDocumentCreate,
    SupplierDocumentRead,
    SupplierLeadTimeCreate,
    SupplierLeadTimeRead,
    SupplierLeadTimeUpdate,
    SupplierRatingManualOverride,
    SupplierRatingRead,
)
from modules.purchase.schemas.vendor_return import (
    ReturnLineCreate,
    VendorReturnCreate,
    VendorReturnListRead,
    VendorReturnRead,
    VendorReturnUpdate,
)
from modules.purchase.services.approval_service import ApprovalService
from modules.purchase.services.cost_service import CostService
from modules.purchase.services.feature_flag_service import PurchaseFeatureFlagService
from modules.purchase.services.gr_service import (
    GRImmutableError,
    GRInvalidPOStatusError,
    GROverReceiptError,
    GRService,
)
from modules.purchase.services.kpi_service import KPIService
from modules.purchase.services.master_data_service import (
    PaymentTermsService,
    PurchaseReasonCodeService,
    SupplierCategoryService,
)
from modules.purchase.services.permission_check import user_has_purchase_permission
from modules.purchase.services.po_service import (
    InvalidPOStatusTransitionError,
    POCancelBlockedError,
    POImmutableError,
    POMissingLinesError,
    POMissingSupplierError,
    POService,
)
from modules.purchase.services.policy_service import PurchasePolicyService
from modules.purchase.services.pr_service import (
    InvalidPRStatusTransitionError,
    PRMissingLinesError,
    PRNotConvertibleError,
    PRNotEditableError,
    PRService,
)
from modules.purchase.services.report_export_service import ReportExportService
from modules.purchase.services.report_service import ReportService
from modules.purchase.services.rma_service import (
    RMAImmutableError,
    RMAInvalidGRStatusError,
    RMAInvalidTransitionError,
    RMAReturnQuantityError,
    RMAService,
)
from modules.purchase.services.supplier_document_service import SupplierDocumentService
from modules.purchase.services.supplier_import_service import SupplierImportService
from modules.purchase.services.supplier_rating_service import SupplierRatingService
from modules.purchase.services.supplier_service import (
    InvalidSupplierTransitionError,
    SupplierService,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["purchase"])


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    summary="Purchase module health check",
    description="Returns module name, version, and status.",
)
async def purchase_health(
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
) -> dict[str, str]:
    """Purchase module liveness probe."""
    return {
        "module": MODULE_NAME,
        "version": MODULE_VERSION,
        "status": "healthy",
        "company_id": str(company_id),
    }


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------


@router.get(
    "/feature-flags",
    response_model=StandardResponse[list[PurchaseFeatureFlagRead]],
    summary="List all purchase feature flags",
)
async def list_feature_flags(
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    flag_svc: PurchaseFeatureFlagService = Depends(get_purchase_feature_flag_service),
) -> StandardResponse[list[PurchaseFeatureFlagRead]]:
    """Return all purchase feature flags with their effective state for this company."""
    flags = flag_svc.get_all(company_id=company_id)
    now = utcnow()
    return StandardResponse(
        data=[PurchaseFeatureFlagRead(**f) for f in flags],
        message="Purchase feature flags retrieved",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


@router.put(
    "/feature-flags/{flag_key}",
    response_model=StandardResponse[PurchaseFeatureFlagRead],
    summary="Update a purchase feature flag",
)
async def update_feature_flag(
    flag_key: str,
    body: PurchaseFeatureFlagUpdate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    flag_svc: PurchaseFeatureFlagService = Depends(get_purchase_feature_flag_service),
    db: Session = Depends(get_db),
) -> StandardResponse[PurchaseFeatureFlagRead]:
    """Enable or disable a purchase feature flag for this company."""
    # RBAC gap hardened (Epic 9A Phase 10, T140, plan.md §14): feature
    # flags can toggle module-wide behavior and had no permission check
    # beyond active tenant membership. Reuses the same
    # settings-management pattern already patched onto Accounting.
    if not user_has_purchase_permission(
        db,
        company_id,
        current_user.user_id,
        PURCHASE_SETTINGS_MANAGE_PERMISSION,
        user_roles=current_user.roles,
    ):
        raise ForbiddenException(
            message=(
                f"You do not have the '{PURCHASE_SETTINGS_MANAGE_PERMISSION}' "
                "permission required to perform this action."
            ),
            details={"permission_code": PURCHASE_SETTINGS_MANAGE_PERMISSION},
        )

    if flag_key not in PURCHASE_FLAG_BY_KEY:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown feature flag key: '{flag_key}'",
        )

    if body.is_enabled:
        # Entitlement ceiling at the mutation point (secondary guard,
        # FR-9A-185, plan.md §14) — a tenant cannot switch a module-grain
        # toggle ON beyond the Plan ceiling. Not the primary enforcement
        # point (that is the mount-level require_capability_entitled
        # dependency, plan.md §13.1) — this exists only so an out-of-
        # ceiling attempt fails loudly and immediately rather than
        # performing a write that would be silently ineffective at
        # runtime. Retained per plan.md §14 even though, for this
        # module-grain-only capability, the mount-level gate already
        # denies the whole request first in practice (verified) — plan.md
        # itself says removing this secondary check "would not create a
        # runtime bypass".
        entitlement_service = PlatformEntitlementService(
            db=db,
            plan_repo=PlanRepository(db),
            subscription_repo=SubscriptionRepository(db),
        )
        if not entitlement_service.is_within_plan_ceiling(
            company_id=company_id, capability_key="purchase"
        ):
            raise CapabilityNotEntitledError(
                message=(
                    "Cannot enable this feature: the 'purchase' capability "
                    "is not entitled under the current plan."
                ),
                details={"capability_key": "purchase", "flag_key": flag_key},
            )

    if body.is_enabled:
        flag_svc.enable(
            company_id=company_id,
            flag_key=flag_key,
            actor_id=current_user.user_id,
            description=body.description,
        )
    else:
        flag_svc.disable(
            company_id=company_id,
            flag_key=flag_key,
            actor_id=current_user.user_id,
            description=body.description,
        )

    # Return updated state
    all_flags = flag_svc.get_all(company_id=company_id)
    flag_data = next(f for f in all_flags if f["flag_key"] == flag_key)
    now = utcnow()
    return StandardResponse(
        data=PurchaseFeatureFlagRead(**flag_data),
        message="Feature flag updated",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


# ---------------------------------------------------------------------------
# Supplier Categories
# ---------------------------------------------------------------------------


@router.get(
    "/settings/categories",
    response_model=StandardResponse[list[SupplierCategoryList]],
    summary="List supplier categories",
)
async def list_supplier_categories(
    company_id: UUID = Path(..., description="Company identifier"),
    status_filter: str | None = Query(
        None, alias="status", description="Filter by status"
    ),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierCategoryService = Depends(get_supplier_category_service),
) -> StandardResponse[list[SupplierCategoryList]]:
    """Return all supplier categories for this company."""
    repo = svc._repo
    if status_filter:
        items = repo.get_by_status(company_id=company_id, status=status_filter)
    else:
        items_tuple = repo.list(company_id=company_id, limit=1000)
        items = items_tuple[0]

    now = utcnow()
    return StandardResponse(
        data=[SupplierCategoryList.model_validate(c) for c in items],
        message="Supplier categories retrieved",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


@router.post(
    "/settings/categories",
    response_model=StandardResponse[SupplierCategoryRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a supplier category",
)
async def create_supplier_category(
    body: SupplierCategoryCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierCategoryService = Depends(get_supplier_category_service),
) -> StandardResponse[SupplierCategoryRead]:
    """Create a new supplier category."""
    category = svc.create(
        company_id=company_id,
        code=body.code,
        name=body.name,
        parent_id=body.parent_id,
        description=body.description,
        actor_id=current_user.user_id,
    )
    now = utcnow()
    return StandardResponse(
        data=SupplierCategoryRead.model_validate(category),
        message="Supplier category created",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


@router.get(
    "/settings/categories/{category_id}",
    response_model=StandardResponse[SupplierCategoryRead],
    summary="Get a supplier category",
)
async def get_supplier_category(
    category_id: UUID,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierCategoryService = Depends(get_supplier_category_service),
) -> StandardResponse[SupplierCategoryRead]:
    """Return a single supplier category by ID."""
    category = svc._repo.get_by_id(id=category_id, company_id=company_id)
    now = utcnow()
    return StandardResponse(
        data=SupplierCategoryRead.model_validate(category),
        message="Supplier category retrieved",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


@router.put(
    "/settings/categories/{category_id}",
    response_model=StandardResponse[SupplierCategoryRead],
    summary="Update a supplier category",
)
async def update_supplier_category(
    category_id: UUID,
    body: SupplierCategoryUpdate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierCategoryService = Depends(get_supplier_category_service),
) -> StandardResponse[SupplierCategoryRead]:
    """Update a supplier category's mutable fields."""
    category = svc.update(
        category_id=category_id,
        company_id=company_id,
        name=body.name,
        description=body.description,
        actor_id=current_user.user_id,
    )
    now = utcnow()
    return StandardResponse(
        data=SupplierCategoryRead.model_validate(category),
        message="Supplier category updated",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


@router.delete(
    "/settings/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a supplier category",
)
async def delete_supplier_category(
    category_id: UUID,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierCategoryService = Depends(get_supplier_category_service),
) -> None:
    """Soft-delete a supplier category."""
    svc.delete(category_id=category_id, company_id=company_id)


# ---------------------------------------------------------------------------
# Payment Terms
# ---------------------------------------------------------------------------


@router.get(
    "/settings/payment-terms",
    response_model=StandardResponse[list[PaymentTermsRead]],
    summary="List payment terms",
)
async def list_payment_terms(
    company_id: UUID = Path(..., description="Company identifier"),
    active_only: bool = Query(True, description="Return only active payment terms"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PaymentTermsService = Depends(get_payment_terms_service),
) -> StandardResponse[list[PaymentTermsRead]]:
    """Return all payment terms for this company."""
    if active_only:
        items = svc._repo.get_active(company_id=company_id)
    else:
        items_tuple = svc._repo.list(company_id=company_id, limit=1000)
        items = items_tuple[0]

    now = utcnow()
    return StandardResponse(
        data=[PaymentTermsRead.model_validate(t) for t in items],
        message="Payment terms retrieved",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


@router.post(
    "/settings/payment-terms",
    response_model=StandardResponse[PaymentTermsRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create payment terms",
)
async def create_payment_terms(
    body: PaymentTermsCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PaymentTermsService = Depends(get_payment_terms_service),
) -> StandardResponse[PaymentTermsRead]:
    """Create new payment terms."""
    terms = svc.create(
        company_id=company_id,
        code=body.code,
        name=body.name,
        net_days=body.net_days,
        discount_days=body.discount_days,
        discount_percent=(
            float(body.discount_percent) if body.discount_percent is not None else None
        ),
        description=body.description,
        actor_id=current_user.user_id,
    )
    now = utcnow()
    return StandardResponse(
        data=PaymentTermsRead.model_validate(terms),
        message="Payment terms created",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


@router.get(
    "/settings/payment-terms/{terms_id}",
    response_model=StandardResponse[PaymentTermsRead],
    summary="Get payment terms",
)
async def get_payment_terms(
    terms_id: UUID,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PaymentTermsService = Depends(get_payment_terms_service),
) -> StandardResponse[PaymentTermsRead]:
    """Return a single payment terms record by ID."""
    terms = svc._repo.get_by_id(id=terms_id, company_id=company_id)
    now = utcnow()
    return StandardResponse(
        data=PaymentTermsRead.model_validate(terms),
        message="Payment terms retrieved",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


@router.put(
    "/settings/payment-terms/{terms_id}",
    response_model=StandardResponse[PaymentTermsRead],
    summary="Update payment terms",
)
async def update_payment_terms(
    terms_id: UUID,
    body: PaymentTermsUpdate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PaymentTermsService = Depends(get_payment_terms_service),
) -> StandardResponse[PaymentTermsRead]:
    """Update payment terms fields."""
    terms = svc.update(
        terms_id=terms_id,
        company_id=company_id,
        name=body.name,
        net_days=body.net_days,
        discount_days=body.discount_days,
        discount_percent=(
            float(body.discount_percent) if body.discount_percent is not None else None
        ),
        description=body.description,
        is_active=body.is_active,
    )
    now = utcnow()
    return StandardResponse(
        data=PaymentTermsRead.model_validate(terms),
        message="Payment terms updated",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


@router.delete(
    "/settings/payment-terms/{terms_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete payment terms",
)
async def delete_payment_terms(
    terms_id: UUID,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PaymentTermsService = Depends(get_payment_terms_service),
) -> None:
    """Soft-delete payment terms."""
    svc.delete(terms_id=terms_id, company_id=company_id)


# ---------------------------------------------------------------------------
# Reason Codes
# ---------------------------------------------------------------------------


@router.get(
    "/settings/reason-codes",
    response_model=StandardResponse[list[PurchaseReasonCodeRead]],
    summary="List purchase reason codes",
)
async def list_reason_codes(
    company_id: UUID = Path(..., description="Company identifier"),
    reason_type: str | None = Query(
        None, description="Filter by type: RETURN/CANCELLATION/REJECTION/GENERAL"
    ),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PurchaseReasonCodeService = Depends(get_purchase_reason_code_service),
) -> StandardResponse[list[PurchaseReasonCodeRead]]:
    """Return purchase reason codes for this company."""
    if reason_type:
        items = svc._repo.get_by_type(
            company_id=company_id, reason_type=reason_type.upper()
        )
    else:
        items_tuple = svc._repo.list(company_id=company_id, limit=1000)
        items = items_tuple[0]

    now = utcnow()
    return StandardResponse(
        data=[PurchaseReasonCodeRead.model_validate(r) for r in items],
        message="Reason codes retrieved",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


@router.post(
    "/settings/reason-codes",
    response_model=StandardResponse[PurchaseReasonCodeRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a purchase reason code",
)
async def create_reason_code(
    body: PurchaseReasonCodeCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PurchaseReasonCodeService = Depends(get_purchase_reason_code_service),
) -> StandardResponse[PurchaseReasonCodeRead]:
    """Create a new purchase reason code."""
    rc = svc.create(
        company_id=company_id,
        code=body.code,
        name=body.name,
        reason_type=body.reason_type,
        actor_id=current_user.user_id,
    )
    now = utcnow()
    return StandardResponse(
        data=PurchaseReasonCodeRead.model_validate(rc),
        message="Reason code created",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


@router.get(
    "/settings/reason-codes/{code_id}",
    response_model=StandardResponse[PurchaseReasonCodeRead],
    summary="Get a purchase reason code",
)
async def get_reason_code(
    code_id: UUID,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PurchaseReasonCodeService = Depends(get_purchase_reason_code_service),
) -> StandardResponse[PurchaseReasonCodeRead]:
    """Return a single reason code by ID."""
    rc = svc._repo.get_by_id(id=code_id, company_id=company_id)
    now = utcnow()
    return StandardResponse(
        data=PurchaseReasonCodeRead.model_validate(rc),
        message="Reason code retrieved",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


@router.put(
    "/settings/reason-codes/{code_id}",
    response_model=StandardResponse[PurchaseReasonCodeRead],
    summary="Update a purchase reason code",
)
async def update_reason_code(
    code_id: UUID,
    body: PurchaseReasonCodeUpdate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PurchaseReasonCodeService = Depends(get_purchase_reason_code_service),
) -> StandardResponse[PurchaseReasonCodeRead]:
    """Update a reason code."""
    rc = svc.update(
        code_id=code_id,
        company_id=company_id,
        name=body.name,
        is_active=body.is_active,
    )
    now = utcnow()
    return StandardResponse(
        data=PurchaseReasonCodeRead.model_validate(rc),
        message="Reason code updated",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


@router.delete(
    "/settings/reason-codes/{code_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a purchase reason code",
)
async def delete_reason_code(
    code_id: UUID,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PurchaseReasonCodeService = Depends(get_purchase_reason_code_service),
) -> None:
    """Soft-delete a reason code."""
    svc.delete(code_id=code_id, company_id=company_id)


# ---------------------------------------------------------------------------
# Purchase Policy
# ---------------------------------------------------------------------------


@router.get(
    "/settings/policy",
    response_model=StandardResponse[PurchasePolicyRead],
    summary="Get purchase policy",
)
async def get_purchase_policy(
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PurchasePolicyService = Depends(get_purchase_policy_service),
) -> StandardResponse[PurchasePolicyRead]:
    """Return the procurement policy for this company (creates with defaults if not yet configured)."""
    policy = svc.get_or_create(company_id=company_id, actor_id=current_user.user_id)
    now = utcnow()
    return StandardResponse(
        data=PurchasePolicyRead.model_validate(policy),
        message="Purchase policy retrieved",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


@router.put(
    "/settings/policy",
    response_model=StandardResponse[PurchasePolicyRead],
    summary="Update purchase policy",
)
async def update_purchase_policy(
    body: PurchasePolicyUpdate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PurchasePolicyService = Depends(get_purchase_policy_service),
) -> StandardResponse[PurchasePolicyRead]:
    """Update procurement policy settings for this company."""
    policy = svc.update(
        company_id=company_id,
        actor_id=current_user.user_id,
        direct_po_allowed=body.direct_po_allowed,
        pr_approval_required=body.pr_approval_required,
        po_approval_required=body.po_approval_required,
        over_receipt_policy=body.over_receipt_policy,
        credit_limit_mode=body.credit_limit_mode,
        ppv_alert_threshold_percent=body.ppv_alert_threshold_percent,
        supplier_rating_window=body.supplier_rating_window,
    )
    now = utcnow()
    return StandardResponse(
        data=PurchasePolicyRead.model_validate(policy),
        message="Purchase policy updated",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


# ===========================================================================
# Phase 1: Supplier aggregate endpoints
# ===========================================================================


def _raise_transition_error(exc: InvalidSupplierTransitionError) -> None:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(exc),
    )


# ---------------------------------------------------------------------------
# Suppliers — CRUD + Search
# ---------------------------------------------------------------------------


@router.get(
    "/suppliers",
    response_model=StandardResponse[list[SupplierList]],
    summary="List / search suppliers",
)
async def list_suppliers(
    company_id: UUID = Path(..., description="Company identifier"),
    query: str | None = Query(None, description="FTS search query"),
    status_filter: str | None = Query(None, alias="status"),
    category_id: UUID | None = Query(None),
    supplier_type: str | None = Query(None),
    is_preferred: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[list[SupplierList]]:
    """Return a paginated, filtered list of suppliers for this company."""
    items, total = svc.search(
        company_id=company_id,
        query=query,
        status=status_filter,
        category_id=category_id,
        supplier_type=supplier_type,
        is_preferred=is_preferred,
        skip=skip,
        limit=limit,
    )
    now = utcnow()
    return StandardResponse(
        data=[SupplierList.model_validate(s) for s in items],
        message=f"{total} supplier(s) found",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/suppliers",
    response_model=StandardResponse[SupplierRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a supplier",
)
async def create_supplier(
    body: SupplierCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[SupplierRead]:
    """Create a new supplier in DRAFT status."""
    supplier = svc.create(
        company_id=company_id,
        supplier_code=body.supplier_code,
        legal_name=body.legal_name,
        supplier_type=body.supplier_type,
        vendor_code=body.vendor_code,
        trading_name=body.trading_name,
        category_id=body.category_id,
        payment_terms_id=body.payment_terms_id,
        currency_code=body.currency_code,
        tax_registration_number=body.tax_registration_number,
        tax_category=body.tax_category,
        tax_region=body.tax_region,
        website=body.website,
        notes=body.notes,
        lead_time_days=body.lead_time_days,
        actor_id=current_user.user_id,
    )
    now = utcnow()
    return StandardResponse(
        data=SupplierRead.model_validate(supplier),
        message="Supplier created",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/suppliers/expiring-documents",
    response_model=StandardResponse[ExpiringDocumentsResponse],
    summary="Get documents expiring within N days",
)
async def expiring_documents(
    company_id: UUID = Path(..., description="Company identifier"),
    days: int = Query(30, ge=1, le=365, description="Alert window in days"),
    current_user: CurrentUser = Depends(require_authenticated),
    doc_svc: SupplierDocumentService = Depends(get_supplier_document_service),
) -> StandardResponse[ExpiringDocumentsResponse]:
    """Return all compliance documents expiring within the given number of days."""
    result = doc_svc.check_expiring_documents(company_id=company_id, alert_days=days)
    return StandardResponse(
        data=result, message=f"{result.total} expiring document(s) found", meta=_meta()
    )


@router.get(
    "/suppliers/{supplier_id}",
    response_model=StandardResponse[SupplierRead],
    summary="Get a supplier",
)
async def get_supplier(
    supplier_id: UUID,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[SupplierRead]:
    """Return a single supplier by ID."""
    supplier = svc._repo.get_by_id(id=supplier_id, company_id=company_id)
    now = utcnow()
    return StandardResponse(
        data=SupplierRead.model_validate(supplier),
        message="Supplier retrieved",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/suppliers/{supplier_id}",
    response_model=StandardResponse[SupplierRead],
    summary="Update a supplier",
)
async def update_supplier(
    supplier_id: UUID,
    body: SupplierUpdate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[SupplierRead]:
    """Update a supplier's mutable fields."""
    supplier = svc.update(
        supplier_id=supplier_id,
        company_id=company_id,
        vendor_code=body.vendor_code,
        legal_name=body.legal_name,
        trading_name=body.trading_name,
        supplier_type=body.supplier_type,
        category_id=body.category_id,
        payment_terms_id=body.payment_terms_id,
        currency_code=body.currency_code,
        tax_registration_number=body.tax_registration_number,
        tax_category=body.tax_category,
        tax_region=body.tax_region,
        website=body.website,
        notes=body.notes,
        lead_time_days=body.lead_time_days,
        actor_id=current_user.user_id,
    )
    now = utcnow()
    return StandardResponse(
        data=SupplierRead.model_validate(supplier),
        message="Supplier updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------


@router.post(
    "/suppliers/{supplier_id}/activate",
    response_model=StandardResponse[SupplierRead],
    summary="Activate a supplier",
)
async def activate_supplier(
    supplier_id: UUID,
    body: SupplierActivateRequest,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[SupplierRead]:
    """Transition a DRAFT or INACTIVE supplier to ACTIVE."""
    try:
        supplier = svc.activate(
            supplier_id=supplier_id,
            company_id=company_id,
            actor_id=current_user.user_id,
        )
    except InvalidSupplierTransitionError as exc:
        _raise_transition_error(exc)
    now = utcnow()
    return StandardResponse(
        data=SupplierRead.model_validate(supplier),
        message="Supplier activated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/suppliers/{supplier_id}/deactivate",
    response_model=StandardResponse[SupplierRead],
    summary="Deactivate a supplier",
)
async def deactivate_supplier(
    supplier_id: UUID,
    body: SupplierDeactivateRequest,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[SupplierRead]:
    """Transition an ACTIVE supplier to INACTIVE."""
    try:
        supplier = svc.deactivate(
            supplier_id=supplier_id,
            company_id=company_id,
            reason=body.reason,
            actor_id=current_user.user_id,
        )
    except InvalidSupplierTransitionError as exc:
        _raise_transition_error(exc)
    now = utcnow()
    return StandardResponse(
        data=SupplierRead.model_validate(supplier),
        message="Supplier deactivated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/suppliers/{supplier_id}/block",
    response_model=StandardResponse[SupplierRead],
    summary="Block a supplier",
)
async def block_supplier(
    supplier_id: UUID,
    body: SupplierBlockRequest,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[SupplierRead]:
    """Transition an ACTIVE supplier to BLOCKED (reason mandatory)."""
    try:
        supplier = svc.block(
            supplier_id=supplier_id,
            company_id=company_id,
            reason=body.reason,
            actor_id=current_user.user_id,
        )
    except InvalidSupplierTransitionError as exc:
        _raise_transition_error(exc)
    now = utcnow()
    return StandardResponse(
        data=SupplierRead.model_validate(supplier),
        message="Supplier blocked",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/suppliers/{supplier_id}/reactivate",
    response_model=StandardResponse[SupplierRead],
    summary="Reactivate a supplier",
)
async def reactivate_supplier(
    supplier_id: UUID,
    body: SupplierReactivateRequest,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[SupplierRead]:
    """Transition a BLOCKED or INACTIVE supplier back to ACTIVE."""
    try:
        supplier = svc.reactivate(
            supplier_id=supplier_id,
            company_id=company_id,
            reason=body.reason,
            actor_id=current_user.user_id,
        )
    except InvalidSupplierTransitionError as exc:
        _raise_transition_error(exc)
    now = utcnow()
    return StandardResponse(
        data=SupplierRead.model_validate(supplier),
        message="Supplier reactivated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/suppliers/{supplier_id}/archive",
    response_model=StandardResponse[SupplierRead],
    summary="Archive a supplier",
)
async def archive_supplier(
    supplier_id: UUID,
    body: SupplierArchiveRequest,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[SupplierRead]:
    """Transition an ACTIVE or INACTIVE supplier to ARCHIVED."""
    try:
        # In Phase 1 the open PO check is not yet available; passes False
        supplier = svc.archive(
            supplier_id=supplier_id,
            company_id=company_id,
            actor_id=current_user.user_id,
            has_open_pos=False,
        )
    except (InvalidSupplierTransitionError, Exception) as exc:
        if isinstance(exc, InvalidSupplierTransitionError):
            _raise_transition_error(exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    now = utcnow()
    return StandardResponse(
        data=SupplierRead.model_validate(supplier),
        message="Supplier archived",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Supplier Contacts
# ---------------------------------------------------------------------------


@router.get(
    "/suppliers/{supplier_id}/contacts",
    response_model=StandardResponse[list[SupplierContactRead]],
    summary="List supplier contacts",
)
async def list_supplier_contacts(
    supplier_id: UUID,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[list[SupplierContactRead]]:
    contacts = svc._contact_repo.get_for_supplier(
        company_id=company_id, supplier_id=supplier_id
    )
    now = utcnow()
    return StandardResponse(
        data=[SupplierContactRead.model_validate(c) for c in contacts],
        message="Contacts retrieved",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/suppliers/{supplier_id}/contacts",
    response_model=StandardResponse[SupplierContactRead],
    status_code=status.HTTP_201_CREATED,
    summary="Add a supplier contact",
)
async def add_supplier_contact(
    supplier_id: UUID,
    body: SupplierContactCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[SupplierContactRead]:
    contact = svc.add_contact(
        supplier_id=supplier_id,
        company_id=company_id,
        first_name=body.first_name,
        last_name=body.last_name,
        role=body.role,
        email=body.email,
        phone=body.phone,
        mobile=body.mobile,
        is_primary=body.is_primary,
        actor_id=current_user.user_id,
    )
    now = utcnow()
    return StandardResponse(
        data=SupplierContactRead.model_validate(contact),
        message="Contact added",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/suppliers/{supplier_id}/contacts/{contact_id}",
    response_model=StandardResponse[SupplierContactRead],
    summary="Update a supplier contact",
)
async def update_supplier_contact(
    supplier_id: UUID,
    contact_id: UUID,
    body: SupplierContactUpdate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[SupplierContactRead]:
    contact = svc.update_contact(
        contact_id=contact_id,
        supplier_id=supplier_id,
        company_id=company_id,
        first_name=body.first_name,
        last_name=body.last_name,
        role=body.role,
        email=body.email,
        phone=body.phone,
        mobile=body.mobile,
        is_primary=body.is_primary,
        actor_id=current_user.user_id,
    )
    now = utcnow()
    return StandardResponse(
        data=SupplierContactRead.model_validate(contact),
        message="Contact updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.delete(
    "/suppliers/{supplier_id}/contacts/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a supplier contact",
)
async def remove_supplier_contact(
    supplier_id: UUID,
    contact_id: UUID,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> None:
    svc.remove_contact(
        contact_id=contact_id, supplier_id=supplier_id, company_id=company_id
    )


@router.post(
    "/suppliers/{supplier_id}/contacts/{contact_id}/set-primary",
    response_model=StandardResponse[SupplierContactRead],
    summary="Set primary contact",
)
async def set_primary_contact(
    supplier_id: UUID,
    contact_id: UUID,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[SupplierContactRead]:
    contact = svc.set_primary_contact(
        contact_id=contact_id, supplier_id=supplier_id, company_id=company_id
    )
    now = utcnow()
    return StandardResponse(
        data=SupplierContactRead.model_validate(contact),
        message="Primary contact updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Supplier Addresses
# ---------------------------------------------------------------------------


@router.get(
    "/suppliers/{supplier_id}/addresses",
    response_model=StandardResponse[list[SupplierAddressRead]],
    summary="List supplier addresses",
)
async def list_supplier_addresses(
    supplier_id: UUID,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[list[SupplierAddressRead]]:
    addresses = svc._address_repo.get_for_supplier(
        company_id=company_id, supplier_id=supplier_id
    )
    now = utcnow()
    return StandardResponse(
        data=[SupplierAddressRead.model_validate(a) for a in addresses],
        message="Addresses retrieved",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/suppliers/{supplier_id}/addresses",
    response_model=StandardResponse[SupplierAddressRead],
    status_code=status.HTTP_201_CREATED,
    summary="Add a supplier address",
)
async def add_supplier_address(
    supplier_id: UUID,
    body: SupplierAddressCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[SupplierAddressRead]:
    address = svc.add_address(
        supplier_id=supplier_id,
        company_id=company_id,
        address_type=body.address_type,
        address_line_1=body.address_line_1,
        city=body.city,
        country_code=body.country_code,
        address_line_2=body.address_line_2,
        state=body.state,
        postal_code=body.postal_code,
        is_default=body.is_default,
        actor_id=current_user.user_id,
    )
    now = utcnow()
    return StandardResponse(
        data=SupplierAddressRead.model_validate(address),
        message="Address added",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/suppliers/{supplier_id}/addresses/{address_id}",
    response_model=StandardResponse[SupplierAddressRead],
    summary="Update a supplier address",
)
async def update_supplier_address(
    supplier_id: UUID,
    address_id: UUID,
    body: SupplierAddressUpdate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[SupplierAddressRead]:
    address = svc.update_address(
        address_id=address_id,
        supplier_id=supplier_id,
        company_id=company_id,
        address_line_1=body.address_line_1,
        address_line_2=body.address_line_2,
        city=body.city,
        state=body.state,
        postal_code=body.postal_code,
        country_code=body.country_code,
        is_default=body.is_default,
        actor_id=current_user.user_id,
    )
    now = utcnow()
    return StandardResponse(
        data=SupplierAddressRead.model_validate(address),
        message="Address updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.delete(
    "/suppliers/{supplier_id}/addresses/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a supplier address",
)
async def remove_supplier_address(
    supplier_id: UUID,
    address_id: UUID,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> None:
    svc.remove_address(
        address_id=address_id, supplier_id=supplier_id, company_id=company_id
    )


@router.post(
    "/suppliers/{supplier_id}/addresses/{address_id}/set-default",
    response_model=StandardResponse[SupplierAddressRead],
    summary="Set default address",
)
async def set_default_address(
    supplier_id: UUID,
    address_id: UUID,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[SupplierAddressRead]:
    address = svc.set_default_address(
        address_id=address_id, supplier_id=supplier_id, company_id=company_id
    )
    now = utcnow()
    return StandardResponse(
        data=SupplierAddressRead.model_validate(address),
        message="Default address updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Bulk Import
# ---------------------------------------------------------------------------


@router.post(
    "/suppliers/import",
    response_model=StandardResponse[BulkImportResult],
    summary="Bulk import suppliers from CSV",
)
async def bulk_import_suppliers(
    company_id: UUID = Path(..., description="Company identifier"),
    file: UploadFile = File(..., description="CSV file with supplier rows"),
    current_user: CurrentUser = Depends(require_authenticated),
    import_svc: SupplierImportService = Depends(get_supplier_import_service),
) -> StandardResponse[BulkImportResult]:
    """Import suppliers in bulk from a CSV file (up to 10,000 rows).

    Required columns: supplier_code, legal_name
    Optional columns: trading_name, supplier_type, currency_code,
                      website, notes, lead_time_days, tax_registration_number
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported.",
        )

    csv_bytes = await file.read()
    result = import_svc.import_from_csv(
        company_id=company_id,
        csv_bytes=csv_bytes,
        actor_id=current_user.user_id,
    )
    now = utcnow()
    return StandardResponse(
        data=result,
        message=f"Import complete: {result.created} created, {result.skipped} skipped, {result.failed} failed",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# =============================================================================
# Phase 2 — Supplier Enrichment Endpoints
# =============================================================================

# ---------------------------------------------------------------------------
# Credit Limit
# ---------------------------------------------------------------------------


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow())


@router.get(
    "/suppliers/{supplier_id}/credit-limit",
    response_model=StandardResponse[CreditLimitRead],
    summary="Get supplier credit limit",
)
async def get_credit_limit(
    company_id: UUID = Path(..., description="Company identifier"),
    supplier_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    repo: CreditLimitRepository = Depends(get_credit_limit_repo),
) -> StandardResponse[CreditLimitRead]:
    """Return the credit limit for a supplier."""
    cl = repo.get_for_supplier(company_id=company_id, supplier_id=supplier_id)
    if cl is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No credit limit set for this supplier",
        )
    return StandardResponse(
        data=CreditLimitRead.model_validate(cl),
        message="Credit limit retrieved",
        meta=_meta(),
    )


@router.put(
    "/suppliers/{supplier_id}/credit-limit",
    response_model=StandardResponse[CreditLimitRead],
    summary="Set or update supplier credit limit",
)
async def set_credit_limit(
    body: CreditLimitCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    supplier_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    repo: CreditLimitRepository = Depends(get_credit_limit_repo),
) -> StandardResponse[CreditLimitRead]:
    """Create or replace the credit limit for a supplier."""
    from modules.purchase.models.supplier_enrichment import CreditLimit

    cl = repo.get_for_supplier(company_id=company_id, supplier_id=supplier_id)
    if cl is None:
        cl = CreditLimit(
            company_id=company_id,
            supplier_id=str(supplier_id),
            credit_limit_amount=body.credit_limit_amount,
            currency_code=body.currency_code,
            enforcement_mode=body.enforcement_mode,
            created_by=current_user.user_id,
        )
        repo.db.add(cl)
    else:
        cl.credit_limit_amount = body.credit_limit_amount
        cl.currency_code = body.currency_code
        cl.enforcement_mode = body.enforcement_mode
    repo.db.commit()
    repo.db.refresh(cl)
    return StandardResponse(
        data=CreditLimitRead.model_validate(cl),
        message="Credit limit updated",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Bank Details (Finance Manager restricted)
# ---------------------------------------------------------------------------


@router.get(
    "/suppliers/{supplier_id}/bank-details",
    response_model=StandardResponse[list[BankDetailsRead]],
    summary="List supplier bank details (Finance Manager only)",
)
async def list_bank_details(
    company_id: UUID = Path(..., description="Company identifier"),
    supplier_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    repo: BankDetailsRepository = Depends(get_bank_details_repo),
) -> StandardResponse[list[BankDetailsRead]]:
    """Return all bank detail records for a supplier. Restricted to Finance Manager role."""
    _require_finance_manager(current_user)
    items = repo.get_for_supplier(company_id=company_id, supplier_id=supplier_id)
    return StandardResponse(
        data=[BankDetailsRead.model_validate(b) for b in items],
        message="Bank details retrieved",
        meta=_meta(),
    )


@router.post(
    "/suppliers/{supplier_id}/bank-details",
    response_model=StandardResponse[BankDetailsRead],
    status_code=status.HTTP_201_CREATED,
    summary="Add bank details to a supplier (Finance Manager only)",
)
async def add_bank_details(
    body: BankDetailsCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    supplier_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    repo: BankDetailsRepository = Depends(get_bank_details_repo),
) -> StandardResponse[BankDetailsRead]:
    """Add a bank detail record to a supplier. Finance Manager role required."""
    _require_finance_manager(current_user)
    from modules.purchase.models.supplier_enrichment import BankDetails

    if body.is_primary:
        repo.clear_primary(company_id=company_id, supplier_id=supplier_id)

    bd = BankDetails(
        company_id=company_id,
        supplier_id=str(supplier_id),
        bank_name=body.bank_name,
        account_name=body.account_name,
        account_number=body.account_number,
        iban=body.iban,
        swift_bic=body.swift_bic,
        routing_number=body.routing_number,
        bank_country=body.bank_country,
        currency_code=body.currency_code,
        is_primary=body.is_primary,
        created_by=current_user.user_id,
    )
    repo.db.add(bd)
    repo.db.commit()
    repo.db.refresh(bd)
    return StandardResponse(
        data=BankDetailsRead.model_validate(bd),
        message="Bank details added",
        meta=_meta(),
    )


@router.put(
    "/suppliers/{supplier_id}/bank-details/{bd_id}",
    response_model=StandardResponse[BankDetailsRead],
    summary="Update bank details (Finance Manager only)",
)
async def update_bank_details(
    body: BankDetailsUpdate,
    company_id: UUID = Path(..., description="Company identifier"),
    supplier_id: UUID = Path(...),
    bd_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    repo: BankDetailsRepository = Depends(get_bank_details_repo),
) -> StandardResponse[BankDetailsRead]:
    """Update a bank detail record. Finance Manager role required."""
    _require_finance_manager(current_user)
    bd = repo.get_by_id_or_none(id=bd_id, company_id=company_id)
    if bd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bank detail not found"
        )

    if body.bank_name is not None:
        bd.bank_name = body.bank_name
    if body.account_name is not None:
        bd.account_name = body.account_name
    if body.account_number is not None:
        bd.account_number = body.account_number
    if body.iban is not None:
        bd.iban = body.iban
    if body.swift_bic is not None:
        bd.swift_bic = body.swift_bic
    if body.routing_number is not None:
        bd.routing_number = body.routing_number
    if body.bank_country is not None:
        bd.bank_country = body.bank_country
    if body.currency_code is not None:
        bd.currency_code = body.currency_code
    if body.is_primary is not None:
        if body.is_primary:
            repo.clear_primary(company_id=company_id, supplier_id=supplier_id)
        bd.is_primary = body.is_primary

    repo.db.commit()
    repo.db.refresh(bd)
    return StandardResponse(
        data=BankDetailsRead.model_validate(bd),
        message="Bank details updated",
        meta=_meta(),
    )


@router.delete(
    "/suppliers/{supplier_id}/bank-details/{bd_id}",
    response_model=StandardResponse[dict[str, Any]],
    summary="Delete bank details (Finance Manager only)",
)
async def delete_bank_details(
    company_id: UUID = Path(..., description="Company identifier"),
    supplier_id: UUID = Path(...),
    bd_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    repo: BankDetailsRepository = Depends(get_bank_details_repo),
) -> StandardResponse[dict[str, Any]]:
    """Soft-delete a bank detail record. Finance Manager role required."""
    _require_finance_manager(current_user)
    from core.utils.datetime import utcnow as _now

    bd = repo.get_by_id_or_none(id=bd_id, company_id=company_id)
    if bd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bank detail not found"
        )
    bd.is_deleted = True
    bd.deleted_at = _now()
    repo.db.commit()
    return StandardResponse(data={}, message="Bank details deleted", meta=_meta())


# ---------------------------------------------------------------------------
# Supplier Rating
# ---------------------------------------------------------------------------


@router.get(
    "/suppliers/{supplier_id}/rating",
    response_model=StandardResponse[SupplierRatingRead],
    summary="Get supplier rating",
)
async def get_supplier_rating(
    company_id: UUID = Path(..., description="Company identifier"),
    supplier_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    rating_svc: SupplierRatingService = Depends(get_supplier_rating_service),
) -> StandardResponse[SupplierRatingRead]:
    """Return the current rating record for a supplier."""
    rating = rating_svc.get_rating(company_id=company_id, supplier_id=supplier_id)
    if rating is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No rating record for this supplier",
        )
    return StandardResponse(
        data=SupplierRatingRead.model_validate(rating),
        message="Rating retrieved",
        meta=_meta(),
    )


@router.post(
    "/suppliers/{supplier_id}/rating/recompute",
    response_model=StandardResponse[SupplierRatingRead],
    summary="Trigger rating recompute from raw metrics",
)
async def recompute_supplier_rating(
    body: dict[str, Any],
    company_id: UUID = Path(..., description="Company identifier"),
    supplier_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    rating_svc: SupplierRatingService = Depends(get_supplier_rating_service),
) -> StandardResponse[SupplierRatingRead]:
    """Recompute supplier rating from provided on_time_rate, fill_rate, rejection_rate metrics."""
    from decimal import Decimal as D  # noqa: N817

    on_time = D(str(body.get("on_time_rate", 0)))
    fill = D(str(body.get("fill_rate", 0)))
    rejection = D(str(body.get("rejection_rate", 0)))
    gr_count = int(body.get("gr_count_window", 0))

    rating = rating_svc.upsert_rating(
        company_id=company_id,
        supplier_id=supplier_id,
        on_time_rate=on_time,
        fill_rate=fill,
        rejection_rate=rejection,
        gr_count_window=gr_count,
        actor_id=current_user.user_id,
    )
    rating_svc.db.commit()
    rating_svc.db.refresh(rating)
    return StandardResponse(
        data=SupplierRatingRead.model_validate(rating),
        message="Rating recomputed",
        meta=_meta(),
    )


@router.post(
    "/suppliers/{supplier_id}/rating/override",
    response_model=StandardResponse[SupplierRatingRead],
    summary="Set manual rating override (Purchase Manager only)",
)
async def override_supplier_rating(
    body: SupplierRatingManualOverride,
    company_id: UUID = Path(..., description="Company identifier"),
    supplier_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    rating_svc: SupplierRatingService = Depends(get_supplier_rating_service),
) -> StandardResponse[SupplierRatingRead]:
    """Apply a manual rating override (Purchase Manager role required)."""
    rating = rating_svc.set_manual_override(
        company_id=company_id,
        supplier_id=supplier_id,
        override_score=body.override_score,
        override_reason=body.override_reason,
        actor_id=require_user_id(current_user),
    )
    rating_svc.db.commit()
    rating_svc.db.refresh(rating)
    return StandardResponse(
        data=SupplierRatingRead.model_validate(rating),
        message="Rating override applied",
        meta=_meta(),
    )


@router.delete(
    "/suppliers/{supplier_id}/rating/override",
    response_model=StandardResponse[SupplierRatingRead],
    summary="Clear manual rating override (Purchase Manager only)",
)
async def clear_rating_override(
    company_id: UUID = Path(..., description="Company identifier"),
    supplier_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    rating_svc: SupplierRatingService = Depends(get_supplier_rating_service),
) -> StandardResponse[SupplierRatingRead]:
    """Clear the manual rating override and restore the computed score."""
    try:
        rating = rating_svc.clear_manual_override(
            company_id=company_id,
            supplier_id=supplier_id,
            actor_id=require_user_id(current_user),
        )
        rating_svc.db.commit()
        rating_svc.db.refresh(rating)
        return StandardResponse(
            data=SupplierRatingRead.model_validate(rating),
            message="Override cleared",
            meta=_meta(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------------------------------------------------------------------
# Supplier Documents
# ---------------------------------------------------------------------------


@router.get(
    "/suppliers/{supplier_id}/documents",
    response_model=StandardResponse[list[SupplierDocumentRead]],
    summary="List supplier compliance documents",
)
async def list_supplier_documents(
    company_id: UUID = Path(..., description="Company identifier"),
    supplier_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    doc_svc: SupplierDocumentService = Depends(get_supplier_document_service),
) -> StandardResponse[list[SupplierDocumentRead]]:
    """Return all active compliance documents for a supplier."""
    docs = doc_svc.list_documents(company_id=company_id, supplier_id=supplier_id)
    return StandardResponse(
        data=[SupplierDocumentRead.model_validate(d) for d in docs],
        message="Documents retrieved",
        meta=_meta(),
    )


@router.post(
    "/suppliers/{supplier_id}/documents",
    response_model=StandardResponse[SupplierDocumentRead],
    status_code=status.HTTP_201_CREATED,
    summary="Add compliance document to supplier",
)
async def add_supplier_document(
    body: SupplierDocumentCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    supplier_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    doc_svc: SupplierDocumentService = Depends(get_supplier_document_service),
) -> StandardResponse[SupplierDocumentRead]:
    """Attach a compliance document to a supplier."""
    doc = doc_svc.add_document(
        company_id=company_id,
        supplier_id=supplier_id,
        document_type=body.document_type,
        document_number=body.document_number,
        issue_date=body.issue_date,
        expiry_date=body.expiry_date,
        file_url=body.file_url,
        actor_id=require_user_id(current_user),
    )
    doc_svc.db.commit()
    doc_svc.db.refresh(doc)
    return StandardResponse(
        data=SupplierDocumentRead.model_validate(doc),
        message="Document added",
        meta=_meta(),
    )


@router.delete(
    "/suppliers/{supplier_id}/documents/{doc_id}",
    response_model=StandardResponse[dict[str, Any]],
    summary="Delete a supplier compliance document",
)
async def delete_supplier_document(
    company_id: UUID = Path(..., description="Company identifier"),
    supplier_id: UUID = Path(...),
    doc_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    doc_svc: SupplierDocumentService = Depends(get_supplier_document_service),
) -> StandardResponse[dict[str, Any]]:
    """Soft-delete a supplier compliance document."""
    try:
        doc_svc.delete_document(
            company_id=company_id,
            supplier_id=supplier_id,
            document_id=doc_id,
            actor_id=require_user_id(current_user),
        )
        doc_svc.db.commit()
        return StandardResponse(data={}, message="Document deleted", meta=_meta())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------------------------------------------------------------------
# Lead Times
# ---------------------------------------------------------------------------


@router.get(
    "/suppliers/{supplier_id}/lead-times",
    response_model=StandardResponse[list[SupplierLeadTimeRead]],
    summary="List supplier lead times",
)
async def list_supplier_lead_times(
    company_id: UUID = Path(..., description="Company identifier"),
    supplier_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    repo: SupplierLeadTimeRepository = Depends(get_supplier_lead_time_repo),
) -> StandardResponse[list[SupplierLeadTimeRead]]:
    """Return all lead time records for a supplier."""
    items = repo.get_for_supplier(company_id=company_id, supplier_id=supplier_id)
    return StandardResponse(
        data=[SupplierLeadTimeRead.model_validate(lt) for lt in items],
        message="Lead times retrieved",
        meta=_meta(),
    )


@router.post(
    "/suppliers/{supplier_id}/lead-times",
    response_model=StandardResponse[SupplierLeadTimeRead],
    status_code=status.HTTP_201_CREATED,
    summary="Set supplier lead time",
)
async def set_supplier_lead_time(
    body: SupplierLeadTimeCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    supplier_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    repo: SupplierLeadTimeRepository = Depends(get_supplier_lead_time_repo),
) -> StandardResponse[SupplierLeadTimeRead]:
    """Create or update a lead time entry for a supplier."""
    from modules.purchase.models.supplier_enrichment import SupplierLeadTime

    existing = repo.get_for_supplier_product(
        company_id=company_id,
        supplier_id=supplier_id,
        product_id=body.product_id,
    )
    if existing is not None:
        existing.lead_time_days = body.lead_time_days
        existing.notes = body.notes
        repo.db.commit()
        repo.db.refresh(existing)
        return StandardResponse(
            data=SupplierLeadTimeRead.model_validate(existing),
            message="Lead time updated",
            meta=_meta(),
        )

    lt = SupplierLeadTime(
        company_id=company_id,
        supplier_id=str(supplier_id),
        product_id=str(body.product_id) if body.product_id else None,
        lead_time_days=body.lead_time_days,
        notes=body.notes,
        created_by=current_user.user_id,
    )
    repo.db.add(lt)
    repo.db.commit()
    repo.db.refresh(lt)
    return StandardResponse(
        data=SupplierLeadTimeRead.model_validate(lt),
        message="Lead time set",
        meta=_meta(),
    )


@router.put(
    "/suppliers/{supplier_id}/lead-times/{lt_id}",
    response_model=StandardResponse[SupplierLeadTimeRead],
    summary="Update a supplier lead time",
)
async def update_supplier_lead_time(
    body: SupplierLeadTimeUpdate,
    company_id: UUID = Path(..., description="Company identifier"),
    supplier_id: UUID = Path(...),
    lt_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    repo: SupplierLeadTimeRepository = Depends(get_supplier_lead_time_repo),
) -> StandardResponse[SupplierLeadTimeRead]:
    """Update an existing lead time record."""
    lt = repo.get_by_id_or_none(id=lt_id, company_id=company_id)
    if lt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lead time not found"
        )
    if body.lead_time_days is not None:
        lt.lead_time_days = body.lead_time_days
    if body.notes is not None:
        lt.notes = body.notes
    repo.db.commit()
    repo.db.refresh(lt)
    return StandardResponse(
        data=SupplierLeadTimeRead.model_validate(lt),
        message="Lead time updated",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Preferred supplier
# ---------------------------------------------------------------------------


@router.post(
    "/suppliers/{supplier_id}/preferred",
    response_model=StandardResponse[dict[str, Any]],
    summary="Set or clear preferred supplier flag (Purchase Manager only)",
)
async def set_preferred_supplier(
    body: dict[str, Any],
    company_id: UUID = Path(..., description="Company identifier"),
    supplier_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    supplier_svc: SupplierService = Depends(get_supplier_service),
) -> StandardResponse[dict[str, Any]]:
    """Set or clear the is_preferred flag. Purchase Manager role required."""
    is_preferred = bool(body.get("is_preferred", False))
    supplier = supplier_svc.set_preferred(
        supplier_id=supplier_id,
        company_id=company_id,
        is_preferred=is_preferred,
        actor_id=require_user_id(current_user),
    )
    supplier_svc.db.commit()
    return StandardResponse(
        data={"supplier_id": str(supplier.id), "is_preferred": supplier.is_preferred},
        message="Preferred flag updated",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# RBAC helpers
# ---------------------------------------------------------------------------


def _require_finance_manager(current_user: CurrentUser) -> None:
    """Raise 403 if the user is not a Finance Manager or higher role.

    NOTE: RBAC roles (current_user.roles) are populated by the auth provider.
    Until Better Auth RBAC integration is complete (Epic 7+), roles=[] for all
    users and this check is effectively bypassed. The restriction is documented
    here for future enforcement.
    """
    user_roles = set(getattr(current_user, "roles", []))
    if not user_roles:
        # RBAC not yet implemented — allow access, log intent
        return

    allowed_roles = {"FINANCE_MANAGER", "COMPANY_OWNER", "SUPER_ADMIN", "ADMIN"}
    if not (user_roles & allowed_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Finance Manager role required to access bank details.",
        )


def _require_purchase_manager(current_user: CurrentUser) -> None:
    """Raise 403 if the user does not have Purchase Manager or higher role.

    NOTE: RBAC roles not yet enforced until Epic 7+ — currently bypassed when roles=[].
    """
    user_roles = set(getattr(current_user, "roles", []))
    if not user_roles:
        return
    allowed_roles = {"PURCHASE_MANAGER", "COMPANY_OWNER", "SUPER_ADMIN", "ADMIN"}
    if not (user_roles & allowed_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Purchase Manager role required for this action.",
        )


# ===========================================================================
# Phase 3 — Approval Engine
# ===========================================================================
#
# Approval Matrix CRUD
#   GET    /approval/matrices              — list matrices
#   POST   /approval/matrices              — create matrix
#   GET    /approval/matrices/{matrix_id}  — get matrix
#   PATCH  /approval/matrices/{matrix_id}  — update matrix
#   DELETE /approval/matrices/{matrix_id}  — delete matrix
#
# Matrix Rule CRUD
#   GET    /approval/matrices/{matrix_id}/rules         — list rules
#   POST   /approval/matrices/{matrix_id}/rules         — create rule
#   PATCH  /approval/matrices/{matrix_id}/rules/{rule_id} — update rule
#   DELETE /approval/matrices/{matrix_id}/rules/{rule_id} — delete rule
#
# Approval Level CRUD
#   GET    /approval/rules/{rule_id}/levels              — list levels
#   POST   /approval/rules/{rule_id}/levels              — create level
#   PATCH  /approval/rules/{rule_id}/levels/{level_id}   — update level
#   DELETE /approval/rules/{rule_id}/levels/{level_id}   — delete level
#
# Approval Actions
#   POST   /approval/approve    — approve a document level
#   POST   /approval/reject     — reject a document
#   POST   /approval/bypass     — emergency bypass (Purchase Manager)
#   GET    /approval/status     — get approval status for a document
#   GET    /approval/route      — dry-run routing for a document
#
# Delegates
#   GET    /approval/delegates/by-delegator/{delegator_id} — list delegations
#   POST   /approval/delegates  — create delegation
#   PATCH  /approval/delegates/{delegate_id} — update delegation
#   DELETE /approval/delegates/{delegate_id} — delete delegation
#
# Tasks: T087, T088
# ===========================================================================


# ---------------------------------------------------------------------------
# Approval Matrix endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/approval/matrices",
    response_model=StandardResponse[list[ApprovalMatrixRead]],
    summary="List approval matrices for the company",
    tags=["Approval Engine"],
)
def list_approval_matrices(
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[list[ApprovalMatrixRead]]:
    matrices = svc.list_matrices(company_id=company_id)
    return StandardResponse(
        data=[
            ApprovalMatrixRead(
                id=m.id,
                company_id=m.company_id,
                document_type=m.document_type,
                name=m.name,
                is_active=m.is_active,
                created_at=m.created_at,
            )
            for m in matrices
        ],
        message="Approval matrices retrieved.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/approval/matrices",
    response_model=StandardResponse[ApprovalMatrixRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new approval matrix",
    tags=["Approval Engine"],
)
def create_approval_matrix(
    body: ApprovalMatrixCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[ApprovalMatrixRead]:
    _require_purchase_manager(current_user)
    matrix = svc.create_matrix(
        company_id=company_id,
        actor_id=current_user.user_id,
        document_type=body.document_type,
        name=body.name,
        is_active=body.is_active,
    )
    return StandardResponse(
        data=ApprovalMatrixRead(
            id=matrix.id,
            company_id=matrix.company_id,
            document_type=matrix.document_type,
            name=matrix.name,
            is_active=matrix.is_active,
            created_at=matrix.created_at,
        ),
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.get(
    "/approval/matrices/{matrix_id}",
    response_model=StandardResponse[ApprovalMatrixRead],
    summary="Get an approval matrix by ID",
    tags=["Approval Engine"],
)
def get_approval_matrix(
    matrix_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[ApprovalMatrixRead]:
    try:
        matrix = svc.get_matrix(matrix_id=matrix_id, company_id=company_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Approval matrix not found."
        )
    return StandardResponse(
        data=ApprovalMatrixRead(
            id=matrix.id,
            company_id=matrix.company_id,
            document_type=matrix.document_type,
            name=matrix.name,
            is_active=matrix.is_active,
            created_at=matrix.created_at,
        ),
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.patch(
    "/approval/matrices/{matrix_id}",
    response_model=StandardResponse[ApprovalMatrixRead],
    summary="Update an approval matrix",
    tags=["Approval Engine"],
)
def update_approval_matrix(
    body: ApprovalMatrixUpdate,
    matrix_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[ApprovalMatrixRead]:
    _require_purchase_manager(current_user)
    try:
        matrix = svc.update_matrix(
            matrix_id=matrix_id,
            company_id=company_id,
            name=body.name,
            is_active=body.is_active,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Approval matrix not found."
        )
    return StandardResponse(
        data=ApprovalMatrixRead(
            id=matrix.id,
            company_id=matrix.company_id,
            document_type=matrix.document_type,
            name=matrix.name,
            is_active=matrix.is_active,
            created_at=matrix.created_at,
        ),
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.delete(
    "/approval/matrices/{matrix_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an approval matrix",
    tags=["Approval Engine"],
)
def delete_approval_matrix(
    matrix_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> None:
    _require_purchase_manager(current_user)
    try:
        svc.delete_matrix(matrix_id=matrix_id, company_id=company_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Approval matrix not found."
        )


# ---------------------------------------------------------------------------
# Matrix Rule endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/approval/matrices/{matrix_id}/rules",
    response_model=StandardResponse[list[MatrixRuleRead]],
    summary="List rules for an approval matrix",
    tags=["Approval Engine"],
)
def list_matrix_rules(
    matrix_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[list[MatrixRuleRead]]:
    rules = svc.list_rules(matrix_id=matrix_id, company_id=company_id)
    return StandardResponse(
        data=[
            MatrixRuleRead(
                id=r.id,
                company_id=r.company_id,
                matrix_id=str(r.matrix_id),
                condition_type=r.condition_type,
                min_amount=r.min_amount,
                max_amount=r.max_amount,
                category_id=r.category_id,
                department=r.department,
                approval_level=r.approval_level,
                approval_mode=r.approval_mode,
                created_at=r.created_at,
            )
            for r in rules
        ],
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/approval/matrices/{matrix_id}/rules",
    response_model=StandardResponse[MatrixRuleRead],
    status_code=status.HTTP_201_CREATED,
    summary="Add a rule to an approval matrix",
    tags=["Approval Engine"],
)
def create_matrix_rule(
    body: MatrixRuleCreate,
    matrix_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[MatrixRuleRead]:
    _require_purchase_manager(current_user)
    rule = svc.create_rule(
        matrix_id=matrix_id,
        company_id=company_id,
        actor_id=current_user.user_id,
        condition_type=body.condition_type,
        approval_level=body.approval_level,
        approval_mode=body.approval_mode,
        min_amount=body.min_amount,
        max_amount=body.max_amount,
        category_id=body.category_id,
        department=body.department,
    )
    return StandardResponse(
        data=MatrixRuleRead(
            id=rule.id,
            company_id=rule.company_id,
            matrix_id=str(rule.matrix_id),
            condition_type=rule.condition_type,
            min_amount=rule.min_amount,
            max_amount=rule.max_amount,
            category_id=rule.category_id,
            department=rule.department,
            approval_level=rule.approval_level,
            approval_mode=rule.approval_mode,
            created_at=rule.created_at,
        ),
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.patch(
    "/approval/matrices/{matrix_id}/rules/{rule_id}",
    response_model=StandardResponse[MatrixRuleRead],
    summary="Update a matrix rule",
    tags=["Approval Engine"],
)
def update_matrix_rule(
    body: MatrixRuleUpdate,
    matrix_id: UUID = Path(...),
    rule_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[MatrixRuleRead]:
    _require_purchase_manager(current_user)
    try:
        rule = svc.update_rule(
            rule_id=rule_id,
            company_id=company_id,
            **body.model_dump(exclude_none=True),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Matrix rule not found."
        )
    return StandardResponse(
        data=MatrixRuleRead(
            id=rule.id,
            company_id=rule.company_id,
            matrix_id=str(rule.matrix_id),
            condition_type=rule.condition_type,
            min_amount=rule.min_amount,
            max_amount=rule.max_amount,
            category_id=rule.category_id,
            department=rule.department,
            approval_level=rule.approval_level,
            approval_mode=rule.approval_mode,
            created_at=rule.created_at,
        ),
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.delete(
    "/approval/matrices/{matrix_id}/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a matrix rule",
    tags=["Approval Engine"],
)
def delete_matrix_rule(
    matrix_id: UUID = Path(...),
    rule_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> None:
    _require_purchase_manager(current_user)
    try:
        svc.delete_rule(rule_id=rule_id, company_id=company_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Matrix rule not found."
        )


# ---------------------------------------------------------------------------
# Approval Level endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/approval/rules/{rule_id}/levels",
    response_model=StandardResponse[list[ApprovalLevelRead]],
    summary="List approval levels for a rule",
    tags=["Approval Engine"],
)
def list_approval_levels(
    rule_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[list[ApprovalLevelRead]]:
    levels = svc.list_levels(rule_id=rule_id, company_id=company_id)
    return StandardResponse(
        data=[
            ApprovalLevelRead(
                id=lv.id,
                company_id=lv.company_id,
                rule_id=str(lv.rule_id),
                level_number=lv.level_number,
                approver_type=lv.approver_type,
                approver_role=lv.approver_role,
                approver_user_id=lv.approver_user_id,
                escalation_days=lv.escalation_days,
                created_at=lv.created_at,
            )
            for lv in levels
        ],
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/approval/rules/{rule_id}/levels",
    response_model=StandardResponse[ApprovalLevelRead],
    status_code=status.HTTP_201_CREATED,
    summary="Add an approver level to a rule",
    tags=["Approval Engine"],
)
def create_approval_level(
    body: ApprovalLevelCreate,
    rule_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[ApprovalLevelRead]:
    _require_purchase_manager(current_user)
    level = svc.create_level(
        rule_id=rule_id,
        company_id=company_id,
        actor_id=current_user.user_id,
        level_number=body.level_number,
        approver_type=body.approver_type,
        escalation_days=body.escalation_days,
        approver_role=body.approver_role,
        approver_user_id=body.approver_user_id,
    )
    return StandardResponse(
        data=ApprovalLevelRead(
            id=level.id,
            company_id=level.company_id,
            rule_id=str(level.rule_id),
            level_number=level.level_number,
            approver_type=level.approver_type,
            approver_role=level.approver_role,
            approver_user_id=level.approver_user_id,
            escalation_days=level.escalation_days,
            created_at=level.created_at,
        ),
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.patch(
    "/approval/rules/{rule_id}/levels/{level_id}",
    response_model=StandardResponse[ApprovalLevelRead],
    summary="Update an approval level",
    tags=["Approval Engine"],
)
def update_approval_level(
    body: ApprovalLevelUpdate,
    rule_id: UUID = Path(...),
    level_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[ApprovalLevelRead]:
    _require_purchase_manager(current_user)
    try:
        level = svc.update_level(
            level_id=level_id,
            company_id=company_id,
            **body.model_dump(exclude_none=True),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Approval level not found."
        )
    return StandardResponse(
        data=ApprovalLevelRead(
            id=level.id,
            company_id=level.company_id,
            rule_id=str(level.rule_id),
            level_number=level.level_number,
            approver_type=level.approver_type,
            approver_role=level.approver_role,
            approver_user_id=level.approver_user_id,
            escalation_days=level.escalation_days,
            created_at=level.created_at,
        ),
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.delete(
    "/approval/rules/{rule_id}/levels/{level_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an approval level",
    tags=["Approval Engine"],
)
def delete_approval_level(
    rule_id: UUID = Path(...),
    level_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> None:
    _require_purchase_manager(current_user)
    try:
        svc.delete_level(level_id=level_id, company_id=company_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Approval level not found."
        )


# ---------------------------------------------------------------------------
# Approval Action endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/approval/approve",
    response_model=StandardResponse[ApprovalRecordRead],
    status_code=status.HTTP_201_CREATED,
    summary="Approve a document at a given level",
    tags=["Approval Engine"],
)
def approve_document(
    body: ApproveAction,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[ApprovalRecordRead]:
    try:
        record = svc.approve(
            document_type=body.document_type,
            document_id=body.document_id,
            approver_id=require_user_id(current_user),
            company_id=company_id,
            level_number=body.level_number,
            comment=body.comment,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return StandardResponse(
        data=ApprovalRecordRead(
            id=record.id,
            company_id=record.company_id,
            document_type=record.document_type,
            document_id=record.document_id,
            level_number=record.level_number,
            approver_id=record.approver_id,
            action=record.action,
            comment=record.comment,
            is_emergency_bypass=record.is_emergency_bypass,
            bypass_justification=record.bypass_justification,
            actioned_at=record.actioned_at,
            created_at=record.created_at,
        ),
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/approval/reject",
    response_model=StandardResponse[ApprovalRecordRead],
    status_code=status.HTTP_201_CREATED,
    summary="Reject a document at a given level",
    tags=["Approval Engine"],
)
def reject_document(
    body: RejectAction,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[ApprovalRecordRead]:
    try:
        record = svc.reject(
            document_type=body.document_type,
            document_id=body.document_id,
            approver_id=require_user_id(current_user),
            company_id=company_id,
            level_number=body.level_number,
            comment=body.comment,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return StandardResponse(
        data=ApprovalRecordRead(
            id=record.id,
            company_id=record.company_id,
            document_type=record.document_type,
            document_id=record.document_id,
            level_number=record.level_number,
            approver_id=record.approver_id,
            action=record.action,
            comment=record.comment,
            is_emergency_bypass=record.is_emergency_bypass,
            bypass_justification=record.bypass_justification,
            actioned_at=record.actioned_at,
            created_at=record.created_at,
        ),
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/approval/bypass",
    response_model=StandardResponse[ApprovalRecordRead],
    status_code=status.HTTP_201_CREATED,
    summary="Emergency bypass — Purchase Manager only",
    tags=["Approval Engine"],
)
def emergency_bypass(
    body: EmergencyBypassAction,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[ApprovalRecordRead]:
    _require_purchase_manager(current_user)
    try:
        record = svc.emergency_bypass(
            document_type=body.document_type,
            document_id=body.document_id,
            bypasser_id=require_user_id(current_user),
            company_id=company_id,
            justification=body.justification,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return StandardResponse(
        data=ApprovalRecordRead(
            id=record.id,
            company_id=record.company_id,
            document_type=record.document_type,
            document_id=record.document_id,
            level_number=record.level_number,
            approver_id=record.approver_id,
            action=record.action,
            comment=record.comment,
            is_emergency_bypass=record.is_emergency_bypass,
            bypass_justification=record.bypass_justification,
            actioned_at=record.actioned_at,
            created_at=record.created_at,
        ),
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.get(
    "/approval/status",
    response_model=StandardResponse[ApprovalStatusRead],
    summary="Get approval status for a document",
    tags=["Approval Engine"],
)
def get_approval_status(
    document_type: str = Query(
        ..., description="PURCHASE_REQUEST / PURCHASE_ORDER / VENDOR_RETURN"
    ),
    document_id: UUID = Query(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[ApprovalStatusRead]:
    status_data = svc.get_approval_status(
        document_type=document_type,
        document_id=document_id,
        company_id=company_id,
    )
    return StandardResponse(
        data=status_data,
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.get(
    "/approval/route",
    response_model=StandardResponse[RouteForApprovalResult],
    summary="Dry-run: determine approval route for a document",
    tags=["Approval Engine"],
)
def get_approval_route(
    document_type: str = Query(...),
    document_id: UUID = Query(...),
    amount: float | None = Query(None),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[RouteForApprovalResult]:
    from decimal import Decimal

    result = svc.route_for_approval(
        document_type=document_type,
        document_id=document_id,
        company_id=company_id,
        amount=Decimal(str(amount)) if amount is not None else None,
    )
    return StandardResponse(
        data=result,
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# Approval Delegate endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/approval/delegates/by-delegator/{delegator_id}",
    response_model=StandardResponse[list[ApprovalDelegateRead]],
    summary="List delegations by a delegator",
    tags=["Approval Engine"],
)
def list_delegates_by_delegator(
    delegator_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[list[ApprovalDelegateRead]]:
    delegations = svc._delegate_repo.list_for_delegator(
        company_id=company_id, delegator_id=delegator_id
    )
    return StandardResponse(
        data=[
            ApprovalDelegateRead(
                id=d.id,
                company_id=d.company_id,
                delegator_id=d.delegator_id,
                delegate_id=d.delegate_id,
                valid_from=d.valid_from,
                valid_until=d.valid_until,
                document_type=d.document_type,
                is_active=d.is_active,
                created_at=d.created_at,
            )
            for d in delegations
        ],
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/approval/delegates",
    response_model=StandardResponse[ApprovalDelegateRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create an approval delegation",
    tags=["Approval Engine"],
)
def create_approval_delegate(
    body: ApprovalDelegateCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[ApprovalDelegateRead]:
    try:
        delegation = svc.create_delegate(
            company_id=company_id,
            actor_id=require_user_id(current_user),
            delegate_id=body.delegate_id,
            valid_from=body.valid_from,
            valid_until=body.valid_until,
            document_type=body.document_type,
            is_active=body.is_active,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return StandardResponse(
        data=ApprovalDelegateRead(
            id=delegation.id,
            company_id=delegation.company_id,
            delegator_id=delegation.delegator_id,
            delegate_id=delegation.delegate_id,
            valid_from=delegation.valid_from,
            valid_until=delegation.valid_until,
            document_type=delegation.document_type,
            is_active=delegation.is_active,
            created_at=delegation.created_at,
        ),
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.patch(
    "/approval/delegates/{delegate_id}",
    response_model=StandardResponse[ApprovalDelegateRead],
    summary="Update an approval delegation",
    tags=["Approval Engine"],
)
def update_approval_delegate(
    body: ApprovalDelegateUpdate,
    delegate_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[ApprovalDelegateRead]:
    try:
        delegation = svc.update_delegate(
            delegate_id=delegate_id,
            company_id=company_id,
            **body.model_dump(exclude_none=True),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Delegation not found."
        )
    return StandardResponse(
        data=ApprovalDelegateRead(
            id=delegation.id,
            company_id=delegation.company_id,
            delegator_id=delegation.delegator_id,
            delegate_id=delegation.delegate_id,
            valid_from=delegation.valid_from,
            valid_until=delegation.valid_until,
            document_type=delegation.document_type,
            is_active=delegation.is_active,
            created_at=delegation.created_at,
        ),
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.delete(
    "/approval/delegates/{delegate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an approval delegation",
    tags=["Approval Engine"],
)
def delete_approval_delegate(
    delegate_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> None:
    try:
        svc.delete_delegate(delegate_id=delegate_id, company_id=company_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Delegation not found."
        )


# ===========================================================================
# Phase 4 — Purchase Requests (T108, T109)
# ===========================================================================

# ---------------------------------------------------------------------------
# PR CRUD endpoints (T108)
# ---------------------------------------------------------------------------


@router.post(
    "/purchase-requests",
    response_model=StandardResponse[PurchaseRequestRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Purchase Request",
    tags=["Purchase Requests"],
)
def create_purchase_request(
    body: PurchaseRequestCreate,
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PRService = Depends(get_pr_service),
) -> StandardResponse[PurchaseRequestRead]:
    pr = svc.create_pr(
        payload=body,
        company_id=company_id,
        requestor_id=require_user_id(current_user),
    )
    return StandardResponse(
        data=pr,
        message="Purchase request created.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.get(
    "/purchase-requests",
    response_model=StandardResponse[list[PurchaseRequestListRead]],
    summary="List Purchase Requests",
    tags=["Purchase Requests"],
)
def list_purchase_requests(
    company_id: UUID = Path(..., description="Company identifier"),
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PRService = Depends(get_pr_service),
) -> StandardResponse[list[PurchaseRequestListRead]]:
    items, total = svc.list_prs(
        company_id=company_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )
    return StandardResponse(
        data=items,
        message="Success.",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=utcnow(),
            total=total,
            skip=skip,
            limit=limit,
        ),
    )


@router.get(
    "/purchase-requests/{pr_id}",
    response_model=StandardResponse[PurchaseRequestRead],
    summary="Get a Purchase Request by ID",
    tags=["Purchase Requests"],
)
def get_purchase_request(
    pr_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PRService = Depends(get_pr_service),
) -> StandardResponse[PurchaseRequestRead]:
    from core.exceptions.base import NotFoundException

    try:
        pr = svc.get_pr(pr_id, company_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return StandardResponse(
        data=pr,
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.put(
    "/purchase-requests/{pr_id}",
    response_model=StandardResponse[PurchaseRequestRead],
    summary="Update a Purchase Request (DRAFT only)",
    tags=["Purchase Requests"],
)
def update_purchase_request(
    pr_id: UUID = Path(...),
    body: PurchaseRequestUpdate = Body(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PRService = Depends(get_pr_service),
) -> StandardResponse[PurchaseRequestRead]:
    from core.exceptions.base import NotFoundException

    try:
        pr = svc.update_pr(pr_id, company_id, body)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PRNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=pr,
        message="Purchase request updated.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.delete(
    "/purchase-requests/{pr_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete (soft) a DRAFT Purchase Request",
    tags=["Purchase Requests"],
)
def delete_purchase_request(
    pr_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PRService = Depends(get_pr_service),
) -> None:
    from core.exceptions.base import NotFoundException

    try:
        pr = svc._get_or_404(pr_id, company_id)
        if pr.status != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete PR in status {pr.status!r}. Cancel it first.",
            )
        svc.pr_repo.soft_delete(id=pr_id, company_id=company_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------------------------------------------------------------------
# PR Line endpoints (T108)
# ---------------------------------------------------------------------------


@router.post(
    "/purchase-requests/{pr_id}/lines",
    response_model=StandardResponse[PRLineRead],
    status_code=status.HTTP_201_CREATED,
    summary="Add a line to a DRAFT Purchase Request",
    tags=["Purchase Requests"],
)
def add_pr_line(
    pr_id: UUID = Path(...),
    body: PRLineCreate = Body(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PRService = Depends(get_pr_service),
) -> StandardResponse[PRLineRead]:
    from core.exceptions.base import NotFoundException

    try:
        line = svc.add_line(pr_id, company_id, body)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PRNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=line,
        message="Line added.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.put(
    "/purchase-requests/{pr_id}/lines/{line_id}",
    response_model=StandardResponse[PRLineRead],
    summary="Update a line on a DRAFT Purchase Request",
    tags=["Purchase Requests"],
)
def update_pr_line(
    pr_id: UUID = Path(...),
    line_id: UUID = Path(...),
    body: PRLineUpdate = Body(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PRService = Depends(get_pr_service),
) -> StandardResponse[PRLineRead]:
    from core.exceptions.base import NotFoundException

    try:
        line = svc.update_line(pr_id, line_id, company_id, body)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PRNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=line,
        message="Line updated.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.delete(
    "/purchase-requests/{pr_id}/lines/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a line from a DRAFT Purchase Request",
    tags=["Purchase Requests"],
)
def remove_pr_line(
    pr_id: UUID = Path(...),
    line_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PRService = Depends(get_pr_service),
) -> None:
    from core.exceptions.base import NotFoundException

    try:
        svc.remove_line(pr_id, line_id, company_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PRNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


# ---------------------------------------------------------------------------
# PR Action endpoints (T109)
# ---------------------------------------------------------------------------


@router.post(
    "/purchase-requests/{pr_id}/submit",
    response_model=StandardResponse[PurchaseRequestRead],
    summary="Submit a Purchase Request for approval",
    tags=["Purchase Requests"],
)
def submit_purchase_request(
    pr_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PRService = Depends(get_pr_service),
) -> StandardResponse[PurchaseRequestRead]:
    from core.exceptions.base import NotFoundException

    try:
        pr = svc.submit_pr(pr_id, company_id, require_user_id(current_user))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PRMissingLinesError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except InvalidPRStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=pr,
        message="Purchase request submitted.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/purchase-requests/{pr_id}/approve",
    response_model=StandardResponse[PurchaseRequestRead],
    summary="Approve a Purchase Request",
    tags=["Purchase Requests"],
)
def approve_purchase_request(
    pr_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PRService = Depends(get_pr_service),
) -> StandardResponse[PurchaseRequestRead]:
    from core.exceptions.base import NotFoundException

    try:
        pr = svc.approve_pr(pr_id, company_id, require_user_id(current_user))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidPRStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=pr,
        message="Purchase request approved.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/purchase-requests/{pr_id}/reject",
    response_model=StandardResponse[PurchaseRequestRead],
    summary="Reject a Purchase Request",
    tags=["Purchase Requests"],
)
def reject_purchase_request(
    pr_id: UUID = Path(...),
    body: PRCancelRequest = Body(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PRService = Depends(get_pr_service),
) -> StandardResponse[PurchaseRequestRead]:
    from core.exceptions.base import NotFoundException

    try:
        pr = svc.reject_pr(
            pr_id, company_id, require_user_id(current_user), reason=body.reason or ""
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidPRStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return StandardResponse(
        data=pr,
        message="Purchase request rejected.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/purchase-requests/{pr_id}/cancel",
    response_model=StandardResponse[PurchaseRequestRead],
    summary="Cancel a Purchase Request",
    tags=["Purchase Requests"],
)
def cancel_purchase_request(
    pr_id: UUID = Path(...),
    body: PRCancelRequest = Body(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PRService = Depends(get_pr_service),
) -> StandardResponse[PurchaseRequestRead]:
    from core.exceptions.base import NotFoundException

    try:
        pr = svc.cancel_pr(
            pr_id, company_id, require_user_id(current_user), reason=body.reason
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidPRStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=pr,
        message="Purchase request cancelled.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/purchase-requests/{pr_id}/convert-to-po",
    response_model=StandardResponse[dict[str, Any]],
    summary="Convert an approved Purchase Request to a Purchase Order",
    tags=["Purchase Requests"],
)
def convert_pr_to_po(
    pr_id: UUID = Path(...),
    company_id: UUID = Path(..., description="Company identifier"),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: PRService = Depends(get_pr_service),
) -> StandardResponse[dict[str, Any]]:
    from core.exceptions.base import NotFoundException

    try:
        po = svc.convert_to_po(pr_id, company_id, require_user_id(current_user))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PRNotConvertibleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data={"po_id": str(po.id), "po_number": po.po_number, "status": po.status},
        message="Purchase request converted to purchase order.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# =============================================================================
# Phase 5 — Purchase Orders (T134, T135, T136, T137)
# =============================================================================


def _raise_po_transition_error(exc: InvalidPOStatusTransitionError) -> None:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(exc),
    )


# ---------------------------------------------------------------------------
# PO CRUD  (T134)
# ---------------------------------------------------------------------------


@router.post(
    "/purchase-orders",
    response_model=StandardResponse[PurchaseOrderRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a Purchase Order",
    tags=["Purchase Orders"],
)
def create_purchase_order(
    body: PurchaseOrderCreate,
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[PurchaseOrderRead]:

    po = svc.create_po(body, company_id, require_user_id(current_user))
    return StandardResponse(
        data=po,
        message="Purchase order created.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.get(
    "/purchase-orders",
    response_model=StandardResponse[list[PurchaseOrderListRead]],
    summary="List Purchase Orders",
    tags=["Purchase Orders"],
)
def list_purchase_orders(
    company_id: UUID = Path(...),
    status_filter: str | None = Query(None, alias="status"),
    supplier_id: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[list[PurchaseOrderListRead]]:
    items, total = svc.list_pos(
        company_id,
        status=status_filter,
        supplier_id=supplier_id,
        skip=skip,
        limit=limit,
    )
    return StandardResponse(
        data=items,
        message=f"Found {total} purchase orders.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.get(
    "/purchase-orders/overdue",
    response_model=StandardResponse[list[PurchaseOrderListRead]],
    summary="List overdue Purchase Orders",
    tags=["Purchase Orders"],
)
def list_overdue_purchase_orders(
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[list[PurchaseOrderListRead]]:
    items = svc.get_overdue_pos(company_id)
    return StandardResponse(
        data=items,
        message=f"Found {len(items)} overdue purchase orders.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.get(
    "/purchase-orders/{po_id}",
    response_model=StandardResponse[PurchaseOrderRead],
    summary="Get a Purchase Order",
    tags=["Purchase Orders"],
)
def get_purchase_order(
    po_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[PurchaseOrderRead]:
    from core.exceptions.base import NotFoundException

    try:
        po = svc.get_po(po_id, company_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return StandardResponse(
        data=po,
        message="Purchase order retrieved.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.put(
    "/purchase-orders/{po_id}",
    response_model=StandardResponse[PurchaseOrderRead],
    summary="Update a Purchase Order (DRAFT only)",
    tags=["Purchase Orders"],
)
def update_purchase_order(
    po_id: UUID = Path(...),
    body: PurchaseOrderUpdate = Body(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[PurchaseOrderRead]:
    from core.exceptions.base import ConflictException, NotFoundException

    try:
        po = svc.update_po(po_id, company_id, body, require_user_id(current_user))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except POImmutableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=po,
        message="Purchase order updated.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.delete(
    "/purchase-orders/{po_id}",
    response_model=StandardResponse[dict[str, Any]],
    summary="Soft-delete a DRAFT Purchase Order",
    tags=["Purchase Orders"],
)
def delete_purchase_order(
    po_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[dict[str, Any]]:

    po = svc.po_repo.get_by_id_or_none(po_id, company_id)
    if po is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="PO not found."
        )
    if po.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only DRAFT purchase orders can be deleted.",
        )
    svc.po_repo.soft_delete(id=po_id, company_id=company_id)
    return StandardResponse(
        data={"id": str(po_id)},
        message="Purchase order deleted.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# PO Line management  (T135)
# ---------------------------------------------------------------------------


@router.post(
    "/purchase-orders/{po_id}/lines",
    response_model=StandardResponse[PurchaseOrderRead],
    status_code=status.HTTP_201_CREATED,
    summary="Add a line to a DRAFT Purchase Order",
    tags=["Purchase Orders"],
)
def add_po_line(
    po_id: UUID = Path(...),
    body: POLineCreate = Body(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[PurchaseOrderRead]:
    from core.exceptions.base import ConflictException, NotFoundException

    try:
        po = svc.add_line(po_id, company_id, body, require_user_id(current_user))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=po,
        message="Line added to purchase order.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.put(
    "/purchase-orders/{po_id}/lines/{line_id}",
    response_model=StandardResponse[PurchaseOrderRead],
    summary="Update a line on a DRAFT Purchase Order",
    tags=["Purchase Orders"],
)
def update_po_line(
    po_id: UUID = Path(...),
    line_id: UUID = Path(...),
    body: POLineUpdate = Body(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[PurchaseOrderRead]:
    from core.exceptions.base import ConflictException, NotFoundException

    try:
        po = svc.update_line(
            po_id, line_id, company_id, body, require_user_id(current_user)
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=po,
        message="Line updated.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.delete(
    "/purchase-orders/{po_id}/lines/{line_id}",
    response_model=StandardResponse[PurchaseOrderRead],
    summary="Remove a line from a DRAFT Purchase Order",
    tags=["Purchase Orders"],
)
def remove_po_line(
    po_id: UUID = Path(...),
    line_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[PurchaseOrderRead]:
    from core.exceptions.base import ConflictException, NotFoundException

    try:
        po = svc.remove_line(po_id, line_id, company_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=po,
        message="Line removed from purchase order.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# PO Additional Charges  (T136)
# ---------------------------------------------------------------------------


@router.post(
    "/purchase-orders/{po_id}/charges",
    response_model=StandardResponse[PurchaseOrderRead],
    status_code=status.HTTP_201_CREATED,
    summary="Add an additional charge to a DRAFT Purchase Order",
    tags=["Purchase Orders"],
)
def add_po_charge(
    po_id: UUID = Path(...),
    body: POAdditionalChargeCreate = Body(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[PurchaseOrderRead]:
    from core.exceptions.base import ConflictException, NotFoundException

    try:
        po = svc.add_charge(po_id, company_id, body, require_user_id(current_user))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=po,
        message="Charge added to purchase order.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.put(
    "/purchase-orders/{po_id}/charges/{charge_id}",
    response_model=StandardResponse[PurchaseOrderRead],
    summary="Update an additional charge on a DRAFT Purchase Order",
    tags=["Purchase Orders"],
)
def update_po_charge(
    po_id: UUID = Path(...),
    charge_id: UUID = Path(...),
    body: POAdditionalChargeUpdate = Body(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[PurchaseOrderRead]:
    from core.exceptions.base import ConflictException, NotFoundException

    try:
        po = svc.update_charge(
            po_id, charge_id, company_id, body, require_user_id(current_user)
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=po,
        message="Charge updated.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.delete(
    "/purchase-orders/{po_id}/charges/{charge_id}",
    response_model=StandardResponse[PurchaseOrderRead],
    summary="Remove a charge from a DRAFT Purchase Order",
    tags=["Purchase Orders"],
)
def remove_po_charge(
    po_id: UUID = Path(...),
    charge_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[PurchaseOrderRead]:
    from core.exceptions.base import ConflictException, NotFoundException

    try:
        po = svc.remove_charge(po_id, charge_id, company_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=po,
        message="Charge removed from purchase order.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# PO lifecycle actions  (T134)
# ---------------------------------------------------------------------------


@router.post(
    "/purchase-orders/{po_id}/submit",
    response_model=StandardResponse[PurchaseOrderRead],
    summary="Submit a Purchase Order for approval",
    tags=["Purchase Orders"],
)
def submit_purchase_order(
    po_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[PurchaseOrderRead]:
    from core.exceptions.base import NotFoundException

    try:
        po = svc.submit_po(po_id, company_id, require_user_id(current_user))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except POMissingSupplierError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except POMissingLinesError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except InvalidPOStatusTransitionError as exc:
        _raise_po_transition_error(exc)
    return StandardResponse(
        data=po,
        message="Purchase order submitted for approval.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/purchase-orders/{po_id}/approve",
    response_model=StandardResponse[PurchaseOrderRead],
    summary="Approve a Purchase Order",
    tags=["Purchase Orders"],
)
def approve_purchase_order(
    po_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[PurchaseOrderRead]:
    from core.exceptions.base import NotFoundException

    try:
        po = svc.approve_po(po_id, company_id, require_user_id(current_user))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidPOStatusTransitionError as exc:
        _raise_po_transition_error(exc)
    return StandardResponse(
        data=po,
        message="Purchase order approved.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/purchase-orders/{po_id}/reject",
    response_model=StandardResponse[PurchaseOrderRead],
    summary="Reject a Purchase Order",
    tags=["Purchase Orders"],
)
def reject_purchase_order(
    po_id: UUID = Path(...),
    body: dict[str, Any] = Body(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[PurchaseOrderRead]:
    from core.exceptions.base import NotFoundException

    reason = body.get("reason", "") if body else ""
    try:
        po = svc.reject_po(
            po_id, company_id, require_user_id(current_user), reason=reason
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except InvalidPOStatusTransitionError as exc:
        _raise_po_transition_error(exc)
    return StandardResponse(
        data=po,
        message="Purchase order rejected.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/purchase-orders/{po_id}/cancel",
    response_model=StandardResponse[PurchaseOrderRead],
    summary="Cancel a Purchase Order",
    tags=["Purchase Orders"],
)
def cancel_purchase_order(
    po_id: UUID = Path(...),
    body: POCancelRequest = Body(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[PurchaseOrderRead]:
    from core.exceptions.base import NotFoundException

    try:
        po = svc.cancel_po(
            po_id,
            company_id,
            require_user_id(current_user),
            reason_code_id=body.reason_code_id,
            reason=body.reason or body.cancellation_reason,
            has_confirmed_gr=body.has_confirmed_gr,
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except POCancelBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except InvalidPOStatusTransitionError as exc:
        _raise_po_transition_error(exc)
    return StandardResponse(
        data=po,
        message="Purchase order cancelled.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/purchase-orders/{po_id}/close",
    response_model=StandardResponse[PurchaseOrderRead],
    summary="Close a Purchase Order",
    tags=["Purchase Orders"],
)
def close_purchase_order(
    po_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[PurchaseOrderRead]:
    from core.exceptions.base import NotFoundException

    try:
        po = svc.close_po(po_id, company_id, require_user_id(current_user))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidPOStatusTransitionError as exc:
        _raise_po_transition_error(exc)
    return StandardResponse(
        data=po,
        message="Purchase order closed.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/purchase-orders/{po_id}/amend",
    response_model=StandardResponse[PurchaseOrderRead],
    summary="Amend an approved Purchase Order",
    tags=["Purchase Orders"],
)
def amend_purchase_order(
    po_id: UUID = Path(...),
    body: POAmendRequest = Body(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[PurchaseOrderRead]:
    from core.exceptions.base import ConflictException, NotFoundException

    try:
        po = svc.amend_po(
            po_id,
            company_id,
            changes=body.changes,
            reason=body.reason,
            actor_id=require_user_id(current_user),
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=po,
        message="Purchase order amendment created and sent for re-approval.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/purchase-orders/{po_id}/revert-to-draft",
    response_model=StandardResponse[PurchaseOrderRead],
    summary="Revert a rejected PO back to DRAFT for revision",
    tags=["Purchase Orders"],
)
def revert_po_to_draft(
    po_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[PurchaseOrderRead]:
    from core.exceptions.base import NotFoundException

    try:
        po = svc.revert_to_draft(po_id, company_id, require_user_id(current_user))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidPOStatusTransitionError as exc:
        _raise_po_transition_error(exc)
    return StandardResponse(
        data=po,
        message="Purchase order reverted to DRAFT.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# PO PDF export  (T137) — stub implementation
# ---------------------------------------------------------------------------


@router.get(
    "/purchase-orders/{po_id}/export/pdf",
    summary="Export Purchase Order as PDF",
    tags=["Purchase Orders"],
)
def export_po_pdf(
    po_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: POService = Depends(get_po_service),
) -> StandardResponse[dict[str, Any]]:
    """Return PO data formatted for PDF generation.

    Note: Full PDF generation (reportlab/WeasyPrint) is deferred to Phase 9
    infrastructure work. This endpoint returns a JSON payload suitable for
    client-side PDF rendering.
    """
    from core.exceptions.base import NotFoundException

    try:
        po = svc.get_po(po_id, company_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return StandardResponse(
        data={
            "po_number": po.po_number,
            "status": po.status,
            "supplier_id": po.supplier_id,
            "currency_code": po.currency_code,
            "total": str(po.total),
            "lines": [ln.model_dump() for ln in po.lines],
            "charges": [ch.model_dump() for ch in po.charges],
            "notes": po.notes,
        },
        message="Purchase order data for PDF export.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# Goods Receipt endpoints (T158) — Phase 6
# ---------------------------------------------------------------------------


@router.get(
    "/purchase-orders/{po_id}/open-quantities",
    response_model=StandardResponse[list[GROpenQuantity]],
    summary="Get open quantities per PO line (for GR creation UI)",
    tags=["Goods Receipts"],
)
def get_po_open_quantities(
    po_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: GRService = Depends(get_gr_service),
) -> StandardResponse[list[GROpenQuantity]]:
    """Return per-line open quantities for a PO to help populate a new GR."""
    from core.exceptions.base import NotFoundException

    try:
        items = svc.get_open_quantities(po_id=po_id, company_id=company_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return StandardResponse(
        data=items,
        message="Open quantities retrieved.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/goods-receipts",
    response_model=StandardResponse[GoodsReceiptRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Goods Receipt (DRAFT)",
    tags=["Goods Receipts"],
)
def create_goods_receipt(
    body: GoodsReceiptCreate,
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: GRService = Depends(get_gr_service),
) -> StandardResponse[GoodsReceiptRead]:
    """Create a DRAFT GR against an APPROVED or PARTIALLY_RECEIVED PO."""
    from core.exceptions.base import NotFoundException

    try:
        gr = svc.create_gr(
            payload=body,
            company_id=company_id,
            user_id=require_user_id(current_user),
        )
        svc.db.commit()
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except GRInvalidPOStatusError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=gr,
        message="Goods receipt created.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.get(
    "/goods-receipts",
    response_model=StandardResponse[list[GoodsReceiptListRead]],
    summary="List Goods Receipts",
    tags=["Goods Receipts"],
)
def list_goods_receipts(
    company_id: UUID = Path(...),
    status_filter: str | None = Query(None, alias="status"),
    po_id: UUID | None = Query(None),
    supplier_id: UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: GRService = Depends(get_gr_service),
) -> StandardResponse[list[GoodsReceiptListRead]]:
    """Return paginated goods receipt list with optional filters."""
    items, total = svc.list_grs(
        company_id=company_id,
        status=status_filter,
        po_id=str(po_id) if po_id else None,
        supplier_id=str(supplier_id) if supplier_id else None,
        skip=skip,
        limit=limit,
    )
    return StandardResponse(
        data=items,
        message="Success.",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=utcnow(),
            total=total,
            skip=skip,
            limit=limit,
        ),
    )


@router.get(
    "/goods-receipts/{gr_id}",
    response_model=StandardResponse[GoodsReceiptRead],
    summary="Get a Goods Receipt by ID",
    tags=["Goods Receipts"],
)
def get_goods_receipt(
    gr_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: GRService = Depends(get_gr_service),
) -> StandardResponse[GoodsReceiptRead]:
    """Return full GR detail with line items."""
    from core.exceptions.base import NotFoundException

    try:
        gr = svc.get_gr(gr_id=gr_id, company_id=company_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return StandardResponse(
        data=gr,
        message="Success.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.put(
    "/goods-receipts/{gr_id}",
    response_model=StandardResponse[GoodsReceiptRead],
    summary="Update GR header fields (DRAFT only)",
    tags=["Goods Receipts"],
)
def update_goods_receipt(
    gr_id: UUID = Path(...),
    body: GoodsReceiptUpdate = Body(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: GRService = Depends(get_gr_service),
) -> StandardResponse[GoodsReceiptRead]:
    """Update mutable header fields on a DRAFT GR."""
    from core.exceptions.base import NotFoundException

    try:
        gr = svc.update_gr(
            gr_id=gr_id,
            company_id=company_id,
            payload=body,
        )
        svc.db.commit()
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except GRImmutableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=gr,
        message="Goods receipt updated.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.put(
    "/goods-receipts/{gr_id}/lines",
    response_model=StandardResponse[GoodsReceiptRead],
    summary="Replace all lines on a DRAFT GR",
    tags=["Goods Receipts"],
)
def replace_gr_lines(
    gr_id: UUID = Path(...),
    body: list[GRLineCreate] = Body(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: GRService = Depends(get_gr_service),
) -> StandardResponse[GoodsReceiptRead]:
    """Soft-delete existing lines and create new ones. DRAFT only."""
    from core.exceptions.base import NotFoundException

    try:
        gr = svc.replace_lines(
            gr_id=gr_id,
            company_id=company_id,
            lines=body,
            user_id=require_user_id(current_user),
        )
        svc.db.commit()
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except GRImmutableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=gr,
        message="GR lines replaced.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/goods-receipts/{gr_id}/confirm",
    response_model=StandardResponse[GoodsReceiptRead],
    summary="Confirm a DRAFT GR (atomic: stock + PO status + rating)",
    tags=["Goods Receipts"],
)
def confirm_goods_receipt(
    gr_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: GRService = Depends(get_gr_service),
) -> StandardResponse[GoodsReceiptRead]:
    """Transition GR from DRAFT to CONFIRMED.

    Atomically:
    - Sets GR status to CONFIRMED
    - Creates PURCHASE_RECEIPT stock movements (if warehouse_id + product_id set)
    - Updates PO line quantities (quantity_received, quantity_rejected, open_quantity)
    - Updates PO status (PARTIALLY_RECEIVED / FULLY_RECEIVED)
    - Recomputes supplier rating
    - Publishes GR domain events
    """
    from core.exceptions.base import NotFoundException

    try:
        gr = svc.confirm_gr(
            gr_id=gr_id,
            company_id=company_id,
            user_id=require_user_id(current_user),
        )
        svc.db.commit()
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except GRImmutableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except GROverReceiptError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return StandardResponse(
        data=gr,
        message="Goods receipt confirmed.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# T235 — Barcode lookup for GR line entry (purchase.gr_barcode_scan feature flag)
# ---------------------------------------------------------------------------


@router.get(
    "/goods-receipts/barcode/{barcode}",
    response_model=None,
    summary="Resolve product by barcode for GR line entry (feature-flagged)",
    tags=["Goods Receipts"],
)
def resolve_barcode_for_gr(
    barcode: str = Path(..., description="EAN/UPC/QR barcode value"),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    flag_svc: PurchaseFeatureFlagService = Depends(get_purchase_feature_flag_service),
) -> NoReturn:
    """Resolve a product from a barcode scan for Goods Receipt line entry.

    Requires ``purchase.gr_barcode_scan`` feature flag to be enabled.
    When enabled, proxies the lookup to the Epic 5 Inventory barcode API.
    Returns 501 (stub) until the Inventory integration is wired.
    """
    if not flag_svc.is_enabled(company_id, "purchase.gr_barcode_scan"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Feature 'purchase.gr_barcode_scan' is not enabled for this company.",
        )
    # Stub — Epic 5 Inventory barcode API integration pending
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            f"Barcode lookup stub: barcode={barcode!r}. "
            "Wire to Epic 5 Inventory barcode endpoint to activate."
        ),
    )


# =============================================================================
# Vendor Returns (RMA) — Phase 7
# =============================================================================


@router.get(
    "/vendor-returns",
    response_model=StandardResponse[list[VendorReturnListRead]],
    summary="List Vendor Returns (RMAs) for a company",
    tags=["Vendor Returns"],
)
def list_vendor_returns(
    company_id: UUID = Path(...),
    status: str | None = Query(None),
    gr_id: UUID | None = Query(None),
    supplier_id: UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: RMAService = Depends(get_rma_service),
) -> StandardResponse[list[VendorReturnListRead]]:
    rmas = svc.list_rmas(
        company_id,
        status=status,
        gr_id=str(gr_id) if gr_id else None,
        supplier_id=str(supplier_id) if supplier_id else None,
        skip=skip,
        limit=limit,
    )
    return StandardResponse(
        data=rmas,
        message="OK",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/vendor-returns",
    response_model=StandardResponse[VendorReturnRead],
    status_code=201,
    summary="Create a DRAFT Vendor Return (RMA) against a confirmed GR",
    tags=["Vendor Returns"],
)
def create_vendor_return(
    body: VendorReturnCreate,
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: RMAService = Depends(get_rma_service),
) -> StandardResponse[VendorReturnRead]:
    try:
        rma = svc.create_rma(
            payload=body, company_id=company_id, user_id=require_user_id(current_user)
        )
        svc.db.commit()
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RMAInvalidGRStatusError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except RMAReturnQuantityError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return StandardResponse(
        data=rma,
        message="Vendor return created.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.get(
    "/vendor-returns/{rma_id}",
    response_model=StandardResponse[VendorReturnRead],
    summary="Get a Vendor Return by ID",
    tags=["Vendor Returns"],
)
def get_vendor_return(
    rma_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: RMAService = Depends(get_rma_service),
) -> StandardResponse[VendorReturnRead]:
    try:
        rma = svc.get_rma(rma_id, company_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return StandardResponse(
        data=rma,
        message="OK",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.put(
    "/vendor-returns/{rma_id}",
    response_model=StandardResponse[VendorReturnRead],
    summary="Update Vendor Return header (DRAFT only)",
    tags=["Vendor Returns"],
)
def update_vendor_return(
    body: VendorReturnUpdate,
    rma_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: RMAService = Depends(get_rma_service),
) -> StandardResponse[VendorReturnRead]:
    try:
        rma = svc.update_rma(rma_id=rma_id, company_id=company_id, payload=body)
        svc.db.commit()
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RMAImmutableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=rma,
        message="Vendor return updated.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.put(
    "/vendor-returns/{rma_id}/lines",
    response_model=StandardResponse[VendorReturnRead],
    summary="Replace all return lines (DRAFT only)",
    tags=["Vendor Returns"],
)
def replace_return_lines(
    body: list[ReturnLineCreate],
    rma_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: RMAService = Depends(get_rma_service),
) -> StandardResponse[VendorReturnRead]:
    try:
        rma = svc.replace_lines(
            rma_id=rma_id,
            company_id=company_id,
            new_lines=body,
            user_id=require_user_id(current_user),
        )
        svc.db.commit()
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RMAImmutableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except RMAReturnQuantityError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return StandardResponse(
        data=rma,
        message="Return lines replaced.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/vendor-returns/{rma_id}/submit",
    response_model=StandardResponse[VendorReturnRead],
    summary="Submit a DRAFT RMA for approval (DRAFT → SUBMITTED)",
    tags=["Vendor Returns"],
)
def submit_vendor_return(
    rma_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: RMAService = Depends(get_rma_service),
) -> StandardResponse[VendorReturnRead]:
    try:
        rma = svc.submit_rma(
            rma_id=rma_id, company_id=company_id, user_id=require_user_id(current_user)
        )
        svc.db.commit()
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RMAInvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=rma,
        message="Vendor return submitted.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/vendor-returns/{rma_id}/approve",
    response_model=StandardResponse[VendorReturnRead],
    summary="Approve a submitted RMA (SUBMITTED → APPROVED)",
    tags=["Vendor Returns"],
)
def approve_vendor_return(
    rma_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: RMAService = Depends(get_rma_service),
) -> StandardResponse[VendorReturnRead]:
    try:
        rma = svc.approve_rma(
            rma_id=rma_id, company_id=company_id, user_id=require_user_id(current_user)
        )
        svc.db.commit()
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RMAInvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=rma,
        message="Vendor return approved.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/vendor-returns/{rma_id}/dispatch",
    response_model=StandardResponse[VendorReturnRead],
    summary="Dispatch an approved RMA — atomic stock deduction (APPROVED → DISPATCHED)",
    tags=["Vendor Returns"],
)
def dispatch_vendor_return(
    rma_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: RMAService = Depends(get_rma_service),
) -> StandardResponse[VendorReturnRead]:
    try:
        rma = svc.dispatch_rma(
            rma_id=rma_id, company_id=company_id, user_id=require_user_id(current_user)
        )
        svc.db.commit()
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RMAInvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=rma,
        message="Vendor return dispatched. Stock movements created.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/vendor-returns/{rma_id}/complete",
    response_model=StandardResponse[VendorReturnRead],
    summary="Complete a dispatched RMA — sets credit_note_pending (DISPATCHED → COMPLETED)",
    tags=["Vendor Returns"],
)
def complete_vendor_return(
    rma_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: RMAService = Depends(get_rma_service),
) -> StandardResponse[VendorReturnRead]:
    try:
        rma = svc.complete_rma(
            rma_id=rma_id, company_id=company_id, user_id=require_user_id(current_user)
        )
        svc.db.commit()
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RMAInvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=rma,
        message="Vendor return completed. Credit note pending.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.post(
    "/vendor-returns/{rma_id}/cancel",
    response_model=StandardResponse[VendorReturnRead],
    summary="Cancel a SUBMITTED or APPROVED RMA",
    tags=["Vendor Returns"],
)
def cancel_vendor_return(
    rma_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: RMAService = Depends(get_rma_service),
) -> StandardResponse[VendorReturnRead]:
    try:
        rma = svc.cancel_rma(
            rma_id=rma_id, company_id=company_id, user_id=require_user_id(current_user)
        )
        svc.db.commit()
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RMAInvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=rma,
        message="Vendor return cancelled.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# =============================================================================
# Phase 8: Purchase Costing endpoints (T198)
# =============================================================================


@router.get(
    "/purchase-orders/{po_id}/cost-summary",
    response_model=StandardResponse[POCostSummary],
    summary="Get financial cost summary for a Purchase Order",
    tags=["Purchase Costing"],
)
def get_po_cost_summary(
    po_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: CostService = Depends(get_cost_service),
) -> StandardResponse[POCostSummary]:
    try:
        summary = svc.get_po_cost_summary(po_id=po_id, company_id=company_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return StandardResponse(
        data=summary,
        message="PO cost summary retrieved.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.get(
    "/goods-receipts/{gr_id}/cost-summary",
    response_model=StandardResponse[GRCostSummary],
    summary="Get cost summary with PPV per line for a Goods Receipt",
    tags=["Purchase Costing"],
)
def get_gr_cost_summary(
    gr_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: CostService = Depends(get_cost_service),
) -> StandardResponse[GRCostSummary]:
    try:
        summary = svc.get_gr_cost_summary(gr_id=gr_id, company_id=company_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return StandardResponse(
        data=summary,
        message="GR cost summary with PPV retrieved.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


@router.get(
    "/goods-receipts/{gr_id}/cost-entry",
    response_model=StandardResponse[PurchaseCostEntryRead],
    summary="Get the immutable cost entry snapshot for a confirmed Goods Receipt",
    tags=["Purchase Costing"],
)
def get_cost_entry_for_gr(
    gr_id: UUID = Path(...),
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: CostService = Depends(get_cost_service),
) -> StandardResponse[PurchaseCostEntryRead]:
    try:
        entry = svc.get_cost_entry_for_gr(gr_id=gr_id, company_id=company_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return StandardResponse(
        data=entry,
        message="Cost entry retrieved.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ===========================================================================
# Phase 9 — Purchase Intelligence & Reporting  (T223)
# ===========================================================================

# ---------------------------------------------------------------------------
# RPT-01  Purchase Order Summary
# ---------------------------------------------------------------------------


@router.get(
    "/reports/purchase-order-summary",
    response_model=None,
    summary="RPT-01: Purchase Order Summary — all POs filterable by status/supplier/date",
    tags=["Purchase Reports"],
)
def rpt_01_purchase_order_summary(
    company_id: UUID = Path(...),
    status_filter: str | None = Query(None, alias="status"),
    supplier_id: UUID | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    fmt: str | None = Query(None, description="csv | xlsx — omit for JSON"),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportService = Depends(get_report_service),
    export_svc: ReportExportService = Depends(get_report_export_service),
) -> Response | StandardResponse[list[dict[str, Any]]]:
    from datetime import date as _date

    rows = svc.purchase_order_summary(
        company_id,
        status=status_filter,
        supplier_id=supplier_id,
        date_from=_date.fromisoformat(date_from) if date_from else None,
        date_to=_date.fromisoformat(date_to) if date_to else None,
        skip=skip,
        limit=limit,
    )
    if fmt == "csv":
        return Response(
            export_svc.to_csv(rows, report_name="purchase_order_summary"),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=purchase_order_summary.csv"
            },
        )
    if fmt == "xlsx":
        return Response(
            export_svc.to_excel(rows, sheet_name="PO Summary"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=purchase_order_summary.xlsx"
            },
        )
    return StandardResponse(
        data=rows,
        message=f"{len(rows)} records.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# RPT-02  Pending Purchase Orders
# ---------------------------------------------------------------------------


@router.get(
    "/reports/pending-purchase-orders",
    response_model=None,
    summary="RPT-02: Pending Purchase Orders (APPROVED/PARTIALLY_RECEIVED)",
    tags=["Purchase Reports"],
)
def rpt_02_pending_purchase_orders(
    company_id: UUID = Path(...),
    fmt: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportService = Depends(get_report_service),
    export_svc: ReportExportService = Depends(get_report_export_service),
) -> Response | StandardResponse[list[dict[str, Any]]]:
    rows = svc.pending_purchase_orders(company_id, skip=skip, limit=limit)
    if fmt == "csv":
        return Response(
            export_svc.to_csv(rows),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=pending_purchase_orders.csv"
            },
        )
    if fmt == "xlsx":
        return Response(
            export_svc.to_excel(rows, sheet_name="Pending POs"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=pending_purchase_orders.xlsx"
            },
        )
    return StandardResponse(
        data=rows,
        message=f"{len(rows)} records.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# RPT-03  Overdue Deliveries
# ---------------------------------------------------------------------------


@router.get(
    "/reports/overdue-deliveries",
    response_model=None,
    summary="RPT-03: Overdue Deliveries — POs past expected delivery date",
    tags=["Purchase Reports"],
)
def rpt_03_overdue_deliveries(
    company_id: UUID = Path(...),
    as_of: str | None = Query(None),
    fmt: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportService = Depends(get_report_service),
    export_svc: ReportExportService = Depends(get_report_export_service),
) -> Response | StandardResponse[list[dict[str, Any]]]:
    from datetime import date as _date

    rows = svc.overdue_deliveries(
        company_id,
        as_of=_date.fromisoformat(as_of) if as_of else None,
        skip=skip,
        limit=limit,
    )
    if fmt == "csv":
        return Response(
            export_svc.to_csv(rows),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=overdue_deliveries.csv"
            },
        )
    if fmt == "xlsx":
        return Response(
            export_svc.to_excel(rows, sheet_name="Overdue Deliveries"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=overdue_deliveries.xlsx"
            },
        )
    return StandardResponse(
        data=rows,
        message=f"{len(rows)} records.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# RPT-04  Goods Receipt Report
# ---------------------------------------------------------------------------


@router.get(
    "/reports/goods-receipt-report",
    response_model=None,
    summary="RPT-04: Goods Receipt Report — confirmed GRs in period",
    tags=["Purchase Reports"],
)
def rpt_04_goods_receipt_report(
    company_id: UUID = Path(...),
    supplier_id: UUID | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    fmt: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportService = Depends(get_report_service),
    export_svc: ReportExportService = Depends(get_report_export_service),
) -> Response | StandardResponse[list[dict[str, Any]]]:
    from datetime import date as _date

    rows = svc.goods_receipt_report(
        company_id,
        supplier_id=supplier_id,
        date_from=_date.fromisoformat(date_from) if date_from else None,
        date_to=_date.fromisoformat(date_to) if date_to else None,
        skip=skip,
        limit=limit,
    )
    if fmt == "csv":
        return Response(
            export_svc.to_csv(rows),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=goods_receipt_report.csv"
            },
        )
    if fmt == "xlsx":
        return Response(
            export_svc.to_excel(rows, sheet_name="GR Report"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=goods_receipt_report.xlsx"
            },
        )
    return StandardResponse(
        data=rows,
        message=f"{len(rows)} records.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# RPT-05  Purchase Request Status
# ---------------------------------------------------------------------------


@router.get(
    "/reports/purchase-request-status",
    response_model=None,
    summary="RPT-05: Purchase Request Status — all PRs with age and requestor",
    tags=["Purchase Reports"],
)
def rpt_05_purchase_request_status(
    company_id: UUID = Path(...),
    status_filter: str | None = Query(None, alias="status"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    fmt: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportService = Depends(get_report_service),
    export_svc: ReportExportService = Depends(get_report_export_service),
) -> Response | StandardResponse[list[dict[str, Any]]]:
    from datetime import date as _date

    rows = svc.purchase_request_status(
        company_id,
        status=status_filter,
        date_from=_date.fromisoformat(date_from) if date_from else None,
        date_to=_date.fromisoformat(date_to) if date_to else None,
        skip=skip,
        limit=limit,
    )
    if fmt == "csv":
        return Response(
            export_svc.to_csv(rows),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=purchase_request_status.csv"
            },
        )
    if fmt == "xlsx":
        return Response(
            export_svc.to_excel(rows, sheet_name="PR Status"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=purchase_request_status.xlsx"
            },
        )
    return StandardResponse(
        data=rows,
        message=f"{len(rows)} records.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# RPT-06  Supplier Performance
# ---------------------------------------------------------------------------


@router.get(
    "/reports/supplier-performance",
    response_model=None,
    summary="RPT-06: Supplier Performance — on-time rate, fill rate, rejection rate",
    tags=["Purchase Reports"],
)
def rpt_06_supplier_performance(
    company_id: UUID = Path(...),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    fmt: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportService = Depends(get_report_service),
    export_svc: ReportExportService = Depends(get_report_export_service),
) -> Response | StandardResponse[list[dict[str, Any]]]:
    from datetime import date as _date

    rows = svc.supplier_performance(
        company_id,
        date_from=_date.fromisoformat(date_from) if date_from else None,
        date_to=_date.fromisoformat(date_to) if date_to else None,
        skip=skip,
        limit=limit,
    )
    if fmt == "csv":
        return Response(
            export_svc.to_csv(rows),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=supplier_performance.csv"
            },
        )
    if fmt == "xlsx":
        return Response(
            export_svc.to_excel(rows, sheet_name="Supplier Performance"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=supplier_performance.xlsx"
            },
        )
    return StandardResponse(
        data=rows,
        message=f"{len(rows)} records.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# RPT-07  Vendor Return Report
# ---------------------------------------------------------------------------


@router.get(
    "/reports/vendor-return-report",
    response_model=None,
    summary="RPT-07: Vendor Return Report — RMAs in period",
    tags=["Purchase Reports"],
)
def rpt_07_vendor_return_report(
    company_id: UUID = Path(...),
    supplier_id: UUID | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    fmt: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportService = Depends(get_report_service),
    export_svc: ReportExportService = Depends(get_report_export_service),
) -> Response | StandardResponse[list[dict[str, Any]]]:
    from datetime import date as _date

    rows = svc.vendor_return_report(
        company_id,
        supplier_id=supplier_id,
        date_from=_date.fromisoformat(date_from) if date_from else None,
        date_to=_date.fromisoformat(date_to) if date_to else None,
        skip=skip,
        limit=limit,
    )
    if fmt == "csv":
        return Response(
            export_svc.to_csv(rows),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=vendor_return_report.csv"
            },
        )
    if fmt == "xlsx":
        return Response(
            export_svc.to_excel(rows, sheet_name="Vendor Returns"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=vendor_return_report.xlsx"
            },
        )
    return StandardResponse(
        data=rows,
        message=f"{len(rows)} records.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# RPT-08  Purchase by Supplier
# ---------------------------------------------------------------------------


@router.get(
    "/reports/purchase-by-supplier",
    response_model=None,
    summary="RPT-08: Purchase by Supplier — total spend per supplier",
    tags=["Purchase Reports"],
)
def rpt_08_purchase_by_supplier(
    company_id: UUID = Path(...),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    fmt: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportService = Depends(get_report_service),
    export_svc: ReportExportService = Depends(get_report_export_service),
) -> Response | StandardResponse[list[dict[str, Any]]]:
    from datetime import date as _date

    rows = svc.purchase_by_supplier(
        company_id,
        date_from=_date.fromisoformat(date_from) if date_from else None,
        date_to=_date.fromisoformat(date_to) if date_to else None,
        skip=skip,
        limit=limit,
    )
    if fmt == "csv":
        return Response(
            export_svc.to_csv(rows),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=purchase_by_supplier.csv"
            },
        )
    if fmt == "xlsx":
        return Response(
            export_svc.to_excel(rows, sheet_name="Purchase By Supplier"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=purchase_by_supplier.xlsx"
            },
        )
    return StandardResponse(
        data=rows,
        message=f"{len(rows)} records.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# RPT-09  Purchase by Category
# ---------------------------------------------------------------------------


@router.get(
    "/reports/purchase-by-category",
    response_model=None,
    summary="RPT-09: Purchase by Category — total spend per supplier category",
    tags=["Purchase Reports"],
)
def rpt_09_purchase_by_category(
    company_id: UUID = Path(...),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    fmt: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportService = Depends(get_report_service),
    export_svc: ReportExportService = Depends(get_report_export_service),
) -> Response | StandardResponse[list[dict[str, Any]]]:
    from datetime import date as _date

    rows = svc.purchase_by_category(
        company_id,
        date_from=_date.fromisoformat(date_from) if date_from else None,
        date_to=_date.fromisoformat(date_to) if date_to else None,
        skip=skip,
        limit=limit,
    )
    if fmt == "csv":
        return Response(
            export_svc.to_csv(rows),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=purchase_by_category.csv"
            },
        )
    if fmt == "xlsx":
        return Response(
            export_svc.to_excel(rows, sheet_name="Purchase By Category"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=purchase_by_category.xlsx"
            },
        )
    return StandardResponse(
        data=rows,
        message=f"{len(rows)} records.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# RPT-10  Purchase Price Variance
# ---------------------------------------------------------------------------


@router.get(
    "/reports/purchase-price-variance",
    response_model=None,
    summary="RPT-10: Purchase Price Variance — GR vs PO cost per line",
    tags=["Purchase Reports"],
)
def rpt_10_purchase_price_variance(
    company_id: UUID = Path(...),
    supplier_id: UUID | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    fmt: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportService = Depends(get_report_service),
    export_svc: ReportExportService = Depends(get_report_export_service),
) -> Response | StandardResponse[list[dict[str, Any]]]:
    from datetime import date as _date

    rows = svc.purchase_price_variance(
        company_id,
        supplier_id=supplier_id,
        date_from=_date.fromisoformat(date_from) if date_from else None,
        date_to=_date.fromisoformat(date_to) if date_to else None,
        skip=skip,
        limit=limit,
    )
    if fmt == "csv":
        return Response(
            export_svc.to_csv(rows),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=purchase_price_variance.csv"
            },
        )
    if fmt == "xlsx":
        return Response(
            export_svc.to_excel(rows, sheet_name="PPV Report"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=purchase_price_variance.xlsx"
            },
        )
    return StandardResponse(
        data=rows,
        message=f"{len(rows)} records.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# RPT-11  Open Purchase Commitments
# ---------------------------------------------------------------------------


@router.get(
    "/reports/open-purchase-commitments",
    response_model=None,
    summary="RPT-11: Open Purchase Commitments — open value per PO line",
    tags=["Purchase Reports"],
)
def rpt_11_open_purchase_commitments(
    company_id: UUID = Path(...),
    supplier_id: UUID | None = Query(None),
    fmt: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportService = Depends(get_report_service),
    export_svc: ReportExportService = Depends(get_report_export_service),
) -> Response | StandardResponse[list[dict[str, Any]]]:
    rows = svc.open_purchase_commitments(
        company_id, supplier_id=supplier_id, skip=skip, limit=limit
    )
    if fmt == "csv":
        return Response(
            export_svc.to_csv(rows),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=open_purchase_commitments.csv"
            },
        )
    if fmt == "xlsx":
        return Response(
            export_svc.to_excel(rows, sheet_name="Open Commitments"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=open_purchase_commitments.xlsx"
            },
        )
    return StandardResponse(
        data=rows,
        message=f"{len(rows)} records.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# RPT-12  Purchase Trend Analysis
# ---------------------------------------------------------------------------


@router.get(
    "/reports/purchase-trend-analysis",
    response_model=None,
    summary="RPT-12: Purchase Trend Analysis — monthly/quarterly aggregation",
    tags=["Purchase Reports"],
)
def rpt_12_purchase_trend_analysis(
    company_id: UUID = Path(...),
    granularity: str = Query("monthly", pattern="^(monthly|quarterly)$"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    fmt: str | None = Query(None),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportService = Depends(get_report_service),
    export_svc: ReportExportService = Depends(get_report_export_service),
) -> Response | StandardResponse[list[dict[str, Any]]]:
    from datetime import date as _date

    rows = svc.purchase_trend_analysis(
        company_id,
        granularity=granularity,
        date_from=_date.fromisoformat(date_from) if date_from else None,
        date_to=_date.fromisoformat(date_to) if date_to else None,
    )
    if fmt == "csv":
        return Response(
            export_svc.to_csv(rows),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=purchase_trend_analysis.csv"
            },
        )
    if fmt == "xlsx":
        return Response(
            export_svc.to_excel(rows, sheet_name="Purchase Trends"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=purchase_trend_analysis.xlsx"
            },
        )
    return StandardResponse(
        data=rows,
        message=f"{len(rows)} periods.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# RPT-13  Goods Rejection Analysis
# ---------------------------------------------------------------------------


@router.get(
    "/reports/goods-rejection-analysis",
    response_model=None,
    summary="RPT-13: Goods Rejection Analysis — grouped by supplier/reason/product",
    tags=["Purchase Reports"],
)
def rpt_13_goods_rejection_analysis(
    company_id: UUID = Path(...),
    supplier_id: UUID | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    fmt: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportService = Depends(get_report_service),
    export_svc: ReportExportService = Depends(get_report_export_service),
) -> Response | StandardResponse[list[dict[str, Any]]]:
    from datetime import date as _date

    rows = svc.goods_rejection_analysis(
        company_id,
        supplier_id=supplier_id,
        date_from=_date.fromisoformat(date_from) if date_from else None,
        date_to=_date.fromisoformat(date_to) if date_to else None,
        skip=skip,
        limit=limit,
    )
    if fmt == "csv":
        return Response(
            export_svc.to_csv(rows),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=goods_rejection_analysis.csv"
            },
        )
    if fmt == "xlsx":
        return Response(
            export_svc.to_excel(rows, sheet_name="Rejection Analysis"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=goods_rejection_analysis.xlsx"
            },
        )
    return StandardResponse(
        data=rows,
        message=f"{len(rows)} records.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# RPT-14  Procurement Audit Trail
# ---------------------------------------------------------------------------


@router.get(
    "/reports/procurement-audit-trail",
    response_model=None,
    summary="RPT-14: Procurement Audit Trail — full event history per document/supplier",
    tags=["Purchase Reports"],
)
def rpt_14_procurement_audit_trail(
    company_id: UUID = Path(...),
    document_type: str | None = Query(None),
    document_id: str | None = Query(None),
    supplier_id: UUID | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    fmt: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportService = Depends(get_report_service),
    export_svc: ReportExportService = Depends(get_report_export_service),
) -> Response | StandardResponse[list[dict[str, Any]]]:
    from datetime import date as _date

    rows = svc.procurement_audit_trail(
        company_id,
        document_type=document_type,
        document_id=document_id,
        supplier_id=supplier_id,
        date_from=_date.fromisoformat(date_from) if date_from else None,
        date_to=_date.fromisoformat(date_to) if date_to else None,
        skip=skip,
        limit=limit,
    )
    if fmt == "csv":
        return Response(
            export_svc.to_csv(rows),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=procurement_audit_trail.csv"
            },
        )
    if fmt == "xlsx":
        return Response(
            export_svc.to_excel(rows, sheet_name="Audit Trail"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=procurement_audit_trail.xlsx"
            },
        )
    return StandardResponse(
        data=rows,
        message=f"{len(rows)} events.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )


# ---------------------------------------------------------------------------
# KPI Dashboard endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/reports/kpis",
    summary="KPI Dashboard — all 10 procurement KPIs in one call",
    tags=["Purchase Reports"],
)
def get_purchase_kpis(
    company_id: UUID = Path(...),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: KPIService = Depends(get_kpi_service),
) -> StandardResponse[dict[str, Any]]:
    from datetime import date as _date

    kpis = svc.get_all_kpis(
        company_id,
        date_from=_date.fromisoformat(date_from) if date_from else None,
        date_to=_date.fromisoformat(date_to) if date_to else None,
    )
    return StandardResponse(
        data=kpis,
        message="All 10 KPIs computed.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow()),
    )

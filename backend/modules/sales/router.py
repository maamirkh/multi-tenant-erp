"""Sales module API router — Phase 0 + Phase 1 + Phase 2 + Phase 3 + Phase 4 + Phase 5 endpoints.

Phase 0 endpoints:
    GET  /health                    — module health check
    GET  /feature-flags             — list all feature flags with effective state
    PUT  /feature-flags/{key}       — update a feature flag override

    GET  /customer-categories       — list customer categories
    POST /customer-categories       — create customer category
    PUT  /customer-categories/{id}  — update customer category

    GET  /customer-groups           — list customer groups
    POST /customer-groups           — create customer group
    PUT  /customer-groups/{id}      — update customer group

    GET  /payment-terms             — list payment terms
    POST /payment-terms             — create payment term
    PUT  /payment-terms/{id}        — update payment term

    GET  /reason-codes              — list reason codes
    POST /reason-codes              — create reason code
    PUT  /reason-codes/{id}         — update reason code

    GET  /configuration             — get company sales configuration
    PUT  /configuration             — update company sales configuration

Phase 1 endpoints (Customer Master):
    GET  /customers                 — search/list customers
    POST /customers                 — create customer
    GET  /customers/{id}            — get customer detail
    PUT  /customers/{id}            — update customer
    POST /customers/{id}/transitions — execute status transition

    GET  /customers/{id}/contacts   — list contacts
    POST /customers/{id}/contacts   — add contact
    PUT  /customers/{id}/contacts/{cid} — update contact
    DELETE /customers/{id}/contacts/{cid} — delete contact

    GET  /customers/{id}/addresses  — list addresses
    POST /customers/{id}/addresses  — add address
    PUT  /customers/{id}/addresses/{aid} — update address
    DELETE /customers/{id}/addresses/{aid} — delete address

    GET  /customers/{id}/bank-details  — list bank details
    POST /customers/{id}/bank-details  — add bank detail
    PUT  /customers/{id}/bank-details/{bid} — update bank detail
    DELETE /customers/{id}/bank-details/{bid} — delete bank detail

    GET  /customers/{id}/notes      — list notes
    POST /customers/{id}/notes      — add note

    POST /customers/import          — bulk CSV import
    GET  /customers/export          — export customers to CSV

    PUT  /customers/{id}/credit     — update credit limit/status

Spec ref: specs/007-sales-management/spec.md §23 Functional Requirements
"""

from __future__ import annotations

import logging
from typing import Any
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
from pydantic import BaseModel
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
from modules.sales.constants import (
    MODULE_NAME,
    MODULE_VERSION,
    SALES_SETTINGS_MANAGE_PERMISSION,
)
from modules.sales.dependencies import (
    get_approval_service,
    get_customer_address_service,
    get_customer_bank_detail_service,
    get_customer_category_service,
    get_customer_contact_service,
    get_customer_export_service,
    get_customer_group_service,
    get_customer_import_service,
    get_customer_note_service,
    get_customer_service,
    get_customer_specific_price_service,
    get_delivery_service,
    get_discount_rule_service,
    get_invoice_service,
    get_kpi_service,
    get_margin_guard_service,
    get_order_line_service,
    get_order_service,
    get_price_entry_repo,
    get_price_list_service,
    get_pricing_service,
    get_quotation_line_service,
    get_quotation_service,
    get_report_export_service,
    get_report_service,
    get_return_service,
    get_sales_configuration_service,
    get_sales_feature_flag_service,
    get_sales_payment_term_service,
    get_sales_reason_code_service,
)
from modules.sales.repositories.pricing import PriceEntryRepository
from modules.sales.schemas.customer import (
    CustomerAddressCreate,
    CustomerAddressRead,
    CustomerAddressUpdate,
    CustomerBankDetailCreate,
    CustomerBankDetailRead,
    CustomerBankDetailUpdate,
    CustomerContactCreate,
    CustomerContactRead,
    CustomerContactUpdate,
    CustomerCreate,
    CustomerCreditUpdate,
    CustomerImportResult,
    CustomerListItem,
    CustomerNoteCreate,
    CustomerNoteRead,
    CustomerRead,
    CustomerStatusTransition,
    CustomerUpdate,
)
from modules.sales.schemas.delivery import (
    DeliveryNoteCreate,
    DeliveryNoteDispatch,
    DeliveryNoteLineRead,
    DeliveryNoteListItem,
    DeliveryNoteListResponse,
    DeliveryNoteRead,
)
from modules.sales.schemas.invoice import (
    InvoiceChargeRead,
    InvoiceCreate,
    InvoiceCreditNoteRequest,
    InvoiceIssueRequest,
    InvoiceLineRead,
    InvoiceListItem,
    InvoiceListResponse,
    InvoiceRead,
)
from modules.sales.schemas.master import (
    CustomerCategoryCreate,
    CustomerCategoryRead,
    CustomerCategoryUpdate,
    CustomerGroupCreate,
    CustomerGroupRead,
    CustomerGroupUpdate,
    SalesConfigurationRead,
    SalesConfigurationUpdate,
    SalesFeatureFlagRead,
    SalesFeatureFlagUpdate,
    SalesPaymentTermCreate,
    SalesPaymentTermRead,
    SalesPaymentTermUpdate,
    SalesReasonCodeCreate,
    SalesReasonCodeRead,
    SalesReasonCodeUpdate,
)
from modules.sales.schemas.order import (
    OrderApproveRequest,
    OrderCancelRequest,
    OrderCloseRequest,
    OrderLineCreate,
    OrderLineRead,
    OrderLineUpdate,
    OrderRejectRequest,
    OrderSubmitRequest,
    SalesApprovalMatrixCreate,
    SalesApprovalMatrixRead,
    SalesApprovalRecordRead,
    SalesMatrixRuleRead,
    SalesOrderCreate,
    SalesOrderListItem,
    SalesOrderRead,
    SalesOrderUpdate,
)
from modules.sales.schemas.pricing import (
    CustomerSpecificPriceCreate,
    CustomerSpecificPriceRead,
    CustomerSpecificPriceUpdate,
    DiscountRuleCreate,
    DiscountRuleRead,
    DiscountRuleUpdate,
    MarginCheckRequest,
    MarginCheckResponse,
    PriceEntryCreate,
    PriceEntryRead,
    PriceEntryUpdate,
    PriceListCreate,
    PriceListListItem,
    PriceListRead,
    PriceListUpdate,
    PriceResolutionResponse,
    PriceResolveRequest,
)
from modules.sales.schemas.quotation import (
    QuotationAcceptRequest,
    QuotationCancelRequest,
    QuotationConvertResponse,
    QuotationLineCreate,
    QuotationLineRead,
    QuotationLineUpdate,
    QuotationRejectRequest,
    QuotationRevisionRead,
    QuotationSendRequest,
    SalesQuotationCreate,
    SalesQuotationListItem,
    SalesQuotationRead,
    SalesQuotationUpdate,
)
from modules.sales.schemas.reports import (
    ExportFormat,
    ReportParams,
    ReportType,
)
from modules.sales.schemas.sales_return import (
    ReturnApproveRequest,
    ReturnCompleteRequest,
    ReturnLineRead,
    ReturnReceiveRequest,
    ReturnRejectRequest,
    SalesReturnCreate,
    SalesReturnListItem,
    SalesReturnListResponse,
    SalesReturnRead,
)
from modules.sales.services.approval_service import ApprovalService
from modules.sales.services.customer_export_service import CustomerExportService
from modules.sales.services.customer_import_service import CustomerImportService
from modules.sales.services.customer_service import (
    CustomerAddressService,
    CustomerBankDetailService,
    CustomerContactService,
    CustomerNoteService,
    CustomerService,
)
from modules.sales.services.delivery_service import DeliveryService
from modules.sales.services.feature_flag_service import SalesFeatureFlagService
from modules.sales.services.invoice_service import InvoiceService
from modules.sales.services.kpi_service import KPIService
from modules.sales.services.master_data_service import (
    CustomerCategoryService,
    CustomerGroupService,
    SalesConfigurationService,
    SalesPaymentTermService,
    SalesReasonCodeService,
)
from modules.sales.services.order_service import OrderLineService, OrderService
from modules.sales.services.permission_check import user_has_sales_permission
from modules.sales.services.pricing_service import (
    CustomerSpecificPriceService,
    DiscountRuleService,
    MarginGuardService,
    PriceListService,
    PricingService,
)
from modules.sales.services.quotation_service import (
    QuotationLineService,
    QuotationService,
)
from modules.sales.services.report_export_service import ReportExportService
from modules.sales.services.report_service import ReportService
from modules.sales.services.return_service import ReturnService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sales"])


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class SalesHealthData:
    pass


class SalesHealthResponse(BaseModel):
    status: str
    module: str
    version: str


@router.get(
    "/health",
    response_model=StandardResponse[SalesHealthResponse],
    summary="Sales module health check",
)
async def sales_health(
    user: CurrentUser = Depends(require_authenticated),
) -> StandardResponse[SalesHealthResponse]:
    now = utcnow()
    return StandardResponse(
        data=SalesHealthResponse(
            status="healthy",
            module=MODULE_NAME,
            version=MODULE_VERSION,
        ),
        message="Sales module is healthy",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
        ),
    )


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------


@router.get(
    "/feature-flags",
    response_model=StandardResponse[list[SalesFeatureFlagRead]],
    summary="List all sales feature flags",
)
async def list_feature_flags(
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    flag_service: SalesFeatureFlagService = Depends(get_sales_feature_flag_service),
) -> StandardResponse[list[SalesFeatureFlagRead]]:
    flags = flag_service.get_all(company_id=company_id)
    now = utcnow()
    return StandardResponse(
        data=[SalesFeatureFlagRead(**f) for f in flags],
        message=f"Retrieved {len(flags)} feature flags",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/feature-flags/{flag_key}",
    response_model=StandardResponse[SalesFeatureFlagRead],
    summary="Update a sales feature flag",
)
async def update_feature_flag(
    company_id: UUID = Path(...),
    flag_key: str = Path(...),
    body: SalesFeatureFlagUpdate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    flag_service: SalesFeatureFlagService = Depends(get_sales_feature_flag_service),
    db: Session = Depends(get_db),
) -> StandardResponse[SalesFeatureFlagRead]:
    # RBAC gap hardened (Epic 9A Phase 10, T139, plan.md §14): feature
    # flags can toggle module-wide behavior and had no permission check
    # beyond active tenant membership. Reuses the same
    # settings-management pattern already patched onto Accounting.
    if not user_has_sales_permission(
        db,
        company_id,
        user.user_id,
        SALES_SETTINGS_MANAGE_PERMISSION,
        user_roles=user.roles,
    ):
        raise ForbiddenException(
            message=(
                f"You do not have the '{SALES_SETTINGS_MANAGE_PERMISSION}' "
                "permission required to perform this action."
            ),
            details={"permission_code": SALES_SETTINGS_MANAGE_PERMISSION},
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
            company_id=company_id, capability_key="sales"
        ):
            raise CapabilityNotEntitledError(
                message=(
                    "Cannot enable this feature: the 'sales' capability is "
                    "not entitled under the current plan."
                ),
                details={"capability_key": "sales", "flag_key": flag_key},
            )

    try:
        if body.is_enabled:
            flag_service.enable(
                company_id=company_id,
                flag_key=flag_key,
                actor_id=user.user_id,
                description=body.description,
            )
        else:
            flag_service.disable(
                company_id=company_id,
                flag_key=flag_key,
                actor_id=user.user_id,
                description=body.description,
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    flags = flag_service.get_all(company_id=company_id)
    updated = next((f for f in flags if f["flag_key"] == flag_key), None)
    now = utcnow()
    return StandardResponse(
        data=SalesFeatureFlagRead(**updated) if updated else None,
        message=f"Feature flag '{flag_key}' updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Customer Categories
# ---------------------------------------------------------------------------


@router.get(
    "/customer-categories",
    response_model=StandardResponse[list[CustomerCategoryRead]],
    summary="List customer categories",
)
async def list_customer_categories(
    company_id: UUID = Path(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerCategoryService = Depends(get_customer_category_service),
) -> StandardResponse[list[CustomerCategoryRead]]:
    items, total = service.list_all(company_id=company_id, skip=skip, limit=limit)
    now = utcnow()
    return StandardResponse(
        data=[CustomerCategoryRead.model_validate(i) for i in items],
        message=f"Retrieved {len(items)} of {total} customer categories",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/customer-categories",
    response_model=StandardResponse[CustomerCategoryRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a customer category",
)
async def create_customer_category(
    company_id: UUID = Path(...),
    body: CustomerCategoryCreate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerCategoryService = Depends(get_customer_category_service),
) -> StandardResponse[CustomerCategoryRead]:
    try:
        category = service.create(
            company_id=company_id,
            code=body.code,
            name=body.name,
            description=body.description,
            default_payment_term_id=body.default_payment_term_id,
            default_credit_limit=float(body.default_credit_limit),
            created_by=user.user_id,
        )
    except ConflictException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    now = utcnow()
    return StandardResponse(
        data=CustomerCategoryRead.model_validate(category),
        message="Customer category created",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/customer-categories/{category_id}",
    response_model=StandardResponse[CustomerCategoryRead],
    summary="Update a customer category",
)
async def update_customer_category(
    company_id: UUID = Path(...),
    category_id: UUID = Path(...),
    body: CustomerCategoryUpdate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerCategoryService = Depends(get_customer_category_service),
) -> StandardResponse[CustomerCategoryRead]:
    try:
        category = service.update(
            company_id=company_id,
            category_id=category_id,
            **body.model_dump(exclude_unset=True),
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    now = utcnow()
    return StandardResponse(
        data=CustomerCategoryRead.model_validate(category),
        message="Customer category updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Customer Groups
# ---------------------------------------------------------------------------


@router.get(
    "/customer-groups",
    response_model=StandardResponse[list[CustomerGroupRead]],
    summary="List customer groups",
)
async def list_customer_groups(
    company_id: UUID = Path(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerGroupService = Depends(get_customer_group_service),
) -> StandardResponse[list[CustomerGroupRead]]:
    items, total = service.list_all(company_id=company_id, skip=skip, limit=limit)
    now = utcnow()
    return StandardResponse(
        data=[CustomerGroupRead.model_validate(i) for i in items],
        message=f"Retrieved {len(items)} of {total} customer groups",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/customer-groups",
    response_model=StandardResponse[CustomerGroupRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a customer group",
)
async def create_customer_group(
    company_id: UUID = Path(...),
    body: CustomerGroupCreate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerGroupService = Depends(get_customer_group_service),
) -> StandardResponse[CustomerGroupRead]:
    try:
        group = service.create(
            company_id=company_id,
            code=body.code,
            name=body.name,
            description=body.description,
            created_by=user.user_id,
        )
    except ConflictException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    now = utcnow()
    return StandardResponse(
        data=CustomerGroupRead.model_validate(group),
        message="Customer group created",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/customer-groups/{group_id}",
    response_model=StandardResponse[CustomerGroupRead],
    summary="Update a customer group",
)
async def update_customer_group(
    company_id: UUID = Path(...),
    group_id: UUID = Path(...),
    body: CustomerGroupUpdate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerGroupService = Depends(get_customer_group_service),
) -> StandardResponse[CustomerGroupRead]:
    try:
        group = service.update(
            company_id=company_id,
            group_id=group_id,
            **body.model_dump(exclude_unset=True),
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    now = utcnow()
    return StandardResponse(
        data=CustomerGroupRead.model_validate(group),
        message="Customer group updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Payment Terms
# ---------------------------------------------------------------------------


@router.get(
    "/payment-terms",
    response_model=StandardResponse[list[SalesPaymentTermRead]],
    summary="List sales payment terms",
)
async def list_payment_terms(
    company_id: UUID = Path(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(require_authenticated),
    service: SalesPaymentTermService = Depends(get_sales_payment_term_service),
) -> StandardResponse[list[SalesPaymentTermRead]]:
    items, total = service.list_all(company_id=company_id, skip=skip, limit=limit)
    now = utcnow()
    return StandardResponse(
        data=[SalesPaymentTermRead.model_validate(i) for i in items],
        message=f"Retrieved {len(items)} of {total} payment terms",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/payment-terms",
    response_model=StandardResponse[SalesPaymentTermRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a sales payment term",
)
async def create_payment_term(
    company_id: UUID = Path(...),
    body: SalesPaymentTermCreate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: SalesPaymentTermService = Depends(get_sales_payment_term_service),
) -> StandardResponse[SalesPaymentTermRead]:
    try:
        term = service.create(
            company_id=company_id,
            code=body.code,
            name=body.name,
            due_days=body.due_days,
            discount_days=body.discount_days,
            discount_percent=(
                float(body.discount_percent) if body.discount_percent else None
            ),
            description=body.description,
            created_by=user.user_id,
        )
    except ConflictException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    now = utcnow()
    return StandardResponse(
        data=SalesPaymentTermRead.model_validate(term),
        message="Payment term created",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/payment-terms/{term_id}",
    response_model=StandardResponse[SalesPaymentTermRead],
    summary="Update a sales payment term",
)
async def update_payment_term(
    company_id: UUID = Path(...),
    term_id: UUID = Path(...),
    body: SalesPaymentTermUpdate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: SalesPaymentTermService = Depends(get_sales_payment_term_service),
) -> StandardResponse[SalesPaymentTermRead]:
    try:
        term = service.update(
            company_id=company_id,
            term_id=term_id,
            **body.model_dump(exclude_unset=True),
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    now = utcnow()
    return StandardResponse(
        data=SalesPaymentTermRead.model_validate(term),
        message="Payment term updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Reason Codes
# ---------------------------------------------------------------------------


@router.get(
    "/reason-codes",
    response_model=StandardResponse[list[SalesReasonCodeRead]],
    summary="List sales reason codes",
)
async def list_reason_codes(
    company_id: UUID = Path(...),
    reason_type: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(require_authenticated),
    service: SalesReasonCodeService = Depends(get_sales_reason_code_service),
) -> StandardResponse[list[SalesReasonCodeRead]]:
    if reason_type:
        items = service.get_by_type(
            company_id=company_id, reason_type=reason_type.upper()
        )
        total = len(items)
    else:
        items, total = service.list_all(company_id=company_id, skip=skip, limit=limit)
    now = utcnow()
    return StandardResponse(
        data=[SalesReasonCodeRead.model_validate(i) for i in items],
        message=f"Retrieved {len(items)} of {total} reason codes",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/reason-codes",
    response_model=StandardResponse[SalesReasonCodeRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a sales reason code",
)
async def create_reason_code(
    company_id: UUID = Path(...),
    body: SalesReasonCodeCreate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: SalesReasonCodeService = Depends(get_sales_reason_code_service),
) -> StandardResponse[SalesReasonCodeRead]:
    try:
        reason = service.create(
            company_id=company_id,
            code=body.code,
            name=body.name,
            reason_type=body.reason_type,
            created_by=user.user_id,
        )
    except ConflictException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    now = utcnow()
    return StandardResponse(
        data=SalesReasonCodeRead.model_validate(reason),
        message="Reason code created",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/reason-codes/{reason_id}",
    response_model=StandardResponse[SalesReasonCodeRead],
    summary="Update a sales reason code",
)
async def update_reason_code(
    company_id: UUID = Path(...),
    reason_id: UUID = Path(...),
    body: SalesReasonCodeUpdate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: SalesReasonCodeService = Depends(get_sales_reason_code_service),
) -> StandardResponse[SalesReasonCodeRead]:
    try:
        reason = service.update(
            company_id=company_id,
            reason_id=reason_id,
            **body.model_dump(exclude_unset=True),
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    now = utcnow()
    return StandardResponse(
        data=SalesReasonCodeRead.model_validate(reason),
        message="Reason code updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Sales Configuration
# ---------------------------------------------------------------------------


@router.get(
    "/configuration",
    response_model=StandardResponse[SalesConfigurationRead],
    summary="Get company sales configuration",
)
async def get_configuration(
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: SalesConfigurationService = Depends(get_sales_configuration_service),
) -> StandardResponse[SalesConfigurationRead]:
    config = service.get_or_create(company_id=company_id)
    now = utcnow()
    return StandardResponse(
        data=SalesConfigurationRead.model_validate(config),
        message="Sales configuration retrieved",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/configuration",
    response_model=StandardResponse[SalesConfigurationRead],
    summary="Update company sales configuration",
)
async def update_configuration(
    company_id: UUID = Path(...),
    body: SalesConfigurationUpdate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: SalesConfigurationService = Depends(get_sales_configuration_service),
) -> StandardResponse[SalesConfigurationRead]:
    config = service.update(
        company_id=company_id,
        **body.model_dump(exclude_unset=True),
    )
    now = utcnow()
    return StandardResponse(
        data=SalesConfigurationRead.model_validate(config),
        message="Sales configuration updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Phase 1: Customers
# ---------------------------------------------------------------------------


@router.get(
    "/customers",
    response_model=StandardResponse[list[CustomerListItem]],
    summary="Search/list customers",
)
async def list_customers(
    company_id: UUID = Path(...),
    q: str | None = Query(None, description="Full-text search query"),
    status: str | None = Query(None),
    customer_type: str | None = Query(None),
    category_id: UUID | None = Query(None),
    group_id: UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerService = Depends(get_customer_service),
) -> StandardResponse[list[CustomerListItem]]:
    items, total = service.search(
        company_id=company_id,
        query=q,
        status=status,
        customer_type=customer_type,
        category_id=category_id,
        group_id=group_id,
        skip=skip,
        limit=limit,
    )
    now = utcnow()
    return StandardResponse(
        data=[CustomerListItem.model_validate(i) for i in items],
        message=f"Retrieved {len(items)} of {total} customers",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/customers",
    response_model=StandardResponse[CustomerRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new customer",
)
async def create_customer(
    company_id: UUID = Path(...),
    body: CustomerCreate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerService = Depends(get_customer_service),
) -> StandardResponse[CustomerRead]:
    try:
        customer = service.create(
            company_id=company_id,
            customer_code=body.customer_code,
            legal_name=body.legal_name,
            trading_name=body.trading_name,
            customer_type=body.customer_type,
            category_id=body.category_id,
            group_id=body.group_id,
            payment_term_id=body.payment_term_id,
            credit_limit=body.credit_limit,
            rating=body.rating,
            currency_code=body.currency_code,
            tax_registration_number=body.tax_registration_number,
            tax_exempt=body.tax_exempt,
            tax_exempt_certificate=body.tax_exempt_certificate,
            tax_exempt_expiry=body.tax_exempt_expiry,
            website=body.website,
            industry=body.industry,
            annual_revenue_range=body.annual_revenue_range,
            custom_fields=body.custom_fields,
            notes=body.notes,
            created_by=user.user_id,
        )
    except ConflictException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    now = utcnow()
    return StandardResponse(
        data=CustomerRead.model_validate(customer),
        message="Customer created",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/customers/{customer_id}",
    response_model=StandardResponse[CustomerRead],
    summary="Get customer detail",
)
async def get_customer(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerService = Depends(get_customer_service),
) -> StandardResponse[CustomerRead]:
    try:
        customer = service.get_by_id(company_id=company_id, customer_id=customer_id)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    now = utcnow()
    return StandardResponse(
        data=CustomerRead.model_validate(customer),
        message="Customer retrieved",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/customers/{customer_id}",
    response_model=StandardResponse[CustomerRead],
    summary="Update customer core fields",
)
async def update_customer(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    body: CustomerUpdate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerService = Depends(get_customer_service),
) -> StandardResponse[CustomerRead]:
    try:
        customer = service.update(
            company_id=company_id,
            customer_id=customer_id,
            updated_by=user.user_id,
            **body.model_dump(exclude_unset=True),
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    now = utcnow()
    return StandardResponse(
        data=CustomerRead.model_validate(customer),
        message="Customer updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/customers/{customer_id}/transitions",
    response_model=StandardResponse[CustomerRead],
    summary="Execute a customer status transition",
)
async def transition_customer(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    body: CustomerStatusTransition = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerService = Depends(get_customer_service),
) -> StandardResponse[CustomerRead]:
    try:
        customer = service.transition(
            company_id=company_id,
            customer_id=customer_id,
            action=body.action,
            actor_id=user.user_id,
            reason=body.reason,
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    now = utcnow()
    return StandardResponse(
        data=CustomerRead.model_validate(customer),
        message=f"Customer transition '{body.action}' executed",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/customers/{customer_id}/credit",
    response_model=StandardResponse[CustomerRead],
    summary="Update customer credit limit and status",
)
async def update_customer_credit(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    body: CustomerCreditUpdate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerService = Depends(get_customer_service),
) -> StandardResponse[CustomerRead]:
    try:
        customer = service.update_credit(
            company_id=company_id,
            customer_id=customer_id,
            credit_limit=body.credit_limit,
            credit_status=body.credit_status,
            actor_id=user.user_id,
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    now = utcnow()
    return StandardResponse(
        data=CustomerRead.model_validate(customer),
        message="Customer credit updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Customer Contacts
# ---------------------------------------------------------------------------


@router.get(
    "/customers/{customer_id}/contacts",
    response_model=StandardResponse[list[CustomerContactRead]],
    summary="List customer contacts",
)
async def list_customer_contacts(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerContactService = Depends(get_customer_contact_service),
) -> StandardResponse[list[CustomerContactRead]]:
    contacts = service.get_contacts(company_id=company_id, customer_id=customer_id)
    now = utcnow()
    return StandardResponse(
        data=[CustomerContactRead.model_validate(c) for c in contacts],
        message=f"Retrieved {len(contacts)} contacts",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/customers/{customer_id}/contacts",
    response_model=StandardResponse[CustomerContactRead],
    status_code=status.HTTP_201_CREATED,
    summary="Add a contact to a customer",
)
async def add_customer_contact(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    body: CustomerContactCreate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerContactService = Depends(get_customer_contact_service),
) -> StandardResponse[CustomerContactRead]:
    contact = service.add_contact(
        company_id=company_id,
        customer_id=customer_id,
        contact_name=body.contact_name,
        is_primary=body.is_primary,
        title=body.title,
        email=body.email,
        phone=body.phone,
        mobile=body.mobile,
        department=body.department,
        is_billing_contact=body.is_billing_contact,
        is_shipping_contact=body.is_shipping_contact,
        notes=body.notes,
        created_by=user.user_id,
    )
    now = utcnow()
    return StandardResponse(
        data=CustomerContactRead.model_validate(contact),
        message="Contact added",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/customers/{customer_id}/contacts/{contact_id}",
    response_model=StandardResponse[CustomerContactRead],
    summary="Update a customer contact",
)
async def update_customer_contact(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    contact_id: UUID = Path(...),
    body: CustomerContactUpdate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerContactService = Depends(get_customer_contact_service),
) -> StandardResponse[CustomerContactRead]:
    try:
        contact = service.update_contact(
            company_id=company_id,
            contact_id=contact_id,
            customer_id=customer_id,
            **body.model_dump(exclude_unset=True),
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    now = utcnow()
    return StandardResponse(
        data=CustomerContactRead.model_validate(contact),
        message="Contact updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.delete(
    "/customers/{customer_id}/contacts/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a customer contact",
)
async def delete_customer_contact(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    contact_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerContactService = Depends(get_customer_contact_service),
) -> Response:
    try:
        service.delete_contact(
            company_id=company_id,
            contact_id=contact_id,
            customer_id=customer_id,
            deleted_by=user.user_id,
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Customer Addresses
# ---------------------------------------------------------------------------


@router.get(
    "/customers/{customer_id}/addresses",
    response_model=StandardResponse[list[CustomerAddressRead]],
    summary="List customer addresses",
)
async def list_customer_addresses(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerAddressService = Depends(get_customer_address_service),
) -> StandardResponse[list[CustomerAddressRead]]:
    addresses = service.get_addresses(company_id=company_id, customer_id=customer_id)
    now = utcnow()
    return StandardResponse(
        data=[CustomerAddressRead.model_validate(a) for a in addresses],
        message=f"Retrieved {len(addresses)} addresses",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/customers/{customer_id}/addresses",
    response_model=StandardResponse[CustomerAddressRead],
    status_code=status.HTTP_201_CREATED,
    summary="Add an address to a customer",
)
async def add_customer_address(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    body: CustomerAddressCreate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerAddressService = Depends(get_customer_address_service),
) -> StandardResponse[CustomerAddressRead]:
    address = service.add_address(
        company_id=company_id,
        customer_id=customer_id,
        address_type=body.address_type,
        address_label=body.address_label,
        address_line_1=body.address_line_1,
        address_line_2=body.address_line_2,
        city=body.city,
        state_province=body.state_province,
        postal_code=body.postal_code,
        country_code=body.country_code,
        is_default_billing=body.is_default_billing,
        is_default_shipping=body.is_default_shipping,
        created_by=user.user_id,
    )
    now = utcnow()
    return StandardResponse(
        data=CustomerAddressRead.model_validate(address),
        message="Address added",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/customers/{customer_id}/addresses/{address_id}",
    response_model=StandardResponse[CustomerAddressRead],
    summary="Update a customer address",
)
async def update_customer_address(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    address_id: UUID = Path(...),
    body: CustomerAddressUpdate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerAddressService = Depends(get_customer_address_service),
) -> StandardResponse[CustomerAddressRead]:
    try:
        address = service.update_address(
            company_id=company_id,
            address_id=address_id,
            customer_id=customer_id,
            **body.model_dump(exclude_unset=True),
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    now = utcnow()
    return StandardResponse(
        data=CustomerAddressRead.model_validate(address),
        message="Address updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.delete(
    "/customers/{customer_id}/addresses/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a customer address",
)
async def delete_customer_address(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    address_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerAddressService = Depends(get_customer_address_service),
) -> Response:
    try:
        service.delete_address(
            company_id=company_id,
            address_id=address_id,
            customer_id=customer_id,
            deleted_by=user.user_id,
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Customer Bank Details
# ---------------------------------------------------------------------------


@router.get(
    "/customers/{customer_id}/bank-details",
    response_model=StandardResponse[list[CustomerBankDetailRead]],
    summary="List customer bank details",
)
async def list_customer_bank_details(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerBankDetailService = Depends(get_customer_bank_detail_service),
) -> StandardResponse[list[CustomerBankDetailRead]]:
    banks = service.get_bank_details(company_id=company_id, customer_id=customer_id)
    now = utcnow()
    return StandardResponse(
        data=[CustomerBankDetailRead.model_validate(b) for b in banks],
        message=f"Retrieved {len(banks)} bank details",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/customers/{customer_id}/bank-details",
    response_model=StandardResponse[CustomerBankDetailRead],
    status_code=status.HTTP_201_CREATED,
    summary="Add a bank detail to a customer",
)
async def add_customer_bank_detail(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    body: CustomerBankDetailCreate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerBankDetailService = Depends(get_customer_bank_detail_service),
) -> StandardResponse[CustomerBankDetailRead]:
    bank = service.add_bank_detail(
        company_id=company_id,
        customer_id=customer_id,
        bank_name=body.bank_name,
        branch_name=body.branch_name,
        account_number=body.account_number,
        iban=body.iban,
        swift_bic=body.swift_bic,
        account_holder_name=body.account_holder_name,
        is_default=body.is_default,
        created_by=user.user_id,
    )
    now = utcnow()
    return StandardResponse(
        data=CustomerBankDetailRead.model_validate(bank),
        message="Bank detail added",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/customers/{customer_id}/bank-details/{bank_id}",
    response_model=StandardResponse[CustomerBankDetailRead],
    summary="Update a customer bank detail",
)
async def update_customer_bank_detail(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    bank_id: UUID = Path(...),
    body: CustomerBankDetailUpdate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerBankDetailService = Depends(get_customer_bank_detail_service),
) -> StandardResponse[CustomerBankDetailRead]:
    try:
        bank = service.update_bank_detail(
            company_id=company_id,
            bank_id=bank_id,
            customer_id=customer_id,
            **body.model_dump(exclude_unset=True),
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    now = utcnow()
    return StandardResponse(
        data=CustomerBankDetailRead.model_validate(bank),
        message="Bank detail updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.delete(
    "/customers/{customer_id}/bank-details/{bank_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a customer bank detail",
)
async def delete_customer_bank_detail(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    bank_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerBankDetailService = Depends(get_customer_bank_detail_service),
) -> Response:
    try:
        service.delete_bank_detail(
            company_id=company_id,
            bank_id=bank_id,
            customer_id=customer_id,
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Customer Notes
# ---------------------------------------------------------------------------


@router.get(
    "/customers/{customer_id}/notes",
    response_model=StandardResponse[list[CustomerNoteRead]],
    summary="List customer notes",
)
async def list_customer_notes(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerNoteService = Depends(get_customer_note_service),
) -> StandardResponse[list[CustomerNoteRead]]:
    notes = service.get_notes(
        company_id=company_id, customer_id=customer_id, skip=skip, limit=limit
    )
    now = utcnow()
    return StandardResponse(
        data=[CustomerNoteRead.model_validate(n) for n in notes],
        message=f"Retrieved {len(notes)} notes",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/customers/{customer_id}/notes",
    response_model=StandardResponse[CustomerNoteRead],
    status_code=status.HTTP_201_CREATED,
    summary="Add a note to a customer",
)
async def add_customer_note(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    body: CustomerNoteCreate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerNoteService = Depends(get_customer_note_service),
) -> StandardResponse[CustomerNoteRead]:
    actor_id = require_user_id(user)
    actor_name = user.email or "System"
    note = service.add_note(
        company_id=company_id,
        customer_id=customer_id,
        content=body.content,
        author_id=actor_id,
        author_name=str(actor_name),
    )
    now = utcnow()
    return StandardResponse(
        data=CustomerNoteRead.model_validate(note),
        message="Note added",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Customer Import / Export
# ---------------------------------------------------------------------------


@router.post(
    "/customers/import",
    response_model=StandardResponse[CustomerImportResult],
    summary="Bulk import customers from CSV",
)
async def import_customers(
    company_id: UUID = Path(...),
    file: UploadFile = File(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerImportService = Depends(get_customer_import_service),
) -> StandardResponse[CustomerImportResult]:
    csv_bytes = await file.read()
    result = service.import_csv(
        company_id=company_id,
        csv_bytes=csv_bytes,
        created_by=user.user_id,
    )
    now = utcnow()
    return StandardResponse(
        data=CustomerImportResult(**result),
        message=f"Import complete: {result['imported']} imported, {result['skipped']} skipped",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/customers/export",
    summary="Export customers to CSV",
    response_class=Response,
)
async def export_customers(
    company_id: UUID = Path(...),
    status: str | None = Query(None),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerExportService = Depends(get_customer_export_service),
) -> Response:
    csv_bytes = service.export_csv(company_id=company_id, status=status)
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=customers.csv",
        },
    )


# ===========================================================================
# Phase 2: Pricing Engine
# ===========================================================================

# ---------------------------------------------------------------------------
# Price Lists
# ---------------------------------------------------------------------------


@router.get(
    "/price-lists",
    summary="List price lists",
    status_code=status.HTTP_200_OK,
)
async def list_price_lists(
    company_id: UUID = Path(...),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(require_authenticated),
    service: PriceListService = Depends(get_price_list_service),
) -> StandardResponse[list[PriceListListItem]]:
    items, total = service._repo.paginated(
        company_id=company_id,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    now = utcnow()
    return StandardResponse(
        data=[
            PriceListListItem.model_validate(pl, from_attributes=True) for pl in items
        ],
        message=f"{total} price list(s) found",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/price-lists",
    summary="Create price list",
    status_code=status.HTTP_201_CREATED,
)
async def create_price_list(
    body: PriceListCreate,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: PriceListService = Depends(get_price_list_service),
) -> StandardResponse[PriceListRead]:
    from uuid import UUID as _UUID

    try:
        pl = service.create(
            company_id=company_id,
            name=body.name,
            currency_code=body.currency_code,
            effective_from=body.effective_from,
            effective_to=body.effective_to,
            is_default=body.is_default,
            is_active=body.is_active,
            priority=body.priority,
            description=body.description,
            customer_group_id=(
                _UUID(body.customer_group_id) if body.customer_group_id else None
            ),
            customer_category_id=(
                _UUID(body.customer_category_id) if body.customer_category_id else None
            ),
            created_by=user.user_id,
        )
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=PriceListRead.model_validate(pl, from_attributes=True),
        message="Price list created",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/price-lists/{price_list_id}",
    summary="Get price list detail",
    status_code=status.HTTP_200_OK,
)
async def get_price_list(
    company_id: UUID = Path(...),
    price_list_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: PriceListService = Depends(get_price_list_service),
    entry_repo: PriceEntryRepository = Depends(get_price_entry_repo),
) -> StandardResponse[PriceListRead]:
    try:
        pl = service.get_by_id(company_id=company_id, price_list_id=price_list_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    entries = entry_repo.get_for_list(
        company_id=company_id, price_list_id=price_list_id
    )
    pl_data = PriceListRead.model_validate(pl, from_attributes=True)
    pl_data.entries = [
        PriceEntryRead.model_validate(e, from_attributes=True) for e in entries
    ]
    now = utcnow()
    return StandardResponse(
        data=pl_data,
        message="Price list retrieved",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/price-lists/{price_list_id}",
    summary="Update price list",
    status_code=status.HTTP_200_OK,
)
async def update_price_list(
    body: PriceListUpdate,
    company_id: UUID = Path(...),
    price_list_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: PriceListService = Depends(get_price_list_service),
) -> StandardResponse[PriceListRead]:
    try:
        pl = service.update(
            company_id=company_id,
            price_list_id=price_list_id,
            updated_by=user.user_id,
            **body.model_dump(exclude_none=True),
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=PriceListRead.model_validate(pl, from_attributes=True),
        message="Price list updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.delete(
    "/price-lists/{price_list_id}",
    summary="Delete price list",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_price_list(
    company_id: UUID = Path(...),
    price_list_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: PriceListService = Depends(get_price_list_service),
) -> None:
    try:
        service.delete(company_id=company_id, price_list_id=price_list_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------------------------------------------------------------------
# Price Entries (within a Price List)
# ---------------------------------------------------------------------------


@router.post(
    "/price-lists/{price_list_id}/entries",
    summary="Add price entry to price list",
    status_code=status.HTTP_201_CREATED,
)
async def add_price_entry(
    body: PriceEntryCreate,
    company_id: UUID = Path(...),
    price_list_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: PriceListService = Depends(get_price_list_service),
) -> StandardResponse[PriceEntryRead]:
    from uuid import UUID as _UUID

    try:
        entry = service.add_entry(
            company_id=company_id,
            price_list_id=price_list_id,
            product_id=_UUID(body.product_id),
            unit_price=body.unit_price,
            unit_of_measure=body.unit_of_measure,
            minimum_quantity=body.minimum_quantity,
            created_by=user.user_id,
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=PriceEntryRead.model_validate(entry, from_attributes=True),
        message="Price entry added",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/price-lists/{price_list_id}/entries/{entry_id}",
    summary="Update price entry",
    status_code=status.HTTP_200_OK,
)
async def update_price_entry(
    body: PriceEntryUpdate,
    company_id: UUID = Path(...),
    price_list_id: UUID = Path(...),
    entry_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: PriceListService = Depends(get_price_list_service),
) -> StandardResponse[PriceEntryRead]:
    try:
        entry = service.update_entry(
            company_id=company_id,
            entry_id=entry_id,
            **body.model_dump(exclude_none=True),
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=PriceEntryRead.model_validate(entry, from_attributes=True),
        message="Price entry updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.delete(
    "/price-lists/{price_list_id}/entries/{entry_id}",
    summary="Delete price entry",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_price_entry(
    company_id: UUID = Path(...),
    price_list_id: UUID = Path(...),
    entry_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: PriceListService = Depends(get_price_list_service),
) -> None:
    try:
        service.delete_entry(company_id=company_id, entry_id=entry_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------------------------------------------------------------------
# Customer-Specific Prices
# ---------------------------------------------------------------------------


@router.get(
    "/customer-prices",
    summary="List customer-specific prices",
    status_code=status.HTTP_200_OK,
)
async def list_customer_prices(
    company_id: UUID = Path(...),
    customer_id: UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerSpecificPriceService = Depends(
        get_customer_specific_price_service
    ),
) -> StandardResponse[list[CustomerSpecificPriceRead]]:
    items, total = service._repo.list_all(
        company_id=company_id,
        customer_id=customer_id,
        skip=skip,
        limit=limit,
    )
    now = utcnow()
    return StandardResponse(
        data=[
            CustomerSpecificPriceRead.model_validate(r, from_attributes=True)
            for r in items
        ],
        message=f"{total} record(s) found",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/customer-prices",
    summary="Create customer-specific price",
    status_code=status.HTTP_201_CREATED,
)
async def create_customer_price(
    body: CustomerSpecificPriceCreate,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerSpecificPriceService = Depends(
        get_customer_specific_price_service
    ),
) -> StandardResponse[CustomerSpecificPriceRead]:
    from uuid import UUID as _UUID

    record = service.create(
        company_id=company_id,
        customer_id=_UUID(body.customer_id),
        product_id=_UUID(body.product_id),
        unit_price=body.unit_price,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        minimum_quantity=body.minimum_quantity,
        created_by=user.user_id,
    )
    now = utcnow()
    return StandardResponse(
        data=CustomerSpecificPriceRead.model_validate(record, from_attributes=True),
        message="Customer-specific price created",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/customer-prices/{price_id}",
    summary="Get customer-specific price",
    status_code=status.HTTP_200_OK,
)
async def get_customer_price(
    company_id: UUID = Path(...),
    price_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerSpecificPriceService = Depends(
        get_customer_specific_price_service
    ),
) -> StandardResponse[CustomerSpecificPriceRead]:
    try:
        record = service.get_by_id(company_id=company_id, record_id=price_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=CustomerSpecificPriceRead.model_validate(record, from_attributes=True),
        message="Customer-specific price retrieved",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/customer-prices/{price_id}",
    summary="Update customer-specific price",
    status_code=status.HTTP_200_OK,
)
async def update_customer_price(
    body: CustomerSpecificPriceUpdate,
    company_id: UUID = Path(...),
    price_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerSpecificPriceService = Depends(
        get_customer_specific_price_service
    ),
) -> StandardResponse[CustomerSpecificPriceRead]:
    try:
        record = service.update(
            company_id=company_id,
            record_id=price_id,
            **body.model_dump(exclude_none=True),
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=CustomerSpecificPriceRead.model_validate(record, from_attributes=True),
        message="Customer-specific price updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.delete(
    "/customer-prices/{price_id}",
    summary="Delete customer-specific price",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_customer_price(
    company_id: UUID = Path(...),
    price_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CustomerSpecificPriceService = Depends(
        get_customer_specific_price_service
    ),
) -> None:
    try:
        service.delete(company_id=company_id, record_id=price_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------------------------------------------------------------------
# Discount Rules
# ---------------------------------------------------------------------------


@router.get(
    "/discount-rules",
    summary="List discount rules",
    status_code=status.HTTP_200_OK,
)
async def list_discount_rules(
    company_id: UUID = Path(...),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(require_authenticated),
    service: DiscountRuleService = Depends(get_discount_rule_service),
) -> StandardResponse[list[DiscountRuleRead]]:
    items, total = service._repo.paginated(
        company_id=company_id,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    now = utcnow()
    return StandardResponse(
        data=[DiscountRuleRead.model_validate(r, from_attributes=True) for r in items],
        message=f"{total} discount rule(s) found",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/discount-rules",
    summary="Create discount rule",
    status_code=status.HTTP_201_CREATED,
)
async def create_discount_rule(
    body: DiscountRuleCreate,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: DiscountRuleService = Depends(get_discount_rule_service),
) -> StandardResponse[DiscountRuleRead]:
    from uuid import UUID as _UUID

    rule = service.create(
        company_id=company_id,
        name=body.name,
        rule_type=body.rule_type,
        discount_value=body.discount_value,
        effective_from=body.effective_from,
        applicability=body.applicability,
        applicability_id=(
            _UUID(body.applicability_id) if body.applicability_id else None
        ),
        product_scope=body.product_scope,
        product_scope_id=(
            _UUID(body.product_scope_id) if body.product_scope_id else None
        ),
        minimum_quantity=body.minimum_quantity,
        minimum_order_value=body.minimum_order_value,
        effective_to=body.effective_to,
        is_active=body.is_active,
        priority=body.priority,
        is_stackable=body.is_stackable,
        created_by=user.user_id,
    )
    now = utcnow()
    return StandardResponse(
        data=DiscountRuleRead.model_validate(rule, from_attributes=True),
        message="Discount rule created",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/discount-rules/{rule_id}",
    summary="Get discount rule",
    status_code=status.HTTP_200_OK,
)
async def get_discount_rule(
    company_id: UUID = Path(...),
    rule_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: DiscountRuleService = Depends(get_discount_rule_service),
) -> StandardResponse[DiscountRuleRead]:
    try:
        rule = service.get_by_id(company_id=company_id, rule_id=rule_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=DiscountRuleRead.model_validate(rule, from_attributes=True),
        message="Discount rule retrieved",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/discount-rules/{rule_id}",
    summary="Update discount rule",
    status_code=status.HTTP_200_OK,
)
async def update_discount_rule(
    body: DiscountRuleUpdate,
    company_id: UUID = Path(...),
    rule_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: DiscountRuleService = Depends(get_discount_rule_service),
) -> StandardResponse[DiscountRuleRead]:
    try:
        rule = service.update(
            company_id=company_id,
            rule_id=rule_id,
            **body.model_dump(exclude_none=True),
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=DiscountRuleRead.model_validate(rule, from_attributes=True),
        message="Discount rule updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.delete(
    "/discount-rules/{rule_id}",
    summary="Delete discount rule",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_discount_rule(
    company_id: UUID = Path(...),
    rule_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: DiscountRuleService = Depends(get_discount_rule_service),
) -> None:
    try:
        service.delete(company_id=company_id, rule_id=rule_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------------------------------------------------------------------
# Price Resolution endpoint (test / integration endpoint)
# ---------------------------------------------------------------------------


@router.post(
    "/pricing/resolve",
    summary="Resolve product price using 7-level hierarchy",
    status_code=status.HTTP_200_OK,
)
async def resolve_price(
    body: PriceResolveRequest,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: PricingService = Depends(get_pricing_service),
) -> StandardResponse[PriceResolutionResponse]:
    from uuid import UUID as _UUID

    result = service.resolve_price(
        company_id=company_id,
        product_id=_UUID(body.product_id),
        quantity=body.quantity,
        customer_id=_UUID(body.customer_id) if body.customer_id else None,
        group_id=body.group_id,
        category_id=body.category_id,
        manual_price=body.manual_price,
        as_of_date=body.as_of_date,
    )
    now = utcnow()
    return StandardResponse(
        data=PriceResolutionResponse(
            unit_price=result.unit_price,
            price_source=result.price_source,
            resolution_level=result.resolution_level,
            price_list_id=result.price_list_id,
            price_list_name=result.price_list_name,
            price_entry_id=result.price_entry_id,
            customer_specific_price_id=result.customer_specific_price_id,
        ),
        message=f"Price resolved at level {result.resolution_level} ({result.price_source})",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/pricing/check-margin",
    summary="Check margin against minimum threshold",
    status_code=status.HTTP_200_OK,
)
async def check_margin(
    body: MarginCheckRequest,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: MarginGuardService = Depends(get_margin_guard_service),
) -> StandardResponse[MarginCheckResponse]:
    result = service.check_margin(
        unit_price=body.unit_price,
        cost_price=body.cost_price,
        min_margin_pct=body.min_margin_pct,
        block_on_low_margin=body.block_on_low_margin,
    )
    now = utcnow()
    return StandardResponse(
        data=MarginCheckResponse(
            margin_percentage=result.margin_percentage,
            passes=result.passes,
            action=result.action,
            threshold_pct=result.threshold_pct,
        ),
        message=f"Margin check: {result.action}",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ===========================================================================
# Phase 3 — Sales Quotations
# ===========================================================================


# ---------------------------------------------------------------------------
# Quotation CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/quotations",
    response_model=StandardResponse[SalesQuotationRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new sales quotation (DRAFT)",
)
async def create_quotation(
    body: SalesQuotationCreate,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: QuotationService = Depends(get_quotation_service),
    line_service: QuotationLineService = Depends(get_quotation_line_service),
) -> StandardResponse[SalesQuotationRead]:
    try:
        quot = service.create(
            company_id=company_id,
            data=body,
            created_by=require_user_id(user),
        )
        lines = line_service._line_repo.list_for_quotation(
            company_id, UUID(str(quot.id))
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    now = utcnow()
    data = SalesQuotationRead.model_validate(quot)
    data.lines = [QuotationLineRead.model_validate(ln) for ln in lines]
    return StandardResponse(
        data=data,
        message="Quotation created",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/quotations",
    response_model=StandardResponse[list[SalesQuotationListItem]],
    summary="List sales quotations",
)
async def list_quotations(
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: QuotationService = Depends(get_quotation_service),
    status_filter: str | None = Query(default=None, alias="status"),
    customer_id: UUID | None = Query(default=None),
    search: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> StandardResponse[list[SalesQuotationListItem]]:
    quotations = service.list(
        company_id=company_id,
        status=status_filter,
        customer_id=customer_id,
        search=search,
        skip=skip,
        limit=limit,
    )
    total = service.count(
        company_id=company_id, status=status_filter, customer_id=customer_id
    )
    now = utcnow()
    return StandardResponse(
        data=[SalesQuotationListItem.model_validate(q) for q in quotations],
        message=f"{len(quotations)} quotation(s) found",
        meta=ResponseMeta(
            request_id=REQUEST_ID_CONTEXT.get("-"),
            timestamp=now,
            total=total,
            skip=skip,
            limit=limit,
        ),
    )


@router.get(
    "/quotations/{quotation_id}",
    response_model=StandardResponse[SalesQuotationRead],
    summary="Get quotation by ID",
)
async def get_quotation(
    quotation_id: UUID,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: QuotationService = Depends(get_quotation_service),
    line_service: QuotationLineService = Depends(get_quotation_line_service),
) -> StandardResponse[SalesQuotationRead]:
    try:
        quot = service.get(company_id=company_id, quotation_id=quotation_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    lines = line_service._line_repo.list_for_quotation(company_id, quotation_id)
    now = utcnow()
    data = SalesQuotationRead.model_validate(quot)
    data.lines = [QuotationLineRead.model_validate(ln) for ln in lines]
    return StandardResponse(
        data=data,
        message="Quotation retrieved",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/quotations/{quotation_id}",
    response_model=StandardResponse[SalesQuotationRead],
    summary="Update a DRAFT quotation",
)
async def update_quotation(
    quotation_id: UUID,
    body: SalesQuotationUpdate,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: QuotationService = Depends(get_quotation_service),
    line_service: QuotationLineService = Depends(get_quotation_line_service),
) -> StandardResponse[SalesQuotationRead]:
    try:
        quot = service.update(
            company_id=company_id,
            quotation_id=quotation_id,
            data=body,
            updated_by=require_user_id(user),
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    lines = line_service._line_repo.list_for_quotation(company_id, quotation_id)
    now = utcnow()
    data = SalesQuotationRead.model_validate(quot)
    data.lines = [QuotationLineRead.model_validate(ln) for ln in lines]
    return StandardResponse(
        data=data,
        message="Quotation updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------


@router.post(
    "/quotations/{quotation_id}/send",
    response_model=StandardResponse[SalesQuotationRead],
    summary="Send quotation to customer (DRAFT → SENT_TO_CUSTOMER)",
)
async def send_quotation(
    quotation_id: UUID,
    body: QuotationSendRequest,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: QuotationService = Depends(get_quotation_service),
) -> StandardResponse[SalesQuotationRead]:
    try:
        quot = service.send(
            company_id=company_id,
            quotation_id=quotation_id,
            request=body,
            sent_by=require_user_id(user),
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    now = utcnow()
    return StandardResponse(
        data=SalesQuotationRead.model_validate(quot),
        message="Quotation sent to customer",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/quotations/{quotation_id}/accept",
    response_model=StandardResponse[SalesQuotationRead],
    summary="Accept quotation (SENT_TO_CUSTOMER → ACCEPTED)",
)
async def accept_quotation(
    quotation_id: UUID,
    body: QuotationAcceptRequest,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: QuotationService = Depends(get_quotation_service),
) -> StandardResponse[SalesQuotationRead]:
    try:
        quot = service.accept(
            company_id=company_id,
            quotation_id=quotation_id,
            request=body,
            accepted_by=require_user_id(user),
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    now = utcnow()
    return StandardResponse(
        data=SalesQuotationRead.model_validate(quot),
        message="Quotation accepted",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/quotations/{quotation_id}/reject",
    response_model=StandardResponse[SalesQuotationRead],
    summary="Reject quotation (SENT_TO_CUSTOMER → REJECTED)",
)
async def reject_quotation(
    quotation_id: UUID,
    body: QuotationRejectRequest,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: QuotationService = Depends(get_quotation_service),
) -> StandardResponse[SalesQuotationRead]:
    try:
        quot = service.reject(
            company_id=company_id,
            quotation_id=quotation_id,
            request=body,
            rejected_by=require_user_id(user),
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    now = utcnow()
    return StandardResponse(
        data=SalesQuotationRead.model_validate(quot),
        message="Quotation rejected",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/quotations/{quotation_id}/cancel",
    response_model=StandardResponse[SalesQuotationRead],
    summary="Cancel quotation from any live status",
)
async def cancel_quotation(
    quotation_id: UUID,
    body: QuotationCancelRequest,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: QuotationService = Depends(get_quotation_service),
) -> StandardResponse[SalesQuotationRead]:
    try:
        quot = service.cancel(
            company_id=company_id,
            quotation_id=quotation_id,
            request=body,
            cancelled_by=require_user_id(user),
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    now = utcnow()
    return StandardResponse(
        data=SalesQuotationRead.model_validate(quot),
        message="Quotation cancelled",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/quotations/{quotation_id}/expire",
    response_model=StandardResponse[SalesQuotationRead],
    summary="Mark quotation as EXPIRED (SENT_TO_CUSTOMER → EXPIRED)",
)
async def expire_quotation(
    quotation_id: UUID,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: QuotationService = Depends(get_quotation_service),
) -> StandardResponse[SalesQuotationRead]:
    try:
        quot = service.expire(
            company_id=company_id,
            quotation_id=quotation_id,
            expired_by=user.user_id,
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    now = utcnow()
    return StandardResponse(
        data=SalesQuotationRead.model_validate(quot),
        message="Quotation expired",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/quotations/{quotation_id}/convert",
    response_model=StandardResponse[QuotationConvertResponse],
    summary="Convert ACCEPTED quotation to Sales Order",
    status_code=status.HTTP_201_CREATED,
)
async def convert_quotation(
    quotation_id: UUID,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: QuotationService = Depends(get_quotation_service),
) -> StandardResponse[QuotationConvertResponse]:
    try:
        result = service.convert_to_order(
            company_id=company_id,
            quotation_id=quotation_id,
            converted_by=require_user_id(user),
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    now = utcnow()
    return StandardResponse(
        data=result,
        message=result.message,
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Quotation revision history
# ---------------------------------------------------------------------------


@router.get(
    "/quotations/{quotation_id}/revisions",
    response_model=StandardResponse[list[QuotationRevisionRead]],
    summary="Get revision history for a quotation",
)
async def get_quotation_revisions(
    quotation_id: UUID,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: QuotationService = Depends(get_quotation_service),
) -> StandardResponse[list[QuotationRevisionRead]]:
    from modules.sales.models.quotation import QuotationRevision  # noqa: PLC0415

    try:
        revisions: list[QuotationRevision] = service.get_revisions(
            company_id=company_id, quotation_id=quotation_id
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=[QuotationRevisionRead.model_validate(r) for r in revisions],
        message=f"{len(revisions)} revision(s)",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Quotation lines
# ---------------------------------------------------------------------------


@router.post(
    "/quotations/{quotation_id}/lines",
    response_model=StandardResponse[QuotationLineRead],
    status_code=status.HTTP_201_CREATED,
    summary="Add a line to a DRAFT quotation",
)
async def add_quotation_line(
    quotation_id: UUID,
    body: QuotationLineCreate,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: QuotationLineService = Depends(get_quotation_line_service),
) -> StandardResponse[QuotationLineRead]:
    try:
        line = service.add_line(
            company_id=company_id,
            quotation_id=quotation_id,
            data=body,
            added_by=user.user_id,
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    now = utcnow()
    return StandardResponse(
        data=QuotationLineRead.model_validate(line),
        message="Line added",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/quotations/{quotation_id}/lines/{line_id}",
    response_model=StandardResponse[QuotationLineRead],
    summary="Update a line on a DRAFT quotation",
)
async def update_quotation_line(
    quotation_id: UUID,
    line_id: UUID,
    body: QuotationLineUpdate,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: QuotationLineService = Depends(get_quotation_line_service),
) -> StandardResponse[QuotationLineRead]:
    try:
        line = service.update_line(
            company_id=company_id,
            quotation_id=quotation_id,
            line_id=line_id,
            data=body,
            updated_by=user.user_id,
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    now = utcnow()
    return StandardResponse(
        data=QuotationLineRead.model_validate(line),
        message="Line updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.delete(
    "/quotations/{quotation_id}/lines/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a line from a DRAFT quotation",
)
async def delete_quotation_line(
    quotation_id: UUID,
    line_id: UUID,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: QuotationLineService = Depends(get_quotation_line_service),
) -> Response:
    try:
        service.delete_line(
            company_id=company_id,
            quotation_id=quotation_id,
            line_id=line_id,
            deleted_by=user.user_id,
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ===========================================================================
# Phase 4 — Sales Orders
# ===========================================================================


# ---------------------------------------------------------------------------
# Sales Order CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/sales-orders",
    response_model=StandardResponse[list[SalesOrderListItem]],
    summary="List Sales Orders",
)
async def list_sales_orders(
    company_id: UUID = Path(...),
    status_filter: str | None = Query(default=None, alias="status"),
    customer_id: UUID | None = Query(default=None),
    search: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(require_authenticated),
    svc: OrderService = Depends(get_order_service),
) -> StandardResponse[list[SalesOrderListItem]]:
    orders = svc.list_orders(
        company_id=company_id,
        status=status_filter,
        customer_id=customer_id,
        search=search,
        skip=skip,
        limit=limit,
    )
    now = utcnow()
    return StandardResponse(
        data=[SalesOrderListItem.model_validate(o) for o in orders],
        message=f"Retrieved {len(orders)} orders",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/sales-orders",
    response_model=StandardResponse[SalesOrderRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a Sales Order",
)
async def create_sales_order(
    payload: SalesOrderCreate,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: OrderService = Depends(get_order_service),
    line_svc: OrderLineService = Depends(get_order_line_service),
) -> StandardResponse[SalesOrderRead]:
    try:
        order = svc.create_order(
            company_id=company_id,
            data=payload,
            created_by=require_user_id(user),
        )
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    order_obj, lines = svc.get_order_with_lines(company_id, order.id)
    read = SalesOrderRead.model_validate(order_obj)
    read.lines = [OrderLineRead.model_validate(ln) for ln in lines]

    now = utcnow()
    return StandardResponse(
        data=read,
        message=f"Sales order {order.order_number} created",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/sales-orders/{order_id}",
    response_model=StandardResponse[SalesOrderRead],
    summary="Get Sales Order detail",
)
async def get_sales_order(
    order_id: UUID,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: OrderService = Depends(get_order_service),
) -> StandardResponse[SalesOrderRead]:
    try:
        order, lines = svc.get_order_with_lines(company_id, order_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    read = SalesOrderRead.model_validate(order)
    read.lines = [OrderLineRead.model_validate(ln) for ln in lines]

    now = utcnow()
    return StandardResponse(
        data=read,
        message="Sales order retrieved",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/sales-orders/{order_id}",
    response_model=StandardResponse[SalesOrderRead],
    summary="Update a DRAFT Sales Order",
)
async def update_sales_order(
    order_id: UUID,
    payload: SalesOrderUpdate,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: OrderService = Depends(get_order_service),
) -> StandardResponse[SalesOrderRead]:
    try:
        order = svc.update_order(company_id=company_id, order_id=order_id, data=payload)
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    order_obj, lines = svc.get_order_with_lines(company_id, order.id)
    read = SalesOrderRead.model_validate(order_obj)
    read.lines = [OrderLineRead.model_validate(ln) for ln in lines]

    now = utcnow()
    return StandardResponse(
        data=read,
        message="Sales order updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Sales Order State Transitions
# ---------------------------------------------------------------------------


@router.post(
    "/sales-orders/{order_id}/submit",
    response_model=StandardResponse[SalesOrderRead],
    summary="Submit order for approval",
)
async def submit_sales_order(
    order_id: UUID,
    payload: OrderSubmitRequest,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: OrderService = Depends(get_order_service),
) -> StandardResponse[SalesOrderRead]:
    try:
        order, auto_approved = svc.submit_for_approval(
            company_id=company_id,
            order_id=order_id,
            submitted_by=payload.submitted_by,
        )
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    order_obj, lines = svc.get_order_with_lines(company_id, order.id)
    read = SalesOrderRead.model_validate(order_obj)
    read.lines = [OrderLineRead.model_validate(ln) for ln in lines]
    msg = "Order auto-approved." if auto_approved else "Order submitted for approval."

    now = utcnow()
    return StandardResponse(
        data=read,
        message=msg,
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/sales-orders/{order_id}/approve",
    response_model=StandardResponse[SalesOrderRead],
    summary="Approve a Sales Order",
)
async def approve_sales_order(
    order_id: UUID,
    payload: OrderApproveRequest,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: OrderService = Depends(get_order_service),
) -> StandardResponse[SalesOrderRead]:
    try:
        order = svc.approve_order(
            company_id=company_id,
            order_id=order_id,
            approver_id=payload.approver_id,
            comments=payload.comments,
        )
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    order_obj, lines = svc.get_order_with_lines(company_id, order.id)
    read = SalesOrderRead.model_validate(order_obj)
    read.lines = [OrderLineRead.model_validate(ln) for ln in lines]

    now = utcnow()
    return StandardResponse(
        data=read,
        message="Order approved.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/sales-orders/{order_id}/reject",
    response_model=StandardResponse[SalesOrderRead],
    summary="Reject a Sales Order",
)
async def reject_sales_order(
    order_id: UUID,
    payload: OrderRejectRequest,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: OrderService = Depends(get_order_service),
) -> StandardResponse[SalesOrderRead]:
    try:
        order = svc.reject_order(
            company_id=company_id,
            order_id=order_id,
            approver_id=payload.approver_id,
            rejection_reason=payload.rejection_reason,
            comments=payload.comments,
        )
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    order_obj, lines = svc.get_order_with_lines(company_id, order.id)
    read = SalesOrderRead.model_validate(order_obj)
    read.lines = [OrderLineRead.model_validate(ln) for ln in lines]

    now = utcnow()
    return StandardResponse(
        data=read,
        message="Order rejected and returned to DRAFT for revision.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/sales-orders/{order_id}/cancel",
    response_model=StandardResponse[SalesOrderRead],
    summary="Cancel a Sales Order",
)
async def cancel_sales_order(
    order_id: UUID,
    payload: OrderCancelRequest,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: OrderService = Depends(get_order_service),
) -> StandardResponse[SalesOrderRead]:
    try:
        order = svc.cancel_order(
            company_id=company_id,
            order_id=order_id,
            data=payload,
        )
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    order_obj, lines = svc.get_order_with_lines(company_id, order.id)
    read = SalesOrderRead.model_validate(order_obj)
    read.lines = [OrderLineRead.model_validate(ln) for ln in lines]

    now = utcnow()
    return StandardResponse(
        data=read,
        message="Order cancelled.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/sales-orders/{order_id}/close",
    response_model=StandardResponse[SalesOrderRead],
    summary="Close an invoiced Sales Order",
)
async def close_sales_order(
    order_id: UUID,
    payload: OrderCloseRequest,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: OrderService = Depends(get_order_service),
) -> StandardResponse[SalesOrderRead]:
    try:
        order = svc.close_order(
            company_id=company_id,
            order_id=order_id,
            closed_by=payload.closed_by,
        )
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    order_obj, lines = svc.get_order_with_lines(company_id, order.id)
    read = SalesOrderRead.model_validate(order_obj)
    read.lines = [OrderLineRead.model_validate(ln) for ln in lines]

    now = utcnow()
    return StandardResponse(
        data=read,
        message="Order closed.",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Order Lines
# ---------------------------------------------------------------------------


@router.post(
    "/sales-orders/{order_id}/lines",
    response_model=StandardResponse[OrderLineRead],
    status_code=status.HTTP_201_CREATED,
    summary="Add a line to a Sales Order",
)
async def add_order_line(
    order_id: UUID,
    payload: OrderLineCreate,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: OrderLineService = Depends(get_order_line_service),
) -> StandardResponse[OrderLineRead]:
    try:
        line = svc.add_line(company_id=company_id, order_id=order_id, data=payload)
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    now = utcnow()
    return StandardResponse(
        data=OrderLineRead.model_validate(line),
        message="Order line added",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.put(
    "/sales-orders/{order_id}/lines/{line_id}",
    response_model=StandardResponse[OrderLineRead],
    summary="Update an order line",
)
async def update_order_line(
    order_id: UUID,
    line_id: UUID,
    payload: OrderLineUpdate,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: OrderLineService = Depends(get_order_line_service),
) -> StandardResponse[OrderLineRead]:
    try:
        line = svc.update_line(
            company_id=company_id,
            order_id=order_id,
            line_id=line_id,
            data=payload,
        )
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    now = utcnow()
    return StandardResponse(
        data=OrderLineRead.model_validate(line),
        message="Order line updated",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.delete(
    "/sales-orders/{order_id}/lines/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an order line",
)
async def delete_order_line(
    order_id: UUID,
    line_id: UUID,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: OrderLineService = Depends(get_order_line_service),
) -> Response:
    try:
        svc.delete_line(company_id=company_id, order_id=order_id, line_id=line_id)
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Approval Matrix Configuration
# ---------------------------------------------------------------------------


@router.get(
    "/approval-matrices",
    response_model=StandardResponse[list[SalesApprovalMatrixRead]],
    summary="List approval matrices",
)
async def list_approval_matrices(
    company_id: UUID = Path(...),
    document_type: str | None = Query(default=None),
    user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[list[SalesApprovalMatrixRead]]:
    matrices = svc._matrix_repo.list_for_company(company_id, document_type)
    result: list[SalesApprovalMatrixRead] = []
    for m in matrices:
        rules = svc._rule_repo.list_for_matrix(company_id, m.id)
        matrix_read = SalesApprovalMatrixRead.model_validate(m)
        matrix_read.rules = [SalesMatrixRuleRead.model_validate(r) for r in rules]
        result.append(matrix_read)

    now = utcnow()
    return StandardResponse(
        data=result,
        message=f"Retrieved {len(matrices)} approval matrices",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/approval-matrices",
    response_model=StandardResponse[SalesApprovalMatrixRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create an approval matrix",
)
async def create_approval_matrix(
    payload: SalesApprovalMatrixCreate,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[SalesApprovalMatrixRead]:
    from modules.sales.models.approval import (  # noqa: PLC0415
        SalesApprovalMatrix,
        SalesMatrixRule,
    )

    matrix = SalesApprovalMatrix(
        company_id=company_id,
        name=payload.name,
        document_type=payload.document_type,
        is_active=payload.is_active,
        created_by=user.user_id,
    )
    svc._db.add(matrix)
    svc._db.flush()

    rules_created = []
    for rule_data in payload.rules:
        rule = SalesMatrixRule(
            company_id=company_id,
            matrix_id=str(matrix.id),
            approval_level=rule_data.approval_level,
            min_amount=rule_data.min_amount,
            max_amount=rule_data.max_amount,
            approver_role=rule_data.approver_role,
            approver_user_id=(
                str(rule_data.approver_user_id) if rule_data.approver_user_id else None
            ),
            customer_category_id=(
                str(rule_data.customer_category_id)
                if rule_data.customer_category_id
                else None
            ),
            auto_approve=rule_data.auto_approve,
            created_by=user.user_id,
        )
        svc._db.add(rule)
        rules_created.append(rule)

    svc._db.flush()
    svc._db.commit()

    matrix_read = SalesApprovalMatrixRead.model_validate(matrix)

    now = utcnow()
    return StandardResponse(
        data=matrix_read,
        message=f"Approval matrix '{matrix.name}' created",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Pending Approvals Inbox
# ---------------------------------------------------------------------------


@router.get(
    "/approvals/pending",
    response_model=StandardResponse[list[SalesApprovalRecordRead]],
    summary="Get pending approvals for a user",
)
async def get_pending_approvals(
    company_id: UUID = Path(...),
    approver_id: UUID = Query(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[list[SalesApprovalRecordRead]]:
    records = svc.get_pending_approvals_for_user(company_id, approver_id)
    now = utcnow()
    return StandardResponse(
        data=[SalesApprovalRecordRead.model_validate(r) for r in records],
        message=f"Retrieved {len(records)} pending approvals",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/sales-orders/{order_id}/approvals",
    response_model=StandardResponse[list[SalesApprovalRecordRead]],
    summary="Get approval history for an order",
)
async def get_order_approval_history(
    order_id: UUID,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: ApprovalService = Depends(get_approval_service),
) -> StandardResponse[list[SalesApprovalRecordRead]]:
    records = svc.get_approval_history(company_id, "SALES_ORDER", order_id)
    now = utcnow()
    return StandardResponse(
        data=[SalesApprovalRecordRead.model_validate(r) for r in records],
        message=f"Retrieved {len(records)} approval records",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ---------------------------------------------------------------------------
# Phase 5 — Delivery Notes
# ---------------------------------------------------------------------------


@router.get(
    "/delivery-notes",
    summary="List delivery notes",
    status_code=status.HTTP_200_OK,
)
async def list_delivery_notes(
    company_id: UUID = Path(...),
    order_id: UUID | None = Query(None),
    dn_status: str | None = Query(None, alias="status"),
    customer_id: UUID | None = Query(None),
    dispatch_date_from: str | None = Query(None),
    dispatch_date_to: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(require_authenticated),
    svc: DeliveryService = Depends(get_delivery_service),
) -> StandardResponse[DeliveryNoteListResponse]:
    items, total = svc.list_delivery_notes(
        company_id,
        order_id=order_id,
        status=dn_status,
        customer_id=customer_id,
        dispatch_date_from=dispatch_date_from,
        dispatch_date_to=dispatch_date_to,
        limit=limit,
        offset=skip,
    )
    now = utcnow()
    return StandardResponse(
        data=DeliveryNoteListResponse(
            items=[
                DeliveryNoteListItem.model_validate(dn, from_attributes=True)
                for dn in items
            ],
            total=total,
            limit=limit,
            offset=skip,
        ),
        message=f"{total} delivery note(s) found",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/delivery-notes",
    summary="Create delivery note",
    status_code=status.HTTP_201_CREATED,
)
async def create_delivery_note(
    body: DeliveryNoteCreate,
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: DeliveryService = Depends(get_delivery_service),
) -> StandardResponse[DeliveryNoteRead]:
    try:
        dn = svc.create_delivery_note(
            company_id=company_id,
            data=body,
            created_by=require_user_id(user),
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=DeliveryNoteRead.model_validate(dn, from_attributes=True),
        message="Delivery note created",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/delivery-notes/{dn_id}",
    summary="Get delivery note",
    status_code=status.HTTP_200_OK,
)
async def get_delivery_note(
    company_id: UUID = Path(...),
    dn_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: DeliveryService = Depends(get_delivery_service),
) -> StandardResponse[DeliveryNoteRead]:
    try:
        dn = svc.get_delivery_note(company_id, dn_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=DeliveryNoteRead.model_validate(dn, from_attributes=True),
        message="Delivery note retrieved",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/delivery-notes/{dn_id}/dispatch",
    summary="Dispatch a delivery note (DRAFT → DISPATCHED)",
    status_code=status.HTTP_200_OK,
)
async def dispatch_delivery_note(
    body: DeliveryNoteDispatch,
    company_id: UUID = Path(...),
    dn_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: DeliveryService = Depends(get_delivery_service),
) -> StandardResponse[DeliveryNoteRead]:
    try:
        dn = svc.dispatch(
            company_id=company_id,
            delivery_note_id=dn_id,
            data=body,
            dispatched_by=require_user_id(user),
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=DeliveryNoteRead.model_validate(dn, from_attributes=True),
        message="Delivery note dispatched",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/delivery-notes/{dn_id}/deliver",
    summary="Mark delivery note as delivered (DISPATCHED → DELIVERED)",
    status_code=status.HTTP_200_OK,
)
async def deliver_delivery_note(
    company_id: UUID = Path(...),
    dn_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: DeliveryService = Depends(get_delivery_service),
) -> StandardResponse[DeliveryNoteRead]:
    try:
        dn = svc.mark_delivered(
            company_id=company_id,
            delivery_note_id=dn_id,
            updated_by=require_user_id(user),
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=DeliveryNoteRead.model_validate(dn, from_attributes=True),
        message="Delivery note marked as delivered",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/delivery-notes/{dn_id}/cancel",
    summary="Cancel a delivery note",
    status_code=status.HTTP_200_OK,
)
async def cancel_delivery_note(
    company_id: UUID = Path(...),
    dn_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: DeliveryService = Depends(get_delivery_service),
) -> StandardResponse[DeliveryNoteRead]:
    try:
        dn = svc.cancel(
            company_id=company_id,
            delivery_note_id=dn_id,
            cancelled_by=require_user_id(user),
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=DeliveryNoteRead.model_validate(dn, from_attributes=True),
        message="Delivery note cancelled",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/delivery-notes/{dn_id}/lines",
    summary="List delivery note lines",
    status_code=status.HTTP_200_OK,
)
async def list_delivery_note_lines(
    company_id: UUID = Path(...),
    dn_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: DeliveryService = Depends(get_delivery_service),
) -> StandardResponse[list[DeliveryNoteLineRead]]:
    try:
        svc.get_delivery_note(company_id, dn_id)  # validates existence + tenant
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    lines = svc._dn_line_repo.list_for_delivery_note(company_id, dn_id)
    now = utcnow()
    return StandardResponse(
        data=[
            DeliveryNoteLineRead.model_validate(ln, from_attributes=True)
            for ln in lines
        ],
        message=f"{len(lines)} line(s) found",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ===========================================================================
# Sales Invoice endpoints — Phase 6
# ===========================================================================


@router.get(
    "/invoices",
    summary="List sales invoices",
    tags=["sales", "invoices"],
)
async def list_invoices(
    company_id: UUID = Path(...),
    customer_id: str | None = None,
    status: str | None = None,
    order_id: str | None = None,
    delivery_note_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: CurrentUser = Depends(require_authenticated),
    svc: InvoiceService = Depends(get_invoice_service),
) -> StandardResponse[InvoiceListResponse]:
    items, total = svc.list_invoices(
        company_id,
        customer_id=customer_id,
        status=status,
        order_id=order_id,
        delivery_note_id=delivery_note_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    now = utcnow()
    return StandardResponse(
        data=InvoiceListResponse(
            items=[
                InvoiceListItem.model_validate(i, from_attributes=True) for i in items
            ],
            total=total,
            limit=limit,
            offset=offset,
        ),
        message=f"{total} invoice(s) found",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/invoices",
    summary="Create sales invoice (DRAFT)",
    status_code=status.HTTP_201_CREATED,
    tags=["sales", "invoices"],
)
async def create_invoice(
    company_id: UUID = Path(...),
    payload: InvoiceCreate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: InvoiceService = Depends(get_invoice_service),
) -> StandardResponse[InvoiceRead]:
    try:
        invoice = svc.create_invoice(
            company_id, payload, created_by=require_user_id(user)
        )
    except (NotFoundException, ConflictException) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if isinstance(exc, NotFoundException)
                else status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        )
    now = utcnow()
    return StandardResponse(
        data=InvoiceRead.model_validate(invoice, from_attributes=True),
        message="Invoice created",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/invoices/{invoice_id}",
    summary="Get sales invoice",
    tags=["sales", "invoices"],
)
async def get_invoice(
    company_id: UUID = Path(...),
    invoice_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: InvoiceService = Depends(get_invoice_service),
) -> StandardResponse[InvoiceRead]:
    try:
        invoice = svc.get_invoice(company_id, invoice_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=InvoiceRead.model_validate(invoice, from_attributes=True),
        message="Invoice retrieved",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/invoices/{invoice_id}/issue",
    summary="Issue a sales invoice (DRAFT → ISSUED)",
    tags=["sales", "invoices"],
)
async def issue_invoice(
    company_id: UUID = Path(...),
    invoice_id: UUID = Path(...),
    payload: InvoiceIssueRequest = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: InvoiceService = Depends(get_invoice_service),
) -> StandardResponse[InvoiceRead]:
    try:
        invoice = svc.issue_invoice(
            company_id, invoice_id, payload, issued_by=require_user_id(user)
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=InvoiceRead.model_validate(invoice, from_attributes=True),
        message="Invoice issued",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/invoices/{invoice_id}/cancel",
    summary="Cancel a sales invoice (DRAFT → CANCELLED)",
    tags=["sales", "invoices"],
)
async def cancel_invoice(
    company_id: UUID = Path(...),
    invoice_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: InvoiceService = Depends(get_invoice_service),
) -> StandardResponse[InvoiceRead]:
    try:
        invoice = svc.cancel_invoice(
            company_id, invoice_id, cancelled_by=require_user_id(user)
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=InvoiceRead.model_validate(invoice, from_attributes=True),
        message="Invoice cancelled",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/invoices/{invoice_id}/credit-note",
    summary="Issue credit note against ISSUED invoice",
    tags=["sales", "invoices"],
)
async def issue_credit_note(
    company_id: UUID = Path(...),
    invoice_id: UUID = Path(...),
    payload: InvoiceCreditNoteRequest = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: InvoiceService = Depends(get_invoice_service),
) -> StandardResponse[InvoiceRead]:
    try:
        invoice = svc.issue_credit_note(
            company_id, invoice_id, payload, issued_by=require_user_id(user)
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=InvoiceRead.model_validate(invoice, from_attributes=True),
        message="Credit note issued",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/invoices/{invoice_id}/lines",
    summary="List invoice lines",
    tags=["sales", "invoices"],
)
async def list_invoice_lines(
    company_id: UUID = Path(...),
    invoice_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: InvoiceService = Depends(get_invoice_service),
) -> StandardResponse[list[InvoiceLineRead]]:
    try:
        svc.get_invoice(company_id, invoice_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    lines = svc.get_invoice_lines(company_id, invoice_id)
    now = utcnow()
    return StandardResponse(
        data=[InvoiceLineRead.model_validate(ln, from_attributes=True) for ln in lines],
        message=f"{len(lines)} line(s) found",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/invoices/{invoice_id}/charges",
    summary="List invoice charges",
    tags=["sales", "invoices"],
)
async def list_invoice_charges(
    company_id: UUID = Path(...),
    invoice_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: InvoiceService = Depends(get_invoice_service),
) -> StandardResponse[list[InvoiceChargeRead]]:
    try:
        svc.get_invoice(company_id, invoice_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    charges = svc.get_invoice_charges(company_id, invoice_id)
    now = utcnow()
    return StandardResponse(
        data=[
            InvoiceChargeRead.model_validate(ch, from_attributes=True) for ch in charges
        ],
        message=f"{len(charges)} charge(s) found",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/invoices/{invoice_id}/export",
    summary="Export invoice as PDF (feature-flagged)",
    tags=["sales", "invoices"],
)
async def export_invoice_pdf(
    company_id: UUID = Path(...),
    invoice_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: InvoiceService = Depends(get_invoice_service),
) -> Response:
    try:
        pdf_bytes = svc.export_pdf(company_id, invoice_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=invoice-{invoice_id}.pdf"
        },
    )


# ---------------------------------------------------------------------------
# Phase 7 — Sales Returns
# ---------------------------------------------------------------------------


@router.get(
    "/returns",
    summary="List sales returns",
    tags=["sales", "returns"],
)
async def list_sales_returns(
    company_id: UUID = Path(...),
    customer_id: str | None = Query(None),
    status: str | None = Query(None),
    order_id: str | None = Query(None),
    resolution_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(require_authenticated),
    svc: ReturnService = Depends(get_return_service),
) -> StandardResponse[SalesReturnListResponse]:
    items, total = svc.list_returns(
        company_id,
        customer_id=customer_id,
        status=status,
        order_id=order_id,
        resolution_type=resolution_type,
        limit=limit,
        offset=offset,
    )
    now = utcnow()
    return StandardResponse(
        data=SalesReturnListResponse(
            items=[
                SalesReturnListItem.model_validate(r, from_attributes=True)
                for r in items
            ],
            total=total,
            limit=limit,
            offset=offset,
        ).model_dump(),
        message=f"{total} return(s) found",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/returns",
    summary="Create a sales return (DRAFT)",
    status_code=status.HTTP_201_CREATED,
    tags=["sales", "returns"],
)
async def create_sales_return(
    company_id: UUID = Path(...),
    data: SalesReturnCreate = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: ReturnService = Depends(get_return_service),
) -> StandardResponse[dict[str, Any]]:
    try:
        sales_return = svc.create_return(
            company_id, data, created_by=require_user_id(user)
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    now = utcnow()
    lines = svc.get_return_lines(company_id, sales_return.id)
    read = SalesReturnRead.model_validate(sales_return, from_attributes=True)
    read.lines = [
        ReturnLineRead.model_validate(ln, from_attributes=True) for ln in lines
    ]
    return StandardResponse(
        data=read.model_dump(),
        message=f"Sales return {sales_return.return_number} created",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/returns/{return_id}",
    summary="Get sales return detail",
    tags=["sales", "returns"],
)
async def get_sales_return(
    company_id: UUID = Path(...),
    return_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: ReturnService = Depends(get_return_service),
) -> StandardResponse[dict[str, Any]]:
    try:
        sales_return = svc.get_return(company_id, return_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    lines = svc.get_return_lines(company_id, return_id)
    now = utcnow()
    read = SalesReturnRead.model_validate(sales_return, from_attributes=True)
    read.lines = [
        ReturnLineRead.model_validate(ln, from_attributes=True) for ln in lines
    ]
    return StandardResponse(
        data=read.model_dump(),
        message="Sales return retrieved",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/returns/{return_id}/submit",
    summary="Submit return for approval (DRAFT → PENDING_APPROVAL)",
    tags=["sales", "returns"],
)
async def submit_sales_return(
    company_id: UUID = Path(...),
    return_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: ReturnService = Depends(get_return_service),
) -> StandardResponse[SalesReturnRead]:
    try:
        sales_return = svc.submit_return(
            company_id, return_id, submitted_by=require_user_id(user)
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=SalesReturnRead.model_validate(
            sales_return, from_attributes=True
        ).model_dump(),
        message=f"Return {sales_return.return_number} submitted for approval",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/returns/{return_id}/approve",
    summary="Approve return (PENDING_APPROVAL → APPROVED)",
    tags=["sales", "returns"],
)
async def approve_sales_return(
    company_id: UUID = Path(...),
    return_id: UUID = Path(...),
    data: ReturnApproveRequest = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: ReturnService = Depends(get_return_service),
) -> StandardResponse[SalesReturnRead]:
    try:
        sales_return = svc.approve_return(
            company_id, return_id, data, approved_by=require_user_id(user)
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=SalesReturnRead.model_validate(
            sales_return, from_attributes=True
        ).model_dump(),
        message=f"Return {sales_return.return_number} approved",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/returns/{return_id}/reject",
    summary="Reject return (PENDING_APPROVAL → REJECTED)",
    tags=["sales", "returns"],
)
async def reject_sales_return(
    company_id: UUID = Path(...),
    return_id: UUID = Path(...),
    data: ReturnRejectRequest = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: ReturnService = Depends(get_return_service),
) -> StandardResponse[SalesReturnRead]:
    try:
        sales_return = svc.reject_return(
            company_id, return_id, data, rejected_by=require_user_id(user)
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=SalesReturnRead.model_validate(
            sales_return, from_attributes=True
        ).model_dump(),
        message=f"Return {sales_return.return_number} rejected",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/returns/{return_id}/receive",
    summary="Receive returned goods (APPROVED → RECEIVED)",
    tags=["sales", "returns"],
)
async def receive_sales_return(
    company_id: UUID = Path(...),
    return_id: UUID = Path(...),
    data: ReturnReceiveRequest = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: ReturnService = Depends(get_return_service),
) -> StandardResponse[dict[str, Any]]:
    try:
        sales_return = svc.receive_return(
            company_id, return_id, data, received_by=require_user_id(user)
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    now = utcnow()
    lines = svc.get_return_lines(company_id, return_id)
    read = SalesReturnRead.model_validate(sales_return, from_attributes=True)
    read.lines = [
        ReturnLineRead.model_validate(ln, from_attributes=True) for ln in lines
    ]
    return StandardResponse(
        data=read.model_dump(),
        message=f"Return {sales_return.return_number} received",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/returns/{return_id}/complete",
    summary="Complete return with resolution (RECEIVED → COMPLETED)",
    tags=["sales", "returns"],
)
async def complete_sales_return(
    company_id: UUID = Path(...),
    return_id: UUID = Path(...),
    data: ReturnCompleteRequest = Body(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: ReturnService = Depends(get_return_service),
) -> StandardResponse[SalesReturnRead]:
    try:
        sales_return = svc.complete_return(
            company_id, return_id, data, completed_by=require_user_id(user)
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=SalesReturnRead.model_validate(
            sales_return, from_attributes=True
        ).model_dump(),
        message=f"Return {sales_return.return_number} completed",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.post(
    "/returns/{return_id}/cancel",
    summary="Cancel return (DRAFT | PENDING_APPROVAL → CANCELLED)",
    tags=["sales", "returns"],
)
async def cancel_sales_return(
    company_id: UUID = Path(...),
    return_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: ReturnService = Depends(get_return_service),
) -> StandardResponse[SalesReturnRead]:
    try:
        sales_return = svc.cancel_return(
            company_id, return_id, cancelled_by=require_user_id(user)
        )
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=SalesReturnRead.model_validate(
            sales_return, from_attributes=True
        ).model_dump(),
        message=f"Return {sales_return.return_number} cancelled",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/returns/{return_id}/lines",
    summary="List return lines",
    tags=["sales", "returns"],
)
async def list_return_lines(
    company_id: UUID = Path(...),
    return_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    svc: ReturnService = Depends(get_return_service),
) -> StandardResponse[list[ReturnLineRead]]:
    try:
        lines = svc.get_return_lines(company_id, return_id)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    now = utcnow()
    return StandardResponse(
        data=[ReturnLineRead.model_validate(ln, from_attributes=True) for ln in lines],
        message=f"{len(lines)} line(s) found",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


# ===========================================================================
# Phase 8 — Sales Intelligence & Reporting
# ===========================================================================
#
# GET  /reports/{report_type}          — run a named report
# GET  /reports/{report_type}/export   — export report as CSV or Excel
# GET  /kpis                           — KPI dashboard


@router.get(
    "/reports/{report_type}",
    summary="Run a named sales report",
    tags=["sales", "reports"],
)
async def get_sales_report(
    company_id: UUID = Path(...),
    report_type: ReportType = Path(..., description="Report type identifier"),
    date_from: str | None = Query(default=None, description="Start date YYYY-MM-DD"),
    date_to: str | None = Query(default=None, description="End date YYYY-MM-DD"),
    customer_id: str | None = Query(default=None),
    sales_rep_id: str | None = Query(default=None),
    currency_code: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_authenticated),
    svc: ReportService = Depends(get_report_service),
) -> StandardResponse[dict[str, Any]]:
    params = ReportParams(
        date_from=date_from,
        date_to=date_to,
        customer_id=customer_id,
        sales_rep_id=sales_rep_id,
        currency_code=currency_code,
        limit=limit,
        offset=offset,
    )
    report = svc.run_report(report_type, str(company_id), params)
    now = utcnow()
    return StandardResponse(
        data=report.model_dump(),
        message=f"Report '{report_type.value}' returned {report.total} row(s)",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )


@router.get(
    "/reports/{report_type}/export",
    summary="Export a sales report as CSV or Excel",
    tags=["sales", "reports"],
)
async def export_sales_report(
    company_id: UUID = Path(...),
    report_type: ReportType = Path(...),
    fmt: ExportFormat = Query(default=ExportFormat.CSV, description="csv or excel"),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    sales_rep_id: str | None = Query(default=None),
    currency_code: str | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_authenticated),
    report_svc: ReportService = Depends(get_report_service),
    export_svc: ReportExportService = Depends(get_report_export_service),
) -> Response:
    params = ReportParams(
        date_from=date_from,
        date_to=date_to,
        customer_id=customer_id,
        sales_rep_id=sales_rep_id,
        currency_code=currency_code,
        limit=limit,
        offset=offset,
    )
    report = report_svc.run_report(report_type, str(company_id), params)
    file_bytes, filename, content_type = export_svc.export(report, fmt)
    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/kpis",
    summary="Get KPI dashboard for the company and period",
    tags=["sales", "reports"],
)
async def get_kpi_dashboard(
    company_id: UUID = Path(...),
    date_from: str | None = Query(default=None, description="Start date YYYY-MM-DD"),
    date_to: str | None = Query(default=None, description="End date YYYY-MM-DD"),
    user: CurrentUser = Depends(require_authenticated),
    svc: KPIService = Depends(get_kpi_service),
) -> StandardResponse[dict[str, Any]]:
    dashboard = svc.get_dashboard(str(company_id), date_from=date_from, date_to=date_to)
    now = utcnow()
    return StandardResponse(
        data=dashboard.model_dump(),
        message=f"{len(dashboard.kpis)} KPIs computed for period '{dashboard.period_label}'",
        meta=ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=now),
    )

"""Inventory module API router — Phase 0 + Phase 1 + Phase 2 endpoints.

Endpoints (Phase 0):
    GET  /api/v1/inventory/health
    GET  /api/v1/companies/{company_id}/inventory/feature-flags
    PUT  /api/v1/companies/{company_id}/inventory/feature-flags/{flag_key}

Endpoints (Phase 1 — master data):
    /categories, /brands, /uom, /uom-conversions,
    /attributes, /attribute-sets, /tags, /reason-codes, /custom-fields

Endpoints (Phase 2 — Product Master):
    /products, /products/{id}, /products/{id}/status,
    /products/{id}/variants, /products/{id}/barcodes

Spec ref: specs/005-inventory-management/spec.md §14
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Path,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy.orm import Session

from core.auth.dependencies import require_authenticated
from core.auth.interfaces import CurrentUser
from core.database.session import get_db
from core.logging.setup import REQUEST_ID_CONTEXT
from core.schemas.response import ResponseMeta, StandardResponse
from core.utils.datetime import utcnow
from modules.inventory.constants import (
    INVENTORY_FLAG_BY_KEY,
    INVENTORY_SETTINGS_MANAGE_PERMISSION,
    MODULE_NAME,
    MODULE_VERSION,
)
from modules.inventory.dependencies import (
    get_adjustment_service,
    get_alert_repo,
    get_attr_definition_service,
    get_attr_set_service,
    get_brand_service,
    get_bulk_import_service,
    get_category_service,
    get_custom_field_service,
    get_export_service,
    get_feature_flag_service,
    get_import_job_repo,
    get_kpi_service,
    get_product_enrichment_service,
    get_product_service,
    get_reason_code_service,
    get_reorder_rule_repo,
    get_report_service,
    get_stock_ledger_service,
    get_suggestion_repo,
    get_tag_service,
    get_transfer_service,
    get_uom_conversion_service,
    get_uom_service,
    get_warehouse_service,
)
from modules.inventory.exceptions import InventoryPermissionDeniedError
from modules.inventory.models.product import Product
from modules.inventory.repositories.alerts_repository import (
    LowStockAlertRepository,
    ReorderRuleRepository,
    ReorderSuggestionRepository,
)
from modules.inventory.repositories.product_enrichment_repository import (
    ImportJobRepository,
)
from modules.inventory.schemas.adjustment import (
    AdjustmentApproveRequest,
    AdjustmentCreateRequest,
    AdjustmentRejectRequest,
    AdjustmentResponse,
    AdjustmentSubmitRequest,
)
from modules.inventory.schemas.alerts import (
    AlertAcknowledgeRequest,
    LowStockAlertResponse,
    ReorderRuleCreate,
    ReorderRuleResponse,
    ReorderRuleUpdate,
    ReorderSuggestionResponse,
    SuggestionAcknowledgeRequest,
)
from modules.inventory.schemas.base import (
    FeatureFlagResponse,
    FeatureFlagUpdateRequest,
    PaginatedResponse,
)
from modules.inventory.schemas.enrichment import (
    CustomFieldValueResponse,
    CustomFieldValueSetRequest,
    ImportJobResponse,
    InternalNoteResponse,
    NoteAddRequest,
    ProductImageResponse,
    ProductTagResponse,
    TagAssignRequest,
)
from modules.inventory.schemas.master_data import (
    AttributeDefinitionCreateRequest,
    AttributeDefinitionResponse,
    AttributeDefinitionUpdateRequest,
    AttributeSetCreateRequest,
    AttributeSetMembershipAddRequest,
    AttributeSetMembershipResponse,
    AttributeSetResponse,
    BrandCreateRequest,
    BrandResponse,
    BrandUpdateRequest,
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
    CustomFieldCreateRequest,
    CustomFieldResponse,
    CustomFieldUpdateRequest,
    ReasonCodeCreateRequest,
    ReasonCodeResponse,
    ReasonCodeUpdateRequest,
    TagCreateRequest,
    TagResponse,
    TagUpdateRequest,
    UOMConversionCreateRequest,
    UOMConversionResponse,
    UOMCreateRequest,
    UOMResponse,
    UOMUpdateRequest,
)
from modules.inventory.schemas.product import (
    BarcodeAddRequest,
    BarcodeResponse,
    LabelData,
    LookupResult,
    ProductCreateRequest,
    ProductResponse,
    ProductStatusRequest,
    ProductUpdateRequest,
    VariantCreateRequest,
    VariantResponse,
)
from modules.inventory.schemas.reports import (
    CategoryBrandReport,
    DeadStockReport,
    ExportResponse,
    InventorySummaryReport,
    InventoryValuationReport,
    KPIDashboard,
    MovementVelocityReport,
    OperationalReport,
    StockAgingReport,
    StockLedgerReport,
    StockPositionReport,
    TrendAnalysisReport,
    WarehouseUtilisationReport,
)
from modules.inventory.schemas.stock import (
    AdjustmentRequest,
    OpeningStockRequest,
    SnapshotCreateRequest,
    SnapshotLineResponse,
    SnapshotResponse,
    StockMovementResponse,
    StockPositionResponse,
)
from modules.inventory.schemas.transfer import (
    StockReleaseRequest,
    StockReservationResponse,
    StockReserveRequest,
    TransferCancelRequest,
    TransferCreateRequest,
    TransferResponse,
)
from modules.inventory.schemas.warehouse import (
    LocationCreateRequest,
    LocationResponse,
    LocationUpdateRequest,
    WarehouseCreateRequest,
    WarehouseResponse,
    WarehouseUpdateRequest,
)
from modules.inventory.services.adjustment_service import AdjustmentService
from modules.inventory.services.bulk_import_service import BulkImportService
from modules.inventory.services.category_service import CategoryService
from modules.inventory.services.export_service import ExportService
from modules.inventory.services.feature_flag_service import FeatureFlagService
from modules.inventory.services.kpi_service import KPIService
from modules.inventory.services.master_data_service import (
    AttributeDefinitionService,
    AttributeSetService,
    BrandService,
    CustomFieldService,
    ReasonCodeService,
    TagService,
    UOMConversionService,
    UOMService,
)
from modules.inventory.services.permission_check import user_has_inventory_permission
from modules.inventory.services.product_enrichment_service import (
    ProductEnrichmentService,
)
from modules.inventory.services.product_service import ProductService
from modules.inventory.services.report_service import ReportQueryService
from modules.inventory.services.stock_service import StockLedgerService
from modules.inventory.services.transfer_service import TransferService
from modules.inventory.services.warehouse_service import (
    InvalidWarehouseStateTransitionError,
    LocationCodeConflictError,
    LocationNotFoundError,
    WarehouseHasStockError,
    WarehouseService,
)
from modules.platform_admin.exceptions import CapabilityNotEntitledError
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)

logger = logging.getLogger(__name__)


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow())


router = APIRouter(tags=["inventory"])


# =============================================================================
# Module health (Phase 0)
# =============================================================================


@router.get(
    "/health",
    summary="Inventory module health",
    description="Returns module version and status.",
)
async def inventory_health() -> dict[str, str]:
    return {
        "module": MODULE_NAME,
        "version": MODULE_VERSION,
        "status": "operational",
    }


# =============================================================================
# Feature flags (Phase 0)
# =============================================================================


@router.get(
    "/feature-flags",
    response_model=StandardResponse[list[FeatureFlagResponse]],
    summary="List inventory feature flags",
)
def list_feature_flags(
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    flag_service: FeatureFlagService = Depends(get_feature_flag_service),
) -> StandardResponse[list[FeatureFlagResponse]]:
    flags = flag_service.get_all(company_id=company_id)
    return StandardResponse(
        data=[FeatureFlagResponse(**f) for f in flags],
        message="Feature flags retrieved successfully",
        meta=_meta(),
    )


@router.put(
    "/feature-flags/{flag_key}",
    response_model=StandardResponse[FeatureFlagResponse],
    summary="Update an inventory feature flag",
    status_code=status.HTTP_200_OK,
)
def update_feature_flag(
    company_id: UUID = Path(...),
    flag_key: str = Path(...),
    body: FeatureFlagUpdateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    flag_service: FeatureFlagService = Depends(get_feature_flag_service),
    db: Session = Depends(get_db),
) -> StandardResponse[FeatureFlagResponse]:
    # RBAC gap hardened (Epic 9A Phase 10, T138, plan.md §14): feature
    # flags can toggle module-wide behavior and had no permission check
    # beyond active tenant membership. Reuses the same
    # settings-management pattern already patched onto Accounting.
    if not user_has_inventory_permission(
        db,
        company_id,
        current_user.user_id,
        INVENTORY_SETTINGS_MANAGE_PERMISSION,
        user_roles=current_user.roles,
    ):
        raise InventoryPermissionDeniedError(INVENTORY_SETTINGS_MANAGE_PERMISSION)

    if flag_key not in INVENTORY_FLAG_BY_KEY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature flag '{flag_key}' not found.",
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
            company_id=company_id, capability_key="inventory"
        ):
            raise CapabilityNotEntitledError(
                message=(
                    "Cannot enable this feature: the 'inventory' capability "
                    "is not entitled under the current plan."
                ),
                details={"capability_key": "inventory", "flag_key": flag_key},
            )
        flag_service.enable(
            company_id=company_id,
            flag_key=flag_key,
            actor_id=current_user.user_id,
            description=body.description,
        )
    else:
        flag_service.disable(
            company_id=company_id,
            flag_key=flag_key,
            actor_id=current_user.user_id,
            description=body.description,
        )
    all_flags = flag_service.get_all(company_id=company_id)
    updated = next(f for f in all_flags if f["flag_key"] == flag_key)
    return StandardResponse(
        data=FeatureFlagResponse(**updated),
        message=f"Feature flag {'enabled' if body.is_enabled else 'disabled'} successfully",
        meta=_meta(),
    )


# =============================================================================
# Categories (Phase 1)
# =============================================================================


@router.post(
    "/categories",
    response_model=StandardResponse[CategoryResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a category",
)
def create_category(
    company_id: UUID = Path(...),
    body: CategoryCreateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: CategoryService = Depends(get_category_service),
) -> StandardResponse[CategoryResponse]:
    category = svc.create(
        company_id=company_id,
        code=body.code,
        name=body.name,
        description=body.description,
        parent_id=body.parent_id,
        sort_order=body.sort_order,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=CategoryResponse.model_validate(category),
        message="Category created successfully",
        meta=_meta(),
    )


@router.get(
    "/categories",
    response_model=StandardResponse[list[CategoryResponse]],
    summary="List categories (tree)",
)
def list_categories(
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: CategoryService = Depends(get_category_service),
) -> StandardResponse[list[CategoryResponse]]:
    categories = svc.get_tree(company_id=company_id)
    return StandardResponse(
        data=[CategoryResponse.model_validate(c) for c in categories],
        message="Categories retrieved successfully",
        meta=_meta(),
    )


@router.get(
    "/categories/{category_id}",
    response_model=StandardResponse[CategoryResponse],
    summary="Get a category by ID",
)
def get_category(
    company_id: UUID = Path(...),
    category_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: CategoryService = Depends(get_category_service),
) -> StandardResponse[CategoryResponse]:
    category = svc.get_by_id(company_id=company_id, category_id=category_id)
    return StandardResponse(
        data=CategoryResponse.model_validate(category),
        message="Category retrieved successfully",
        meta=_meta(),
    )


@router.patch(
    "/categories/{category_id}",
    response_model=StandardResponse[CategoryResponse],
    summary="Update a category",
)
def update_category(
    company_id: UUID = Path(...),
    category_id: UUID = Path(...),
    body: CategoryUpdateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: CategoryService = Depends(get_category_service),
) -> StandardResponse[CategoryResponse]:
    category = svc.update(
        company_id=company_id,
        category_id=category_id,
        name=body.name,
        description=body.description,
        sort_order=body.sort_order,
        parent_id=body.parent_id,
        code=body.code,
    )
    return StandardResponse(
        data=CategoryResponse.model_validate(category),
        message="Category updated successfully",
        meta=_meta(),
    )


@router.post(
    "/categories/{category_id}/deactivate",
    response_model=StandardResponse[CategoryResponse],
    summary="Deactivate a category",
)
def deactivate_category(
    company_id: UUID = Path(...),
    category_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: CategoryService = Depends(get_category_service),
) -> StandardResponse[CategoryResponse]:
    category = svc.deactivate(company_id=company_id, category_id=category_id)
    return StandardResponse(
        data=CategoryResponse.model_validate(category),
        message="Category deactivated",
        meta=_meta(),
    )


@router.post(
    "/categories/{category_id}/activate",
    response_model=StandardResponse[CategoryResponse],
    summary="Activate a category",
)
def activate_category(
    company_id: UUID = Path(...),
    category_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: CategoryService = Depends(get_category_service),
) -> StandardResponse[CategoryResponse]:
    category = svc.activate(company_id=company_id, category_id=category_id)
    return StandardResponse(
        data=CategoryResponse.model_validate(category),
        message="Category activated",
        meta=_meta(),
    )


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a category",
)
def delete_category(
    company_id: UUID = Path(...),
    category_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: CategoryService = Depends(get_category_service),
) -> None:
    svc.delete(company_id=company_id, category_id=category_id)


# =============================================================================
# Brands (Phase 1)
# =============================================================================


@router.post(
    "/brands",
    response_model=StandardResponse[BrandResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a brand",
)
def create_brand(
    company_id: UUID = Path(...),
    body: BrandCreateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: BrandService = Depends(get_brand_service),
) -> StandardResponse[BrandResponse]:
    brand = svc.create(
        company_id=company_id,
        code=body.code,
        name=body.name,
        country_of_origin=body.country_of_origin,
        logo_url=body.logo_url,
        website=body.website,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=BrandResponse.model_validate(brand),
        message="Brand created successfully",
        meta=_meta(),
    )


@router.get(
    "/brands",
    response_model=StandardResponse[PaginatedResponse[BrandResponse]],
    summary="List brands",
)
def list_brands(
    company_id: UUID = Path(...),
    page: int = 1,
    page_size: int = 20,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: BrandService = Depends(get_brand_service),
) -> StandardResponse[PaginatedResponse[BrandResponse]]:
    skip = (page - 1) * page_size
    items, total = svc.list(company_id=company_id, skip=skip, limit=page_size)
    return StandardResponse(
        data=PaginatedResponse.from_paginated(
            items=[BrandResponse.model_validate(b) for b in items],
            total=total,
            page=page,
            page_size=page_size,
        ),
        message="Brands retrieved successfully",
        meta=_meta(),
    )


@router.get(
    "/brands/{brand_id}",
    response_model=StandardResponse[BrandResponse],
    summary="Get a brand by ID",
)
def get_brand(
    company_id: UUID = Path(...),
    brand_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: BrandService = Depends(get_brand_service),
) -> StandardResponse[BrandResponse]:
    brand = svc.get_by_id(company_id=company_id, brand_id=brand_id)
    return StandardResponse(
        data=BrandResponse.model_validate(brand),
        message="Brand retrieved successfully",
        meta=_meta(),
    )


@router.patch(
    "/brands/{brand_id}",
    response_model=StandardResponse[BrandResponse],
    summary="Update a brand",
)
def update_brand(
    company_id: UUID = Path(...),
    brand_id: UUID = Path(...),
    body: BrandUpdateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: BrandService = Depends(get_brand_service),
) -> StandardResponse[BrandResponse]:
    brand = svc.update(
        company_id=company_id,
        brand_id=brand_id,
        name=body.name,
        country_of_origin=body.country_of_origin,
        logo_url=body.logo_url,
        website=body.website,
        code=body.code,
    )
    return StandardResponse(
        data=BrandResponse.model_validate(brand),
        message="Brand updated successfully",
        meta=_meta(),
    )


@router.post(
    "/brands/{brand_id}/deactivate",
    response_model=StandardResponse[BrandResponse],
    summary="Deactivate a brand",
)
def deactivate_brand(
    company_id: UUID = Path(...),
    brand_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: BrandService = Depends(get_brand_service),
) -> StandardResponse[BrandResponse]:
    brand = svc.deactivate(company_id=company_id, brand_id=brand_id)
    return StandardResponse(
        data=BrandResponse.model_validate(brand),
        message="Brand deactivated",
        meta=_meta(),
    )


@router.post(
    "/brands/{brand_id}/activate",
    response_model=StandardResponse[BrandResponse],
    summary="Activate a brand",
)
def activate_brand(
    company_id: UUID = Path(...),
    brand_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: BrandService = Depends(get_brand_service),
) -> StandardResponse[BrandResponse]:
    brand = svc.activate(company_id=company_id, brand_id=brand_id)
    return StandardResponse(
        data=BrandResponse.model_validate(brand),
        message="Brand activated",
        meta=_meta(),
    )


@router.delete(
    "/brands/{brand_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a brand",
)
def delete_brand(
    company_id: UUID = Path(...),
    brand_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: BrandService = Depends(get_brand_service),
) -> None:
    svc.delete(company_id=company_id, brand_id=brand_id)


# =============================================================================
# Units of Measure (Phase 1)
# =============================================================================


@router.post(
    "/uom",
    response_model=StandardResponse[UOMResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a unit of measure",
)
def create_uom(
    company_id: UUID = Path(...),
    body: UOMCreateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: UOMService = Depends(get_uom_service),
) -> StandardResponse[UOMResponse]:
    uom = svc.create(
        company_id=company_id,
        code=body.code,
        name=body.name,
        uom_type=body.uom_type,
        symbol=body.symbol,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=UOMResponse.model_validate(uom),
        message="UOM created successfully",
        meta=_meta(),
    )


@router.get(
    "/uom",
    response_model=StandardResponse[PaginatedResponse[UOMResponse]],
    summary="List units of measure",
)
def list_uom(
    company_id: UUID = Path(...),
    page: int = 1,
    page_size: int = 20,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: UOMService = Depends(get_uom_service),
) -> StandardResponse[PaginatedResponse[UOMResponse]]:
    skip = (page - 1) * page_size
    items, total = svc.list(company_id=company_id, skip=skip, limit=page_size)
    return StandardResponse(
        data=PaginatedResponse.from_paginated(
            items=[UOMResponse.model_validate(u) for u in items],
            total=total,
            page=page,
            page_size=page_size,
        ),
        message="UOMs retrieved successfully",
        meta=_meta(),
    )


@router.get(
    "/uom/{uom_id}",
    response_model=StandardResponse[UOMResponse],
    summary="Get a UOM by ID",
)
def get_uom(
    company_id: UUID = Path(...),
    uom_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: UOMService = Depends(get_uom_service),
) -> StandardResponse[UOMResponse]:
    uom = svc.get_by_id(company_id=company_id, uom_id=uom_id)
    return StandardResponse(
        data=UOMResponse.model_validate(uom),
        message="UOM retrieved successfully",
        meta=_meta(),
    )


@router.patch(
    "/uom/{uom_id}",
    response_model=StandardResponse[UOMResponse],
    summary="Update a UOM",
)
def update_uom(
    company_id: UUID = Path(...),
    uom_id: UUID = Path(...),
    body: UOMUpdateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: UOMService = Depends(get_uom_service),
) -> StandardResponse[UOMResponse]:
    uom = svc.update(
        company_id=company_id,
        uom_id=uom_id,
        name=body.name,
        symbol=body.symbol,
        code=body.code,
    )
    return StandardResponse(
        data=UOMResponse.model_validate(uom),
        message="UOM updated successfully",
        meta=_meta(),
    )


@router.post(
    "/uom/{uom_id}/deactivate",
    response_model=StandardResponse[UOMResponse],
    summary="Deactivate a UOM",
)
def deactivate_uom(
    company_id: UUID = Path(...),
    uom_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: UOMService = Depends(get_uom_service),
) -> StandardResponse[UOMResponse]:
    uom = svc.deactivate(company_id=company_id, uom_id=uom_id)
    return StandardResponse(
        data=UOMResponse.model_validate(uom), message="UOM deactivated", meta=_meta()
    )


@router.delete(
    "/uom/{uom_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a UOM",
)
def delete_uom(
    company_id: UUID = Path(...),
    uom_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: UOMService = Depends(get_uom_service),
) -> None:
    svc.delete(company_id=company_id, uom_id=uom_id)


# UOM Conversions


@router.post(
    "/uom-conversions",
    response_model=StandardResponse[UOMConversionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a UOM conversion",
)
def create_uom_conversion(
    company_id: UUID = Path(...),
    body: UOMConversionCreateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: UOMConversionService = Depends(get_uom_conversion_service),
) -> StandardResponse[UOMConversionResponse]:
    conversion = svc.create(
        company_id=company_id,
        source_uom_id=body.source_uom_id,
        target_uom_id=body.target_uom_id,
        conversion_factor=body.conversion_factor,
        notes=body.notes,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=UOMConversionResponse.model_validate(conversion),
        message="UOM conversion created successfully",
        meta=_meta(),
    )


@router.delete(
    "/uom-conversions/{conversion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a UOM conversion",
)
def delete_uom_conversion(
    company_id: UUID = Path(...),
    conversion_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: UOMConversionService = Depends(get_uom_conversion_service),
) -> None:
    svc.delete(company_id=company_id, conversion_id=conversion_id)


# =============================================================================
# Attributes (Phase 1)
# =============================================================================


@router.post(
    "/attributes",
    response_model=StandardResponse[AttributeDefinitionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create an attribute definition",
)
def create_attribute(
    company_id: UUID = Path(...),
    body: AttributeDefinitionCreateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AttributeDefinitionService = Depends(get_attr_definition_service),
) -> StandardResponse[AttributeDefinitionResponse]:
    attr = svc.create(
        company_id=company_id,
        name=body.name,
        data_type=body.data_type,
        options=body.options,
        is_required=body.is_required,
        description=body.description,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=AttributeDefinitionResponse.model_validate(attr),
        message="Attribute created successfully",
        meta=_meta(),
    )


@router.get(
    "/attributes",
    response_model=StandardResponse[list[AttributeDefinitionResponse]],
    summary="List attribute definitions",
)
def list_attributes(
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AttributeDefinitionService = Depends(get_attr_definition_service),
) -> StandardResponse[list[AttributeDefinitionResponse]]:
    attrs = svc.list(company_id=company_id)
    return StandardResponse(
        data=[AttributeDefinitionResponse.model_validate(a) for a in attrs],
        message="Attributes retrieved successfully",
        meta=_meta(),
    )


@router.get(
    "/attributes/{attr_id}",
    response_model=StandardResponse[AttributeDefinitionResponse],
    summary="Get an attribute definition by ID",
)
def get_attribute(
    company_id: UUID = Path(...),
    attr_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AttributeDefinitionService = Depends(get_attr_definition_service),
) -> StandardResponse[AttributeDefinitionResponse]:
    attr = svc.get_by_id(company_id=company_id, attr_id=attr_id)
    return StandardResponse(
        data=AttributeDefinitionResponse.model_validate(attr),
        message="Attribute retrieved successfully",
        meta=_meta(),
    )


@router.patch(
    "/attributes/{attr_id}",
    response_model=StandardResponse[AttributeDefinitionResponse],
    summary="Update an attribute definition",
)
def update_attribute(
    company_id: UUID = Path(...),
    attr_id: UUID = Path(...),
    body: AttributeDefinitionUpdateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AttributeDefinitionService = Depends(get_attr_definition_service),
) -> StandardResponse[AttributeDefinitionResponse]:
    attr = svc.update(
        company_id=company_id,
        attr_id=attr_id,
        description=body.description,
        is_required=body.is_required,
        options=body.options,
    )
    return StandardResponse(
        data=AttributeDefinitionResponse.model_validate(attr),
        message="Attribute updated successfully",
        meta=_meta(),
    )


@router.delete(
    "/attributes/{attr_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an attribute definition",
)
def delete_attribute(
    company_id: UUID = Path(...),
    attr_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AttributeDefinitionService = Depends(get_attr_definition_service),
) -> None:
    svc.delete(company_id=company_id, attr_id=attr_id)


# =============================================================================
# Attribute Sets (Phase 1)
# =============================================================================


@router.post(
    "/attribute-sets",
    response_model=StandardResponse[AttributeSetResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create an attribute set",
)
def create_attribute_set(
    company_id: UUID = Path(...),
    body: AttributeSetCreateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AttributeSetService = Depends(get_attr_set_service),
) -> StandardResponse[AttributeSetResponse]:
    attr_set = svc.create(
        company_id=company_id,
        name=body.name,
        scope=body.scope,
        description=body.description,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=AttributeSetResponse.model_validate(attr_set),
        message="Attribute set created successfully",
        meta=_meta(),
    )


@router.get(
    "/attribute-sets",
    response_model=StandardResponse[list[AttributeSetResponse]],
    summary="List attribute sets",
)
def list_attribute_sets(
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AttributeSetService = Depends(get_attr_set_service),
) -> StandardResponse[list[AttributeSetResponse]]:
    sets = svc.list(company_id=company_id)
    return StandardResponse(
        data=[AttributeSetResponse.model_validate(s) for s in sets],
        message="Attribute sets retrieved successfully",
        meta=_meta(),
    )


@router.get(
    "/attribute-sets/{attr_set_id}",
    response_model=StandardResponse[AttributeSetResponse],
    summary="Get an attribute set by ID",
)
def get_attribute_set(
    company_id: UUID = Path(...),
    attr_set_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AttributeSetService = Depends(get_attr_set_service),
) -> StandardResponse[AttributeSetResponse]:
    attr_set = svc.get_by_id(company_id=company_id, attr_set_id=attr_set_id)
    return StandardResponse(
        data=AttributeSetResponse.model_validate(attr_set),
        message="Attribute set retrieved successfully",
        meta=_meta(),
    )


@router.post(
    "/attribute-sets/{attr_set_id}/attributes",
    response_model=StandardResponse[AttributeSetMembershipResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add attribute to attribute set",
)
def add_attribute_to_set(
    company_id: UUID = Path(...),
    attr_set_id: UUID = Path(...),
    body: AttributeSetMembershipAddRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AttributeSetService = Depends(get_attr_set_service),
) -> StandardResponse[AttributeSetMembershipResponse]:
    membership = svc.add_attribute(
        company_id=company_id,
        attr_set_id=attr_set_id,
        attr_definition_id=body.attribute_definition_id,
        sort_order=body.sort_order,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=AttributeSetMembershipResponse.model_validate(membership),
        message="Attribute added to set",
        meta=_meta(),
    )


@router.delete(
    "/attribute-sets/{attr_set_id}/attributes/{attr_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove attribute from attribute set",
)
def remove_attribute_from_set(
    company_id: UUID = Path(...),
    attr_set_id: UUID = Path(...),
    attr_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AttributeSetService = Depends(get_attr_set_service),
) -> None:
    svc.remove_attribute(
        company_id=company_id,
        attr_set_id=attr_set_id,
        attr_definition_id=attr_id,
    )


@router.delete(
    "/attribute-sets/{attr_set_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an attribute set",
)
def delete_attribute_set(
    company_id: UUID = Path(...),
    attr_set_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AttributeSetService = Depends(get_attr_set_service),
) -> None:
    svc.delete(company_id=company_id, attr_set_id=attr_set_id)


# =============================================================================
# Tags (Phase 1)
# =============================================================================


@router.post(
    "/tags",
    response_model=StandardResponse[TagResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a tag",
)
def create_tag(
    company_id: UUID = Path(...),
    body: TagCreateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: TagService = Depends(get_tag_service),
) -> StandardResponse[TagResponse]:
    tag = svc.create(
        company_id=company_id,
        name=body.name,
        color=body.color,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=TagResponse.model_validate(tag),
        message="Tag created successfully",
        meta=_meta(),
    )


@router.get(
    "/tags",
    response_model=StandardResponse[list[TagResponse]],
    summary="List all tags",
)
def list_tags(
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: TagService = Depends(get_tag_service),
) -> StandardResponse[list[TagResponse]]:
    tags = svc.list(company_id=company_id)
    return StandardResponse(
        data=[TagResponse.model_validate(t) for t in tags],
        message="Tags retrieved successfully",
        meta=_meta(),
    )


@router.get(
    "/tags/{tag_id}",
    response_model=StandardResponse[TagResponse],
    summary="Get a tag by ID",
)
def get_tag(
    company_id: UUID = Path(...),
    tag_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: TagService = Depends(get_tag_service),
) -> StandardResponse[TagResponse]:
    tag = svc.get_by_id(company_id=company_id, tag_id=tag_id)
    return StandardResponse(
        data=TagResponse.model_validate(tag),
        message="Tag retrieved successfully",
        meta=_meta(),
    )


@router.patch(
    "/tags/{tag_id}",
    response_model=StandardResponse[TagResponse],
    summary="Update a tag",
)
def update_tag(
    company_id: UUID = Path(...),
    tag_id: UUID = Path(...),
    body: TagUpdateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: TagService = Depends(get_tag_service),
) -> StandardResponse[TagResponse]:
    tag = svc.update(
        company_id=company_id, tag_id=tag_id, name=body.name, color=body.color
    )
    return StandardResponse(
        data=TagResponse.model_validate(tag),
        message="Tag updated successfully",
        meta=_meta(),
    )


@router.delete(
    "/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a tag",
)
def delete_tag(
    company_id: UUID = Path(...),
    tag_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: TagService = Depends(get_tag_service),
) -> None:
    svc.delete(company_id=company_id, tag_id=tag_id)


# =============================================================================
# Reason Codes (Phase 1)
# =============================================================================


@router.post(
    "/reason-codes",
    response_model=StandardResponse[ReasonCodeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a reason code",
)
def create_reason_code(
    company_id: UUID = Path(...),
    body: ReasonCodeCreateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReasonCodeService = Depends(get_reason_code_service),
) -> StandardResponse[ReasonCodeResponse]:
    rc = svc.create(
        company_id=company_id,
        code=body.code,
        label=body.label,
        applies_to=body.applies_to,
        description=body.description,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=ReasonCodeResponse.model_validate(rc),
        message="Reason code created successfully",
        meta=_meta(),
    )


@router.get(
    "/reason-codes",
    response_model=StandardResponse[PaginatedResponse[ReasonCodeResponse]],
    summary="List reason codes",
)
def list_reason_codes(
    company_id: UUID = Path(...),
    page: int = 1,
    page_size: int = 20,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReasonCodeService = Depends(get_reason_code_service),
) -> StandardResponse[PaginatedResponse[ReasonCodeResponse]]:
    skip = (page - 1) * page_size
    items, total = svc.list(company_id=company_id, skip=skip, limit=page_size)
    return StandardResponse(
        data=PaginatedResponse.from_paginated(
            items=[ReasonCodeResponse.model_validate(r) for r in items],
            total=total,
            page=page,
            page_size=page_size,
        ),
        message="Reason codes retrieved successfully",
        meta=_meta(),
    )


@router.get(
    "/reason-codes/{reason_code_id}",
    response_model=StandardResponse[ReasonCodeResponse],
    summary="Get a reason code by ID",
)
def get_reason_code(
    company_id: UUID = Path(...),
    reason_code_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReasonCodeService = Depends(get_reason_code_service),
) -> StandardResponse[ReasonCodeResponse]:
    rc = svc.get_by_id(company_id=company_id, reason_code_id=reason_code_id)
    return StandardResponse(
        data=ReasonCodeResponse.model_validate(rc),
        message="Reason code retrieved successfully",
        meta=_meta(),
    )


@router.patch(
    "/reason-codes/{reason_code_id}",
    response_model=StandardResponse[ReasonCodeResponse],
    summary="Update a reason code",
)
def update_reason_code(
    company_id: UUID = Path(...),
    reason_code_id: UUID = Path(...),
    body: ReasonCodeUpdateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReasonCodeService = Depends(get_reason_code_service),
) -> StandardResponse[ReasonCodeResponse]:
    rc = svc.update(
        company_id=company_id,
        reason_code_id=reason_code_id,
        label=body.label,
        description=body.description,
    )
    return StandardResponse(
        data=ReasonCodeResponse.model_validate(rc),
        message="Reason code updated successfully",
        meta=_meta(),
    )


@router.post(
    "/reason-codes/{reason_code_id}/deactivate",
    response_model=StandardResponse[ReasonCodeResponse],
    summary="Deactivate a reason code",
)
def deactivate_reason_code(
    company_id: UUID = Path(...),
    reason_code_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReasonCodeService = Depends(get_reason_code_service),
) -> StandardResponse[ReasonCodeResponse]:
    rc = svc.deactivate(company_id=company_id, reason_code_id=reason_code_id)
    return StandardResponse(
        data=ReasonCodeResponse.model_validate(rc),
        message="Reason code deactivated",
        meta=_meta(),
    )


@router.delete(
    "/reason-codes/{reason_code_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a reason code",
)
def delete_reason_code(
    company_id: UUID = Path(...),
    reason_code_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReasonCodeService = Depends(get_reason_code_service),
) -> None:
    svc.delete(company_id=company_id, reason_code_id=reason_code_id)


# =============================================================================
# Custom Fields (Phase 1)
# =============================================================================


@router.post(
    "/custom-fields",
    response_model=StandardResponse[CustomFieldResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom field definition",
)
def create_custom_field(
    company_id: UUID = Path(...),
    body: CustomFieldCreateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: CustomFieldService = Depends(get_custom_field_service),
) -> StandardResponse[CustomFieldResponse]:
    cf = svc.create(
        company_id=company_id,
        entity_type=body.entity_type,
        field_key=body.field_key,
        field_label=body.field_label,
        data_type=body.data_type,
        options=body.options,
        is_required=body.is_required,
        sort_order=body.sort_order,
        placeholder=body.placeholder,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=CustomFieldResponse.model_validate(cf),
        message="Custom field created successfully",
        meta=_meta(),
    )


@router.get(
    "/custom-fields",
    response_model=StandardResponse[list[CustomFieldResponse]],
    summary="List custom fields by entity type",
)
def list_custom_fields(
    company_id: UUID = Path(...),
    entity_type: str = "PRODUCT",
    current_user: CurrentUser = Depends(require_authenticated),
    svc: CustomFieldService = Depends(get_custom_field_service),
) -> StandardResponse[list[CustomFieldResponse]]:
    fields = svc.list_for_entity(company_id=company_id, entity_type=entity_type.upper())
    return StandardResponse(
        data=[CustomFieldResponse.model_validate(f) for f in fields],
        message="Custom fields retrieved successfully",
        meta=_meta(),
    )


@router.get(
    "/custom-fields/{field_id}",
    response_model=StandardResponse[CustomFieldResponse],
    summary="Get a custom field by ID",
)
def get_custom_field(
    company_id: UUID = Path(...),
    field_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: CustomFieldService = Depends(get_custom_field_service),
) -> StandardResponse[CustomFieldResponse]:
    cf = svc.get_by_id(company_id=company_id, field_id=field_id)
    return StandardResponse(
        data=CustomFieldResponse.model_validate(cf),
        message="Custom field retrieved successfully",
        meta=_meta(),
    )


@router.patch(
    "/custom-fields/{field_id}",
    response_model=StandardResponse[CustomFieldResponse],
    summary="Update a custom field",
)
def update_custom_field(
    company_id: UUID = Path(...),
    field_id: UUID = Path(...),
    body: CustomFieldUpdateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: CustomFieldService = Depends(get_custom_field_service),
) -> StandardResponse[CustomFieldResponse]:
    cf = svc.update(
        company_id=company_id,
        field_id=field_id,
        field_label=body.field_label,
        placeholder=body.placeholder,
        is_required=body.is_required,
        sort_order=body.sort_order,
    )
    return StandardResponse(
        data=CustomFieldResponse.model_validate(cf),
        message="Custom field updated successfully",
        meta=_meta(),
    )


@router.delete(
    "/custom-fields/{field_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a custom field",
)
def delete_custom_field(
    company_id: UUID = Path(...),
    field_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: CustomFieldService = Depends(get_custom_field_service),
) -> None:
    svc.delete(company_id=company_id, field_id=field_id)


# =============================================================================
# Phase 2 — Product Master endpoints
# =============================================================================


@router.post(
    "/products",
    response_model=StandardResponse[ProductResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a product",
)
def create_product(
    company_id: UUID = Path(...),
    body: ProductCreateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductService = Depends(get_product_service),
) -> StandardResponse[ProductResponse]:
    product = svc.create_product(
        company_id=company_id,
        product_code=body.product_code,
        name=body.name,
        product_type=body.product_type,
        base_uom_id=body.base_uom_id,
        description=body.description,
        short_description=body.short_description,
        category_id=body.category_id,
        brand_id=body.brand_id,
        hs_code=body.hs_code,
        country_of_origin=body.country_of_origin,
        lead_time_days=body.lead_time_days,
        min_order_qty=body.min_order_qty,
        max_order_qty=body.max_order_qty,
        reorder_point=body.reorder_point,
        weight_kg=body.weight_kg,
        width_cm=body.width_cm,
        height_cm=body.height_cm,
        depth_cm=body.depth_cm,
        is_serialized=body.is_serialized,
        is_batch_tracked=body.is_batch_tracked,
        cost_price=body.cost_price,
        created_by=current_user.id if hasattr(current_user, "id") else None,
    )
    return StandardResponse(
        data=ProductResponse.model_validate(product),
        message="Product created successfully",
        meta=_meta(),
    )


@router.get(
    "/products",
    response_model=StandardResponse[PaginatedResponse[ProductResponse]],
    summary="List / search products",
)
def list_products(
    company_id: UUID = Path(...),
    q: str | None = None,
    status_filter: str | None = None,
    product_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductService = Depends(get_product_service),
) -> StandardResponse[PaginatedResponse[ProductResponse]]:
    items, total = svc.search_products(
        company_id=company_id,
        query=q,
        status=status_filter,
        product_type=product_type,
        page=page,
        page_size=page_size,
    )
    return StandardResponse(
        data=PaginatedResponse.from_paginated(
            items=[ProductResponse.model_validate(p) for p in items],
            total=total,
            page=page,
            page_size=page_size,
        ),
        message="Products retrieved successfully",
        meta=_meta(),
    )


@router.get(
    "/products/{product_id}",
    response_model=StandardResponse[ProductResponse],
    summary="Get a product by ID",
)
def get_product(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductService = Depends(get_product_service),
) -> StandardResponse[ProductResponse]:
    product = svc.get_product(company_id=company_id, product_id=product_id)
    return StandardResponse(
        data=ProductResponse.model_validate(product),
        message="Product retrieved successfully",
        meta=_meta(),
    )


@router.put(
    "/products/{product_id}",
    response_model=StandardResponse[ProductResponse],
    summary="Update a product",
)
def update_product(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    body: ProductUpdateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductService = Depends(get_product_service),
) -> StandardResponse[ProductResponse]:
    product = svc.update_product(
        company_id=company_id,
        product_id=product_id,
        name=body.name,
        description=body.description,
        short_description=body.short_description,
        category_id=body.category_id,
        brand_id=body.brand_id,
        hs_code=body.hs_code,
        country_of_origin=body.country_of_origin,
        lead_time_days=body.lead_time_days,
        min_order_qty=body.min_order_qty,
        max_order_qty=body.max_order_qty,
        reorder_point=body.reorder_point,
        weight_kg=body.weight_kg,
        width_cm=body.width_cm,
        height_cm=body.height_cm,
        depth_cm=body.depth_cm,
        is_serialized=body.is_serialized,
        is_batch_tracked=body.is_batch_tracked,
        cost_price=body.cost_price,
    )
    return StandardResponse(
        data=ProductResponse.model_validate(product),
        message="Product updated successfully",
        meta=_meta(),
    )


@router.patch(
    "/products/{product_id}/status",
    response_model=StandardResponse[ProductResponse],
    summary="Change product lifecycle status",
    description=(
        "Supported actions: **activate** (DRAFT→ACTIVE, INACTIVE→ACTIVE), "
        "**deactivate** (ACTIVE→INACTIVE), **discontinue** (ACTIVE→DISCONTINUED), "
        "**archive** (INACTIVE→ARCHIVED, DISCONTINUED→ARCHIVED)."
    ),
)
def change_product_status(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    body: ProductStatusRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductService = Depends(get_product_service),
) -> StandardResponse[ProductResponse]:
    action_map = {
        "activate": svc.activate_product,
        "deactivate": svc.deactivate_product,
        "discontinue": svc.discontinue_product,
        "archive": svc.archive_product,
    }
    fn = action_map[body.action]
    product = fn(company_id=company_id, product_id=product_id)
    return StandardResponse(
        data=ProductResponse.model_validate(product),
        message=f"Product {body.action}d successfully",
        meta=_meta(),
    )


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a product",
)
def delete_product(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductService = Depends(get_product_service),
) -> None:
    svc.delete_product(company_id=company_id, product_id=product_id)


# ── Product Variants ─────────────────────────────────────────────────────────


@router.post(
    "/products/{product_id}/variants",
    response_model=StandardResponse[VariantResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add a variant to a product",
)
def add_variant(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    body: VariantCreateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductService = Depends(get_product_service),
) -> StandardResponse[VariantResponse]:
    variant = svc.add_variant(
        company_id=company_id,
        product_id=product_id,
        variant_code=body.variant_code,
        attributes=body.attributes,
        is_stock_tracked=body.is_stock_tracked,
        created_by=current_user.id if hasattr(current_user, "id") else None,
    )
    return StandardResponse(
        data=VariantResponse.model_validate(variant),
        message="Variant added successfully",
        meta=_meta(),
    )


@router.get(
    "/products/{product_id}/variants",
    response_model=StandardResponse[list[VariantResponse]],
    summary="List variants for a product",
)
def list_variants(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductService = Depends(get_product_service),
) -> StandardResponse[list[VariantResponse]]:
    variants = svc.get_variants(company_id=company_id, product_id=product_id)
    return StandardResponse(
        data=[VariantResponse.model_validate(v) for v in variants],
        message="Variants retrieved successfully",
        meta=_meta(),
    )


# ── Product Barcodes ─────────────────────────────────────────────────────────


@router.post(
    "/products/{product_id}/barcodes",
    response_model=StandardResponse[BarcodeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add a barcode to a product or variant",
)
def add_barcode(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    body: BarcodeAddRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductService = Depends(get_product_service),
) -> StandardResponse[BarcodeResponse]:
    barcode = svc.add_barcode(
        company_id=company_id,
        product_id=product_id,
        barcode_value=body.barcode_value,
        barcode_type=body.barcode_type,
        is_primary=body.is_primary,
        variant_id=body.variant_id,
        created_by=current_user.id if hasattr(current_user, "id") else None,
    )
    return StandardResponse(
        data=BarcodeResponse.model_validate(barcode),
        message="Barcode added successfully",
        meta=_meta(),
    )


@router.get(
    "/products/{product_id}/barcodes",
    response_model=StandardResponse[list[BarcodeResponse]],
    summary="List barcodes for a product",
)
def list_barcodes(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductService = Depends(get_product_service),
) -> StandardResponse[list[BarcodeResponse]]:
    barcodes = svc.list_barcodes(company_id=company_id, product_id=product_id)
    return StandardResponse(
        data=[BarcodeResponse.model_validate(b) for b in barcodes],
        message="Barcodes retrieved successfully",
        meta=_meta(),
    )


@router.delete(
    "/products/{product_id}/barcodes/{barcode_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a barcode from a product",
)
def delete_barcode(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    barcode_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductService = Depends(get_product_service),
) -> None:
    svc.delete_barcode(
        company_id=company_id,
        product_id=product_id,
        barcode_id=barcode_id,
    )


# =============================================================================
# Product Tags (Phase 3)
# =============================================================================


@router.post(
    "/products/{product_id}/tags",
    response_model=StandardResponse[ProductTagResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Assign a tag to a product",
)
def assign_tag(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    body: TagAssignRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductEnrichmentService = Depends(get_product_enrichment_service),
) -> StandardResponse[ProductTagResponse]:
    pt = svc.assign_tag(
        company_id=company_id,
        product_id=product_id,
        tag_id=body.tag_id,
    )
    return StandardResponse(
        data=ProductTagResponse.model_validate(pt),
        message="Tag assigned successfully",
        meta=_meta(),
    )


@router.get(
    "/products/{product_id}/tags",
    response_model=StandardResponse[list[ProductTagResponse]],
    summary="List tags assigned to a product",
)
def list_product_tags(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductEnrichmentService = Depends(get_product_enrichment_service),
) -> StandardResponse[list[ProductTagResponse]]:
    tags = svc.list_tags(company_id=company_id, product_id=product_id)
    return StandardResponse(
        data=[ProductTagResponse.model_validate(t) for t in tags],
        message="Tags retrieved successfully",
        meta=_meta(),
    )


@router.delete(
    "/products/{product_id}/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a tag from a product",
)
def remove_tag(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    tag_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductEnrichmentService = Depends(get_product_enrichment_service),
) -> None:
    svc.remove_tag(company_id=company_id, product_id=product_id, tag_id=tag_id)


# =============================================================================
# Custom Field Values (Phase 3)
# =============================================================================


@router.post(
    "/products/{product_id}/custom-fields",
    response_model=StandardResponse[CustomFieldValueResponse],
    status_code=status.HTTP_200_OK,
    summary="Set (upsert) a custom field value for a product",
)
def set_custom_field_value(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    body: CustomFieldValueSetRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductEnrichmentService = Depends(get_product_enrichment_service),
) -> StandardResponse[CustomFieldValueResponse]:
    cfv = svc.set_custom_field_value(
        company_id=company_id,
        product_id=product_id,
        field_key=body.field_key,
        value_text=body.value_text,
        value_number=body.value_number,
        value_bool=body.value_bool,
        value_json=body.value_json,
    )
    return StandardResponse(
        data=CustomFieldValueResponse.model_validate(cfv),
        message="Custom field value set successfully",
        meta=_meta(),
    )


@router.get(
    "/products/{product_id}/custom-fields",
    response_model=StandardResponse[list[CustomFieldValueResponse]],
    summary="List custom field values for a product",
)
def list_custom_field_values(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductEnrichmentService = Depends(get_product_enrichment_service),
) -> StandardResponse[list[CustomFieldValueResponse]]:
    values = svc.list_custom_field_values(company_id=company_id, product_id=product_id)
    return StandardResponse(
        data=[CustomFieldValueResponse.model_validate(v) for v in values],
        message="Custom field values retrieved successfully",
        meta=_meta(),
    )


@router.delete(
    "/products/{product_id}/custom-fields/{field_key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a custom field value from a product",
)
def delete_custom_field_value(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    field_key: str = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductEnrichmentService = Depends(get_product_enrichment_service),
) -> None:
    svc.delete_custom_field_value(
        company_id=company_id,
        product_id=product_id,
        field_key=field_key,
    )


# =============================================================================
# Internal Notes (Phase 3)
# =============================================================================


@router.post(
    "/products/{product_id}/notes",
    response_model=StandardResponse[InternalNoteResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add an internal note to a product (append-only)",
)
def add_note(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    body: NoteAddRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductEnrichmentService = Depends(get_product_enrichment_service),
) -> StandardResponse[InternalNoteResponse]:
    note = svc.add_note(
        company_id=company_id,
        product_id=product_id,
        note_text=body.note_text,
        author_id=current_user.user_id,
    )
    return StandardResponse(
        data=InternalNoteResponse.model_validate(note),
        message="Note added successfully",
        meta=_meta(),
    )


@router.get(
    "/products/{product_id}/notes",
    response_model=StandardResponse[list[InternalNoteResponse]],
    summary="List internal notes for a product",
)
def list_notes(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductEnrichmentService = Depends(get_product_enrichment_service),
) -> StandardResponse[list[InternalNoteResponse]]:
    notes = svc.list_notes(company_id=company_id, product_id=product_id)
    return StandardResponse(
        data=[InternalNoteResponse.model_validate(n) for n in notes],
        message="Notes retrieved successfully",
        meta=_meta(),
    )


# =============================================================================
# Product Images (Phase 3)
# =============================================================================


@router.post(
    "/products/{product_id}/images",
    response_model=StandardResponse[ProductImageResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload an image for a product (multipart/form-data)",
)
async def upload_image(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    file: UploadFile = File(...),
    is_primary: bool = False,
    sort_order: int = 0,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductEnrichmentService = Depends(get_product_enrichment_service),
) -> StandardResponse[ProductImageResponse]:
    content = await file.read()
    filename = file.filename or "upload"

    # Build a deterministic S3 key (storage is mocked in dev/test)
    import hashlib

    content_hash = hashlib.md5(content).hexdigest()[:12]
    s3_key = f"products/{company_id}/{product_id}/{content_hash}-{filename}"
    url = f"/static/uploads/{s3_key}"  # placeholder URL

    image = svc.add_image(
        company_id=company_id,
        product_id=product_id,
        s3_key=s3_key,
        url=url,
        is_primary=is_primary,
        sort_order=sort_order,
    )
    return StandardResponse(
        data=ProductImageResponse.model_validate(image),
        message="Image uploaded successfully",
        meta=_meta(),
    )


@router.get(
    "/products/{product_id}/images",
    response_model=StandardResponse[list[ProductImageResponse]],
    summary="List images for a product",
)
def list_images(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductEnrichmentService = Depends(get_product_enrichment_service),
) -> StandardResponse[list[ProductImageResponse]]:
    images = svc.list_images(company_id=company_id, product_id=product_id)
    return StandardResponse(
        data=[ProductImageResponse.model_validate(i) for i in images],
        message="Images retrieved successfully",
        meta=_meta(),
    )


@router.delete(
    "/products/{product_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a product image",
)
def delete_image(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    image_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductEnrichmentService = Depends(get_product_enrichment_service),
) -> None:
    svc.delete_image(
        company_id=company_id,
        product_id=product_id,
        image_id=image_id,
    )


@router.patch(
    "/products/{product_id}/images/{image_id}/primary",
    response_model=StandardResponse[ProductImageResponse],
    summary="Set an image as the primary image for a product",
)
def set_primary_image(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    image_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ProductEnrichmentService = Depends(get_product_enrichment_service),
) -> StandardResponse[ProductImageResponse]:
    image = svc.set_primary_image(
        company_id=company_id,
        product_id=product_id,
        image_id=image_id,
    )
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image not found"
        )
    return StandardResponse(
        data=ProductImageResponse.model_validate(image),
        message="Primary image updated",
        meta=_meta(),
    )


# =============================================================================
# Bulk Import / Export (Phase 3)
# =============================================================================


@router.post(
    "/products/import",
    response_model=StandardResponse[ImportJobResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Bulk import products from CSV file",
)
async def import_products(
    company_id: UUID = Path(...),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: BulkImportService = Depends(get_bulk_import_service),
) -> StandardResponse[ImportJobResponse]:
    content = await file.read()
    filename = file.filename or "import.csv"
    job = svc.import_csv(
        company_id=company_id,
        file_name=filename,
        content=content,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=ImportJobResponse.model_validate(job),
        message="Import job completed",
        meta=_meta(),
    )


@router.get(
    "/products/import/{job_id}",
    response_model=StandardResponse[ImportJobResponse],
    summary="Get bulk import job status",
)
def get_import_job(
    company_id: UUID = Path(...),
    job_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    job_repo: ImportJobRepository = Depends(get_import_job_repo),
) -> StandardResponse[ImportJobResponse]:
    job = job_repo.get(company_id=company_id, job_id=job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found"
        )
    return StandardResponse(
        data=ImportJobResponse.model_validate(job),
        message="Import job retrieved",
        meta=_meta(),
    )


@router.post(
    "/products/export",
    summary="Export product catalogue as CSV",
    response_class=Response,
)
def export_products(
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: BulkImportService = Depends(get_bulk_import_service),
) -> Response:
    csv_bytes = svc.export_csv(company_id=company_id)
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products_export.csv"},
    )


# =============================================================================
# Phase 4: Warehouse Management endpoints
# =============================================================================


@router.post(
    "/warehouses",
    response_model=StandardResponse[WarehouseResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a warehouse",
)
def create_warehouse(
    payload: WarehouseCreateRequest,
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: WarehouseService = Depends(get_warehouse_service),
) -> StandardResponse[WarehouseResponse]:
    try:
        wh = svc.create_warehouse(
            company_id=company_id,
            code=payload.code,
            name=payload.name,
            warehouse_type=payload.warehouse_type,
            address_line1=payload.address_line1,
            address_line2=payload.address_line2,
            city=payload.city,
            state_province=payload.state_province,
            postal_code=payload.postal_code,
            country_code=payload.country_code,
            phone=payload.phone,
            notes=payload.notes,
            actor_id=current_user.user_id,
        )
    except Exception as exc:
        from modules.inventory.exceptions import (
            WarehouseCodeConflictError,
        )  # noqa: N813, I001

        if isinstance(exc, WarehouseCodeConflictError):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        raise
    return StandardResponse(
        data=WarehouseResponse.model_validate(wh),
        message="Warehouse created",
        meta=_meta(),
    )


@router.get(
    "/warehouses",
    response_model=StandardResponse[list[WarehouseResponse]],
    summary="List warehouses",
)
def list_warehouses(
    company_id: UUID = Path(...),
    wh_status: str | None = None,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: WarehouseService = Depends(get_warehouse_service),
) -> StandardResponse[list[WarehouseResponse]]:
    warehouses = svc.list_warehouses(company_id=company_id, status=wh_status)
    return StandardResponse(
        data=[WarehouseResponse.model_validate(w) for w in warehouses],
        message="Warehouses retrieved",
        meta=_meta(),
    )


@router.get(
    "/warehouses/{warehouse_id}",
    response_model=StandardResponse[WarehouseResponse],
    summary="Get a warehouse by ID",
)
def get_warehouse(
    company_id: UUID = Path(...),
    warehouse_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: WarehouseService = Depends(get_warehouse_service),
) -> StandardResponse[WarehouseResponse]:
    from modules.inventory.exceptions import (
        WarehouseNotFoundError,
    )  # noqa: N813, I001

    try:
        wh = svc.get_warehouse(company_id=company_id, warehouse_id=warehouse_id)
    except WarehouseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return StandardResponse(
        data=WarehouseResponse.model_validate(wh),
        message="Warehouse retrieved",
        meta=_meta(),
    )


@router.patch(
    "/warehouses/{warehouse_id}",
    response_model=StandardResponse[WarehouseResponse],
    summary="Update a warehouse",
)
def update_warehouse(
    payload: WarehouseUpdateRequest,
    company_id: UUID = Path(...),
    warehouse_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: WarehouseService = Depends(get_warehouse_service),
) -> StandardResponse[WarehouseResponse]:
    from modules.inventory.exceptions import (
        WarehouseNotFoundError,
    )  # noqa: N813, I001

    try:
        wh = svc.update_warehouse(
            company_id=company_id,
            warehouse_id=warehouse_id,
            name=payload.name,
            warehouse_type=payload.warehouse_type,
            address_line1=payload.address_line1,
            address_line2=payload.address_line2,
            city=payload.city,
            state_province=payload.state_province,
            postal_code=payload.postal_code,
            country_code=payload.country_code,
            phone=payload.phone,
            notes=payload.notes,
            actor_id=current_user.user_id,
        )
    except WarehouseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return StandardResponse(
        data=WarehouseResponse.model_validate(wh),
        message="Warehouse updated",
        meta=_meta(),
    )


@router.post(
    "/warehouses/{warehouse_id}/deactivate",
    response_model=StandardResponse[WarehouseResponse],
    summary="Deactivate a warehouse (ACTIVE → INACTIVE)",
)
def deactivate_warehouse(
    company_id: UUID = Path(...),
    warehouse_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: WarehouseService = Depends(get_warehouse_service),
) -> StandardResponse[WarehouseResponse]:
    from modules.inventory.exceptions import (
        WarehouseNotFoundError,
    )  # noqa: N813, I001

    try:
        wh = svc.transition_status(
            company_id=company_id,
            warehouse_id=warehouse_id,
            target_status="INACTIVE",
            actor_id=current_user.user_id,
        )
    except WarehouseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidWarehouseStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=WarehouseResponse.model_validate(wh),
        message="Warehouse deactivated",
        meta=_meta(),
    )


@router.post(
    "/warehouses/{warehouse_id}/activate",
    response_model=StandardResponse[WarehouseResponse],
    summary="Activate/reactivate a warehouse (INACTIVE → ACTIVE)",
)
def activate_warehouse(
    company_id: UUID = Path(...),
    warehouse_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: WarehouseService = Depends(get_warehouse_service),
) -> StandardResponse[WarehouseResponse]:
    from modules.inventory.exceptions import (
        WarehouseNotFoundError,
    )  # noqa: N813, I001

    try:
        wh = svc.transition_status(
            company_id=company_id,
            warehouse_id=warehouse_id,
            target_status="ACTIVE",
            actor_id=current_user.user_id,
        )
    except WarehouseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidWarehouseStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=WarehouseResponse.model_validate(wh),
        message="Warehouse activated",
        meta=_meta(),
    )


@router.post(
    "/warehouses/{warehouse_id}/archive",
    response_model=StandardResponse[WarehouseResponse],
    summary="Archive a warehouse (INACTIVE → ARCHIVED)",
)
def archive_warehouse(
    company_id: UUID = Path(...),
    warehouse_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: WarehouseService = Depends(get_warehouse_service),
) -> StandardResponse[WarehouseResponse]:
    from modules.inventory.exceptions import (
        WarehouseNotFoundError,
    )  # noqa: N813, I001

    try:
        wh = svc.transition_status(
            company_id=company_id,
            warehouse_id=warehouse_id,
            target_status="ARCHIVED",
            actor_id=current_user.user_id,
        )
    except WarehouseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidWarehouseStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except WarehouseHasStockError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=WarehouseResponse.model_validate(wh),
        message="Warehouse archived",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Warehouse Locations
# ---------------------------------------------------------------------------


@router.get(
    "/warehouses/{warehouse_id}/locations",
    response_model=StandardResponse[list[LocationResponse]],
    summary="List warehouse locations",
)
def list_warehouse_locations(
    company_id: UUID = Path(...),
    warehouse_id: UUID = Path(...),
    active_only: bool = False,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: WarehouseService = Depends(get_warehouse_service),
) -> StandardResponse[list[LocationResponse]]:
    from modules.inventory.exceptions import (
        WarehouseNotFoundError,
    )  # noqa: N813, I001

    try:
        locations = svc.list_locations(
            company_id=company_id,
            warehouse_id=warehouse_id,
            active_only=active_only,
        )
    except WarehouseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return StandardResponse(
        data=[LocationResponse.model_validate(loc) for loc in locations],
        message="Locations retrieved",
        meta=_meta(),
    )


@router.post(
    "/warehouses/{warehouse_id}/locations",
    response_model=StandardResponse[LocationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add a location to a warehouse",
)
def add_warehouse_location(
    payload: LocationCreateRequest,
    company_id: UUID = Path(...),
    warehouse_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: WarehouseService = Depends(get_warehouse_service),
) -> StandardResponse[LocationResponse]:
    from modules.inventory.exceptions import (
        WarehouseNotFoundError,
    )  # noqa: N813, I001

    try:
        loc = svc.add_location(
            company_id=company_id,
            warehouse_id=warehouse_id,
            location_code=payload.location_code,
            aisle=payload.aisle,
            zone=payload.zone,
            shelf=payload.shelf,
            is_active=payload.is_active,
            actor_id=current_user.user_id,
        )
    except WarehouseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except LocationCodeConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=LocationResponse.model_validate(loc),
        message="Location added",
        meta=_meta(),
    )


@router.patch(
    "/warehouses/{warehouse_id}/locations/{location_id}",
    response_model=StandardResponse[LocationResponse],
    summary="Update a warehouse location",
)
def update_warehouse_location(
    payload: LocationUpdateRequest,
    company_id: UUID = Path(...),
    warehouse_id: UUID = Path(...),
    location_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: WarehouseService = Depends(get_warehouse_service),
) -> StandardResponse[LocationResponse]:
    from modules.inventory.exceptions import (
        WarehouseNotFoundError,
    )  # noqa: N813, I001

    try:
        loc = svc.update_location(
            company_id=company_id,
            warehouse_id=warehouse_id,
            location_id=location_id,
            aisle=payload.aisle,
            zone=payload.zone,
            shelf=payload.shelf,
            is_active=payload.is_active,
            actor_id=current_user.user_id,
        )
    except WarehouseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except LocationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return StandardResponse(
        data=LocationResponse.model_validate(loc),
        message="Location updated",
        meta=_meta(),
    )


# =============================================================================
# Phase 5 — Stock Ledger endpoints
# =============================================================================


@router.post(
    "/stock/opening",
    response_model=StandardResponse[StockPositionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record opening stock",
)
def record_opening_stock(
    payload: OpeningStockRequest,
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: StockLedgerService = Depends(get_stock_ledger_service),
) -> StandardResponse[StockPositionResponse]:
    from modules.inventory.exceptions import (
        InvalidStockQuantityError,  # noqa: N813, I001
        WarehouseNotFoundError,  # noqa: N813, I001
    )

    try:
        _, pos = svc.record_opening_stock(
            company_id=company_id,
            product_id=payload.product_id,
            warehouse_id=payload.warehouse_id,
            quantity=payload.quantity,
            unit_cost=payload.unit_cost,
            currency_code=payload.currency_code,
            variant_id=payload.variant_id,
            notes=payload.notes,
            performed_at=payload.performed_at,
            actor_id=current_user.user_id,
        )
    except WarehouseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidStockQuantityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return StandardResponse(
        data=StockPositionResponse.model_validate(pos),
        message="Opening stock recorded",
        meta=_meta(),
    )


@router.post(
    "/stock/adjustments",
    response_model=StandardResponse[StockPositionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a stock adjustment",
)
def record_adjustment(
    payload: AdjustmentRequest,
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: StockLedgerService = Depends(get_stock_ledger_service),
) -> StandardResponse[StockPositionResponse]:
    from modules.inventory.exceptions import (
        InsufficientStockError,  # noqa: N813, I001
        InvalidStockQuantityError,  # noqa: N813, I001
        WarehouseNotFoundError,  # noqa: N813, I001
    )

    try:
        _, pos = svc.record_adjustment(
            company_id=company_id,
            product_id=payload.product_id,
            warehouse_id=payload.warehouse_id,
            movement_type=payload.movement_type,
            quantity=payload.quantity,
            unit_cost=payload.unit_cost,
            currency_code=payload.currency_code,
            variant_id=payload.variant_id,
            reference_type=payload.reference_type,
            reference_id=payload.reference_id,
            notes=payload.notes,
            performed_at=payload.performed_at,
            actor_id=current_user.user_id,
        )
    except WarehouseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidStockQuantityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except InsufficientStockError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return StandardResponse(
        data=StockPositionResponse.model_validate(pos),
        message="Adjustment recorded",
        meta=_meta(),
    )


@router.get(
    "/stock/positions",
    response_model=StandardResponse[list[StockPositionResponse]],
    summary="List all stock positions for a company",
)
def list_stock_positions(
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: StockLedgerService = Depends(get_stock_ledger_service),
) -> StandardResponse[list[StockPositionResponse]]:
    positions = svc.list_positions_for_company(company_id=company_id)
    return StandardResponse(
        data=[StockPositionResponse.model_validate(p) for p in positions],
        message="Stock positions retrieved",
        meta=_meta(),
    )


@router.get(
    "/stock/positions/warehouse/{warehouse_id}",
    response_model=StandardResponse[list[StockPositionResponse]],
    summary="List stock positions for a warehouse",
)
def list_stock_positions_by_warehouse(
    company_id: UUID = Path(...),
    warehouse_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: StockLedgerService = Depends(get_stock_ledger_service),
) -> StandardResponse[list[StockPositionResponse]]:
    positions = svc.list_positions_for_warehouse(
        company_id=company_id, warehouse_id=warehouse_id
    )
    return StandardResponse(
        data=[StockPositionResponse.model_validate(p) for p in positions],
        message="Stock positions retrieved",
        meta=_meta(),
    )


@router.get(
    "/stock/positions/product/{product_id}",
    response_model=StandardResponse[list[StockPositionResponse]],
    summary="List stock positions for a product across warehouses",
)
def list_stock_positions_by_product(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: StockLedgerService = Depends(get_stock_ledger_service),
) -> StandardResponse[list[StockPositionResponse]]:
    positions = svc.list_positions_for_product(
        company_id=company_id, product_id=product_id
    )
    return StandardResponse(
        data=[StockPositionResponse.model_validate(p) for p in positions],
        message="Stock positions retrieved",
        meta=_meta(),
    )


@router.get(
    "/stock/movements",
    response_model=StandardResponse[list[StockMovementResponse]],
    summary="List stock movements (ledger)",
)
def list_stock_movements(
    company_id: UUID = Path(...),
    product_id: UUID | None = None,
    warehouse_id: UUID | None = None,
    movement_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: StockLedgerService = Depends(get_stock_ledger_service),
) -> StandardResponse[list[StockMovementResponse]]:
    movements = svc.list_movements(
        company_id=company_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        limit=limit,
        offset=offset,
    )
    return StandardResponse(
        data=[StockMovementResponse.model_validate(m) for m in movements],
        message="Stock movements retrieved",
        meta=_meta(),
    )


@router.post(
    "/stock/snapshots",
    response_model=StandardResponse[SnapshotResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create an inventory snapshot",
)
def create_snapshot(
    payload: SnapshotCreateRequest,
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: StockLedgerService = Depends(get_stock_ledger_service),
) -> StandardResponse[SnapshotResponse]:
    snap = svc.create_snapshot(
        company_id=company_id,
        snapshot_name=payload.snapshot_name,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=SnapshotResponse.model_validate(snap),
        message="Snapshot created",
        meta=_meta(),
    )


@router.get(
    "/stock/snapshots",
    response_model=StandardResponse[list[SnapshotResponse]],
    summary="List inventory snapshots",
)
def list_snapshots(
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: StockLedgerService = Depends(get_stock_ledger_service),
) -> StandardResponse[list[SnapshotResponse]]:
    snaps = svc.list_snapshots(company_id=company_id)
    return StandardResponse(
        data=[SnapshotResponse.model_validate(s) for s in snaps],
        message="Snapshots retrieved",
        meta=_meta(),
    )


@router.get(
    "/stock/snapshots/{snapshot_id}/lines",
    response_model=StandardResponse[list[SnapshotLineResponse]],
    summary="List lines for a snapshot",
)
def list_snapshot_lines(
    company_id: UUID = Path(...),
    snapshot_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: StockLedgerService = Depends(get_stock_ledger_service),
) -> StandardResponse[list[SnapshotLineResponse]]:
    lines = svc.get_snapshot_lines(company_id=company_id, snapshot_id=snapshot_id)
    return StandardResponse(
        data=[SnapshotLineResponse.model_validate(ln) for ln in lines],
        message="Snapshot lines retrieved",
        meta=_meta(),
    )


# =============================================================================
# Inventory Adjustments (Phase 6)
# =============================================================================


@router.post(
    "/adjustments",
    response_model=StandardResponse[AdjustmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create an inventory adjustment (DRAFT)",
)
def create_adjustment(
    company_id: UUID = Path(...),
    body: AdjustmentCreateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AdjustmentService = Depends(get_adjustment_service),
) -> StandardResponse[AdjustmentResponse]:
    from decimal import Decimal

    adj = svc.create_adjustment(
        company_id=company_id,
        product_id=body.product_id,
        warehouse_id=body.warehouse_id,
        movement_type=body.movement_type,
        quantity=Decimal(body.quantity),
        unit_cost=Decimal(body.unit_cost) if body.unit_cost else None,
        currency_code=body.currency_code,
        variant_id=body.variant_id,
        reason_code_id=body.reason_code_id,
        notes=body.notes,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=AdjustmentResponse.model_validate(adj),
        message="Adjustment created successfully",
        meta=_meta(),
    )


@router.get(
    "/adjustments",
    response_model=StandardResponse[list[AdjustmentResponse]],
    summary="List inventory adjustments",
)
def list_adjustments(
    company_id: UUID = Path(...),
    status_filter: str | None = None,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AdjustmentService = Depends(get_adjustment_service),
) -> StandardResponse[list[AdjustmentResponse]]:
    adjs = svc.list_adjustments(company_id=company_id, status=status_filter)
    return StandardResponse(
        data=[AdjustmentResponse.model_validate(a) for a in adjs],
        message="Adjustments retrieved",
        meta=_meta(),
    )


@router.get(
    "/adjustments/{adjustment_id}",
    response_model=StandardResponse[AdjustmentResponse],
    summary="Get an inventory adjustment by ID",
)
def get_adjustment(
    company_id: UUID = Path(...),
    adjustment_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AdjustmentService = Depends(get_adjustment_service),
) -> StandardResponse[AdjustmentResponse]:
    adj = svc.get_adjustment(company_id=company_id, adjustment_id=adjustment_id)
    return StandardResponse(
        data=AdjustmentResponse.model_validate(adj),
        message="Adjustment retrieved",
        meta=_meta(),
    )


@router.post(
    "/adjustments/{adjustment_id}/submit",
    response_model=StandardResponse[AdjustmentResponse],
    summary="Submit an adjustment for approval (or auto-approve if flag disabled)",
)
def submit_adjustment(
    company_id: UUID = Path(...),
    adjustment_id: UUID = Path(...),
    body: AdjustmentSubmitRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AdjustmentService = Depends(get_adjustment_service),
) -> StandardResponse[AdjustmentResponse]:
    adj = svc.submit_adjustment(
        company_id=company_id,
        adjustment_id=adjustment_id,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=AdjustmentResponse.model_validate(adj),
        message="Adjustment submitted",
        meta=_meta(),
    )


@router.post(
    "/adjustments/{adjustment_id}/approve",
    response_model=StandardResponse[AdjustmentResponse],
    summary="Approve a pending adjustment (approver must differ from submitter)",
)
def approve_adjustment(
    company_id: UUID = Path(...),
    adjustment_id: UUID = Path(...),
    body: AdjustmentApproveRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AdjustmentService = Depends(get_adjustment_service),
) -> StandardResponse[AdjustmentResponse]:
    adj = svc.approve_adjustment(
        company_id=company_id,
        adjustment_id=adjustment_id,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=AdjustmentResponse.model_validate(adj),
        message="Adjustment approved",
        meta=_meta(),
    )


@router.post(
    "/adjustments/{adjustment_id}/reject",
    response_model=StandardResponse[AdjustmentResponse],
    summary="Reject a pending adjustment",
)
def reject_adjustment(
    company_id: UUID = Path(...),
    adjustment_id: UUID = Path(...),
    body: AdjustmentRejectRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: AdjustmentService = Depends(get_adjustment_service),
) -> StandardResponse[AdjustmentResponse]:
    adj = svc.reject_adjustment(
        company_id=company_id,
        adjustment_id=adjustment_id,
        rejection_reason=body.rejection_reason,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=AdjustmentResponse.model_validate(adj),
        message="Adjustment rejected",
        meta=_meta(),
    )


# =============================================================================
# Phase 7 — Stock Transfers (T202)
# =============================================================================


@router.post(
    "/stock-transfers",
    response_model=StandardResponse[TransferResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft stock transfer",
)
def create_stock_transfer(
    company_id: UUID = Path(...),
    body: TransferCreateRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: TransferService = Depends(get_transfer_service),
) -> StandardResponse[TransferResponse]:
    transfer = svc.create_transfer(
        company_id=company_id,
        source_warehouse_id=body.source_warehouse_id,
        destination_warehouse_id=body.destination_warehouse_id,
        lines=[line.model_dump() for line in body.lines],
        notes=body.notes,
        reference_no=body.reference_no,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=TransferResponse.model_validate(transfer),
        message="Transfer created",
        meta=_meta(),
    )


@router.get(
    "/stock-transfers",
    response_model=StandardResponse[list[TransferResponse]],
    summary="List stock transfers",
)
def list_stock_transfers(
    company_id: UUID = Path(...),
    status_filter: str | None = None,
    source_warehouse_id: UUID | None = None,
    destination_warehouse_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: TransferService = Depends(get_transfer_service),
) -> StandardResponse[list[TransferResponse]]:
    transfers = svc.list_transfers(
        company_id=company_id,
        status=status_filter,
        source_warehouse_id=source_warehouse_id,
        destination_warehouse_id=destination_warehouse_id,
        limit=limit,
        offset=offset,
    )
    return StandardResponse(
        data=[TransferResponse.model_validate(t) for t in transfers],
        message="OK",
        meta=_meta(),
    )


@router.get(
    "/stock-transfers/{transfer_id}",
    response_model=StandardResponse[TransferResponse],
    summary="Get stock transfer by ID",
)
def get_stock_transfer(
    company_id: UUID = Path(...),
    transfer_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: TransferService = Depends(get_transfer_service),
) -> StandardResponse[TransferResponse]:
    transfer = svc.get_transfer(company_id=company_id, transfer_id=transfer_id)
    return StandardResponse(
        data=TransferResponse.model_validate(transfer),
        message="OK",
        meta=_meta(),
    )


@router.post(
    "/stock-transfers/{transfer_id}/dispatch",
    response_model=StandardResponse[TransferResponse],
    summary="Dispatch a transfer (DRAFT → IN_TRANSIT)",
)
def dispatch_stock_transfer(
    company_id: UUID = Path(...),
    transfer_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: TransferService = Depends(get_transfer_service),
) -> StandardResponse[TransferResponse]:
    transfer = svc.dispatch_transfer(
        company_id=company_id,
        transfer_id=transfer_id,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=TransferResponse.model_validate(transfer),
        message="Transfer dispatched",
        meta=_meta(),
    )


@router.post(
    "/stock-transfers/{transfer_id}/receive",
    response_model=StandardResponse[TransferResponse],
    summary="Receive a transfer (IN_TRANSIT → COMPLETED)",
)
def receive_stock_transfer(
    company_id: UUID = Path(...),
    transfer_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: TransferService = Depends(get_transfer_service),
) -> StandardResponse[TransferResponse]:
    transfer = svc.receive_transfer(
        company_id=company_id,
        transfer_id=transfer_id,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=TransferResponse.model_validate(transfer),
        message="Transfer received",
        meta=_meta(),
    )


@router.post(
    "/stock-transfers/{transfer_id}/cancel",
    response_model=StandardResponse[TransferResponse],
    summary="Cancel a transfer (DRAFT or IN_TRANSIT → CANCELLED)",
)
def cancel_stock_transfer(
    company_id: UUID = Path(...),
    transfer_id: UUID = Path(...),
    body: TransferCancelRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: TransferService = Depends(get_transfer_service),
) -> StandardResponse[TransferResponse]:
    transfer = svc.cancel_transfer(
        company_id=company_id,
        transfer_id=transfer_id,
        cancelled_reason=body.cancelled_reason,
        actor_id=current_user.user_id,
    )
    return StandardResponse(
        data=TransferResponse.model_validate(transfer),
        message="Transfer cancelled",
        meta=_meta(),
    )


# =============================================================================
# Phase 7 — Stock Reservation (T203)
# =============================================================================


@router.post(
    "/stock/reserve",
    response_model=StandardResponse[StockReservationResponse],
    summary="Reserve stock (for downstream module consumption)",
)
def reserve_stock(
    company_id: UUID = Path(...),
    body: StockReserveRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: TransferService = Depends(get_transfer_service),
) -> StandardResponse[StockReservationResponse]:
    from decimal import Decimal

    svc.reserve_stock(
        company_id=company_id,
        product_id=body.product_id,
        warehouse_id=body.warehouse_id,
        quantity=Decimal(body.quantity),
        variant_id=body.variant_id,
        reference_type=body.reference_type,
        reference_id=body.reference_id,
    )
    # Fetch updated position for response
    pos = svc._pos_repo.get_by_product_warehouse(
        company_id=company_id,
        product_id=body.product_id,
        warehouse_id=body.warehouse_id,
        variant_id=body.variant_id,
    )
    on_hand = Decimal(str(pos.qty_on_hand)) if pos else Decimal("0")
    reserved = Decimal(str(pos.qty_reserved)) if pos else Decimal("0")
    damaged = Decimal(str(pos.qty_damaged)) if pos else Decimal("0")
    available = on_hand - reserved - damaged
    return StandardResponse(
        data=StockReservationResponse(
            product_id=str(body.product_id),
            warehouse_id=str(body.warehouse_id),
            variant_id=str(body.variant_id) if body.variant_id else None,
            qty_reserved=str(reserved),
            qty_on_hand=str(on_hand),
            available_quantity=str(available),
            message="Stock reserved successfully",
        ),
        message="Stock reserved",
        meta=_meta(),
    )


@router.post(
    "/stock/release",
    response_model=StandardResponse[StockReservationResponse],
    summary="Release a stock reservation",
)
def release_stock(
    company_id: UUID = Path(...),
    body: StockReleaseRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: TransferService = Depends(get_transfer_service),
) -> StandardResponse[StockReservationResponse]:
    from decimal import Decimal

    svc.release_stock(
        company_id=company_id,
        product_id=body.product_id,
        warehouse_id=body.warehouse_id,
        quantity=Decimal(body.quantity),
        variant_id=body.variant_id,
    )
    pos = svc._pos_repo.get_by_product_warehouse(
        company_id=company_id,
        product_id=body.product_id,
        warehouse_id=body.warehouse_id,
        variant_id=body.variant_id,
    )
    on_hand = Decimal(str(pos.qty_on_hand)) if pos else Decimal("0")
    reserved = Decimal(str(pos.qty_reserved)) if pos else Decimal("0")
    damaged = Decimal(str(pos.qty_damaged)) if pos else Decimal("0")
    available = on_hand - reserved - damaged
    return StandardResponse(
        data=StockReservationResponse(
            product_id=str(body.product_id),
            warehouse_id=str(body.warehouse_id),
            variant_id=str(body.variant_id) if body.variant_id else None,
            qty_reserved=str(reserved),
            qty_on_hand=str(on_hand),
            available_quantity=str(available),
            message="Reservation released successfully",
        ),
        message="Reservation released",
        meta=_meta(),
    )


# =============================================================================
# Phase 8 — Inventory Intelligence & Alerts
# =============================================================================

# ---------------------------------------------------------------------------
# Reorder Rules
# ---------------------------------------------------------------------------


@router.post(
    "/reorder-rules",
    response_model=StandardResponse[ReorderRuleResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a reorder rule",
)
def create_reorder_rule(
    company_id: UUID = Path(...),
    body: ReorderRuleCreate = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    rule_repo: ReorderRuleRepository = Depends(get_reorder_rule_repo),
) -> StandardResponse[ReorderRuleResponse]:
    from uuid import uuid4

    from modules.inventory.models.alerts import ReorderRule

    db = rule_repo.db
    rule = ReorderRule(
        id=uuid4(),
        company_id=company_id,
        product_id=str(body.product_id),
        variant_id=str(body.variant_id) if body.variant_id else None,
        warehouse_id=str(body.warehouse_id) if body.warehouse_id else None,
        reorder_level=body.reorder_level,
        reorder_quantity=body.reorder_quantity,
        is_active=body.is_active,
    )
    db.add(rule)
    db.flush()
    db.commit()
    db.refresh(rule)
    return StandardResponse(
        data=ReorderRuleResponse.model_validate(rule),
        message="Reorder rule created",
        meta=_meta(),
    )


@router.get(
    "/reorder-rules",
    response_model=StandardResponse[list[ReorderRuleResponse]],
    summary="List reorder rules for this company",
)
def list_reorder_rules(
    company_id: UUID = Path(...),
    active_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    current_user: CurrentUser = Depends(require_authenticated),
    rule_repo: ReorderRuleRepository = Depends(get_reorder_rule_repo),
) -> StandardResponse[list[ReorderRuleResponse]]:
    rules = rule_repo.list_for_company(
        company_id=company_id,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return StandardResponse(
        data=[ReorderRuleResponse.model_validate(r) for r in rules],
        message="Reorder rules retrieved",
        meta=_meta(),
    )


@router.get(
    "/reorder-rules/{rule_id}",
    response_model=StandardResponse[ReorderRuleResponse],
    summary="Get a reorder rule by ID",
)
def get_reorder_rule(
    company_id: UUID = Path(...),
    rule_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    rule_repo: ReorderRuleRepository = Depends(get_reorder_rule_repo),
) -> StandardResponse[ReorderRuleResponse]:
    rule = rule_repo.get_by_id_or_none(id=rule_id, company_id=company_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Reorder rule not found")
    return StandardResponse(
        data=ReorderRuleResponse.model_validate(rule),
        message="Reorder rule retrieved",
        meta=_meta(),
    )


@router.patch(
    "/reorder-rules/{rule_id}",
    response_model=StandardResponse[ReorderRuleResponse],
    summary="Update a reorder rule",
)
def update_reorder_rule(
    company_id: UUID = Path(...),
    rule_id: UUID = Path(...),
    body: ReorderRuleUpdate = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    rule_repo: ReorderRuleRepository = Depends(get_reorder_rule_repo),
) -> StandardResponse[ReorderRuleResponse]:
    rule = rule_repo.get_by_id_or_none(id=rule_id, company_id=company_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Reorder rule not found")
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)
    db = rule_repo.db
    db.flush()
    db.commit()
    db.refresh(rule)
    return StandardResponse(
        data=ReorderRuleResponse.model_validate(rule),
        message="Reorder rule updated",
        meta=_meta(),
    )


@router.delete(
    "/reorder-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete (soft-delete) a reorder rule",
)
def delete_reorder_rule(
    company_id: UUID = Path(...),
    rule_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    rule_repo: ReorderRuleRepository = Depends(get_reorder_rule_repo),
) -> Response:
    rule = rule_repo.get_by_id_or_none(id=rule_id, company_id=company_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Reorder rule not found")
    rule.is_deleted = True
    rule.is_active = False
    db = rule_repo.db
    db.flush()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Low Stock Alerts
# ---------------------------------------------------------------------------


@router.get(
    "/alerts",
    response_model=StandardResponse[list[LowStockAlertResponse]],
    summary="List inventory alerts for this company",
)
def list_alerts(
    company_id: UUID = Path(...),
    alert_status: str | None = None,
    alert_type: str | None = None,
    product_id: UUID | None = None,
    warehouse_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
    current_user: CurrentUser = Depends(require_authenticated),
    alert_repo: LowStockAlertRepository = Depends(get_alert_repo),
) -> StandardResponse[list[LowStockAlertResponse]]:
    alerts = alert_repo.list_for_company(
        company_id=company_id,
        status=alert_status,
        alert_type=alert_type,
        product_id=product_id,
        warehouse_id=warehouse_id,
        limit=limit,
        offset=offset,
    )
    return StandardResponse(
        data=[LowStockAlertResponse.model_validate(a) for a in alerts],
        message="Alerts retrieved",
        meta=_meta(),
    )


@router.get(
    "/alerts/{alert_id}",
    response_model=StandardResponse[LowStockAlertResponse],
    summary="Get an alert by ID",
)
def get_alert(
    company_id: UUID = Path(...),
    alert_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    alert_repo: LowStockAlertRepository = Depends(get_alert_repo),
) -> StandardResponse[LowStockAlertResponse]:
    alert = alert_repo.get_by_id_or_none(id=alert_id, company_id=company_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return StandardResponse(
        data=LowStockAlertResponse.model_validate(alert),
        message="Alert retrieved",
        meta=_meta(),
    )


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=StandardResponse[LowStockAlertResponse],
    summary="Acknowledge an open alert",
)
def acknowledge_alert(
    company_id: UUID = Path(...),
    alert_id: UUID = Path(...),
    body: AlertAcknowledgeRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    alert_repo: LowStockAlertRepository = Depends(get_alert_repo),
) -> StandardResponse[LowStockAlertResponse]:
    from core.utils.datetime import utcnow as _utcnow

    alert = alert_repo.get_by_id_or_none(id=alert_id, company_id=company_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status != "OPEN":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Alert is already {alert.status}",
        )
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = _utcnow()
    alert.acknowledged_by = str(current_user.user_id) if current_user.user_id else None
    if body.notes:
        alert.notes = body.notes
    db = alert_repo.db
    db.flush()
    db.commit()
    db.refresh(alert)
    return StandardResponse(
        data=LowStockAlertResponse.model_validate(alert),
        message="Alert acknowledged",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Reorder Suggestions
# ---------------------------------------------------------------------------


@router.get(
    "/suggestions",
    response_model=StandardResponse[list[ReorderSuggestionResponse]],
    summary="List reorder suggestions for this company",
)
def list_suggestions(
    company_id: UUID = Path(...),
    suggestion_status: str | None = None,
    product_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
    current_user: CurrentUser = Depends(require_authenticated),
    suggestion_repo: ReorderSuggestionRepository = Depends(get_suggestion_repo),
) -> StandardResponse[list[ReorderSuggestionResponse]]:
    suggestions = suggestion_repo.list_for_company(
        company_id=company_id,
        status=suggestion_status,
        product_id=product_id,
        limit=limit,
        offset=offset,
    )
    return StandardResponse(
        data=[ReorderSuggestionResponse.model_validate(s) for s in suggestions],
        message="Suggestions retrieved",
        meta=_meta(),
    )


@router.get(
    "/suggestions/{suggestion_id}",
    response_model=StandardResponse[ReorderSuggestionResponse],
    summary="Get a reorder suggestion by ID",
)
def get_suggestion(
    company_id: UUID = Path(...),
    suggestion_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    suggestion_repo: ReorderSuggestionRepository = Depends(get_suggestion_repo),
) -> StandardResponse[ReorderSuggestionResponse]:
    suggestion = suggestion_repo.get_by_id_or_none(
        id=suggestion_id, company_id=company_id
    )
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return StandardResponse(
        data=ReorderSuggestionResponse.model_validate(suggestion),
        message="Suggestion retrieved",
        meta=_meta(),
    )


@router.post(
    "/suggestions/{suggestion_id}/acknowledge",
    response_model=StandardResponse[ReorderSuggestionResponse],
    summary="Acknowledge a reorder suggestion",
)
def acknowledge_suggestion(
    company_id: UUID = Path(...),
    suggestion_id: UUID = Path(...),
    body: SuggestionAcknowledgeRequest = Body(...),
    current_user: CurrentUser = Depends(require_authenticated),
    suggestion_repo: ReorderSuggestionRepository = Depends(get_suggestion_repo),
) -> StandardResponse[ReorderSuggestionResponse]:
    suggestion = suggestion_repo.get_by_id_or_none(
        id=suggestion_id, company_id=company_id
    )
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Suggestion is already {suggestion.status}",
        )
    suggestion.status = "ACKNOWLEDGED"
    db = suggestion_repo.db
    db.flush()
    db.commit()
    db.refresh(suggestion)
    return StandardResponse(
        data=ReorderSuggestionResponse.model_validate(suggestion),
        message="Suggestion acknowledged",
        meta=_meta(),
    )


# =============================================================================
# Phase 9 — Reporting Foundation
# =============================================================================


# ---------------------------------------------------------------------------
# Report 1 — Inventory Summary
# ---------------------------------------------------------------------------


@router.get(
    "/reports/inventory-summary",
    response_model=StandardResponse[InventorySummaryReport],
    summary="Inventory Summary report",
)
def report_inventory_summary(
    company_id: UUID = Path(...),
    warehouse_id: UUID | None = None,
    category_id: UUID | None = None,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportQueryService = Depends(get_report_service),
) -> StandardResponse[InventorySummaryReport]:
    data = svc.inventory_summary(
        company_id=company_id,
        warehouse_id=warehouse_id,
        category_id=category_id,
    )
    return StandardResponse(
        data=InventorySummaryReport(**data),
        message="Inventory summary report",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Report 2 — Stock Ledger
# ---------------------------------------------------------------------------


@router.get(
    "/reports/stock-ledger",
    response_model=StandardResponse[StockLedgerReport],
    summary="Stock Ledger report",
)
def report_stock_ledger(
    company_id: UUID = Path(...),
    product_id: UUID | None = None,
    warehouse_id: UUID | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 500,
    offset: int = 0,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportQueryService = Depends(get_report_service),
) -> StandardResponse[StockLedgerReport]:
    from datetime import datetime as _dt

    df = _dt.fromisoformat(date_from) if date_from else None
    dt = _dt.fromisoformat(date_to) if date_to else None
    data = svc.stock_ledger(
        company_id=company_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        date_from=df,
        date_to=dt,
        limit=limit,
        offset=offset,
    )
    return StandardResponse(
        data=StockLedgerReport(**data),
        message="Stock ledger report",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Report 3 — Inventory Valuation
# ---------------------------------------------------------------------------


@router.get(
    "/reports/inventory-valuation",
    response_model=StandardResponse[InventoryValuationReport],
    summary="Inventory Valuation report",
)
def report_inventory_valuation(
    company_id: UUID = Path(...),
    warehouse_id: UUID | None = None,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportQueryService = Depends(get_report_service),
) -> StandardResponse[InventoryValuationReport]:
    data = svc.inventory_valuation(company_id=company_id, warehouse_id=warehouse_id)
    return StandardResponse(
        data=InventoryValuationReport(**data),
        message="Inventory valuation report",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Report 4 — Stock Position
# ---------------------------------------------------------------------------


@router.get(
    "/reports/stock-position",
    response_model=StandardResponse[StockPositionReport],
    summary="Stock Position report",
)
def report_stock_position(
    company_id: UUID = Path(...),
    warehouse_id: UUID | None = None,
    below_reorder_only: bool = False,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportQueryService = Depends(get_report_service),
) -> StandardResponse[StockPositionReport]:
    data = svc.stock_position_report(
        company_id=company_id,
        warehouse_id=warehouse_id,
        below_reorder_only=below_reorder_only,
    )
    return StandardResponse(
        data=StockPositionReport(**data),
        message="Stock position report",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Report 5 — Warehouse Utilisation
# ---------------------------------------------------------------------------


@router.get(
    "/reports/warehouse-utilisation",
    response_model=StandardResponse[WarehouseUtilisationReport],
    summary="Warehouse Utilisation report",
)
def report_warehouse_utilisation(
    company_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportQueryService = Depends(get_report_service),
) -> StandardResponse[WarehouseUtilisationReport]:
    data = svc.warehouse_utilisation(company_id=company_id)
    return StandardResponse(
        data=WarehouseUtilisationReport(**data),
        message="Warehouse utilisation report",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Reports 6 & 7 — Category & Brand Performance
# ---------------------------------------------------------------------------


@router.get(
    "/reports/category-brand",
    response_model=StandardResponse[CategoryBrandReport],
    summary="Category and Brand performance report",
)
def report_category_brand(
    company_id: UUID = Path(...),
    date_from: str | None = None,
    date_to: str | None = None,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportQueryService = Depends(get_report_service),
) -> StandardResponse[CategoryBrandReport]:
    from datetime import datetime as _dt

    df = _dt.fromisoformat(date_from) if date_from else None
    dt = _dt.fromisoformat(date_to) if date_to else None
    data = svc.category_brand_report(company_id=company_id, date_from=df, date_to=dt)
    return StandardResponse(
        data=CategoryBrandReport(**data),
        message="Category and brand report",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Report 8 — Dead Stock
# ---------------------------------------------------------------------------


@router.get(
    "/reports/dead-stock",
    response_model=StandardResponse[DeadStockReport],
    summary="Dead Stock report",
)
def report_dead_stock(
    company_id: UUID = Path(...),
    threshold_days: int = 90,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportQueryService = Depends(get_report_service),
) -> StandardResponse[DeadStockReport]:
    data = svc.dead_stock(company_id=company_id, threshold_days=threshold_days)
    return StandardResponse(
        data=DeadStockReport(**data),
        message="Dead stock report",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Reports 9 & 10 — Movement Velocity
# ---------------------------------------------------------------------------


@router.get(
    "/reports/movement-velocity",
    response_model=StandardResponse[MovementVelocityReport],
    summary="Fast and Slow Moving Products report",
)
def report_movement_velocity(
    company_id: UUID = Path(...),
    date_from: str | None = None,
    date_to: str | None = None,
    top_n: int = 20,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportQueryService = Depends(get_report_service),
) -> StandardResponse[MovementVelocityReport]:
    from datetime import datetime as _dt

    df = _dt.fromisoformat(date_from) if date_from else None
    dt = _dt.fromisoformat(date_to) if date_to else None
    data = svc.movement_velocity(
        company_id=company_id, date_from=df, date_to=dt, top_n=top_n
    )
    return StandardResponse(
        data=MovementVelocityReport(**data),
        message="Movement velocity report",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Report 11 — Stock Aging
# ---------------------------------------------------------------------------


@router.get(
    "/reports/stock-aging",
    response_model=StandardResponse[StockAgingReport],
    summary="Stock Aging report",
)
def report_stock_aging(
    company_id: UUID = Path(...),
    warehouse_id: UUID | None = None,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportQueryService = Depends(get_report_service),
) -> StandardResponse[StockAgingReport]:
    data = svc.stock_aging(company_id=company_id, warehouse_id=warehouse_id)
    return StandardResponse(
        data=StockAgingReport(**data),
        message="Stock aging report",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Reports 12 & 13 — Operational (Adjustments + Transfers)
# ---------------------------------------------------------------------------


@router.get(
    "/reports/operational",
    response_model=StandardResponse[OperationalReport],
    summary="Inventory Adjustment and Stock Transfer audit report",
)
def report_operational(
    company_id: UUID = Path(...),
    date_from: str | None = None,
    date_to: str | None = None,
    warehouse_id: UUID | None = None,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportQueryService = Depends(get_report_service),
) -> StandardResponse[OperationalReport]:
    from datetime import datetime as _dt

    df = _dt.fromisoformat(date_from) if date_from else None
    dt = _dt.fromisoformat(date_to) if date_to else None
    data = svc.operational_report(
        company_id=company_id,
        date_from=df,
        date_to=dt,
        warehouse_id=warehouse_id,
    )
    return StandardResponse(
        data=OperationalReport(**data),
        message="Operational audit report",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Report 14 — Inventory Trend Analysis
# ---------------------------------------------------------------------------


@router.get(
    "/reports/trend-analysis",
    response_model=StandardResponse[TrendAnalysisReport],
    summary="Inventory Trend Analysis for a product",
)
def report_trend_analysis(
    company_id: UUID = Path(...),
    product_id: UUID | None = None,
    warehouse_id: UUID | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: ReportQueryService = Depends(get_report_service),
) -> StandardResponse[TrendAnalysisReport]:
    if product_id is None:
        raise HTTPException(status_code=400, detail="product_id is required")
    from datetime import datetime as _dt

    df = _dt.fromisoformat(date_from) if date_from else None
    dt = _dt.fromisoformat(date_to) if date_to else None
    data = svc.trend_analysis(
        company_id=company_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        date_from=df,
        date_to=dt,
    )
    return StandardResponse(
        data=TrendAnalysisReport(**data),
        message="Inventory trend analysis",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# KPI Dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/kpis",
    response_model=StandardResponse[KPIDashboard],
    summary="Inventory KPI Dashboard (10 KPIs)",
)
def report_kpis(
    company_id: UUID = Path(...),
    period_days: int = 90,
    current_user: CurrentUser = Depends(require_authenticated),
    svc: KPIService = Depends(get_kpi_service),
) -> StandardResponse[KPIDashboard]:
    data = svc.compute(company_id=company_id, period_days=period_days)
    return StandardResponse(
        data=KPIDashboard(**data),
        message="KPI dashboard",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Export endpoints (T250)
# ---------------------------------------------------------------------------


from pydantic import BaseModel as _BaseModel  # noqa: E402


class _ExportBody(_BaseModel):
    format: str = "csv"


@router.post(
    "/reports/inventory-summary/export",
    response_model=StandardResponse[ExportResponse],
    summary="Export Inventory Summary to CSV or Excel",
)
def export_inventory_summary(
    company_id: UUID = Path(...),
    body: _ExportBody = Body(...),
    warehouse_id: UUID | None = None,
    current_user: CurrentUser = Depends(require_authenticated),
    report_svc: ReportQueryService = Depends(get_report_service),
    export_svc: ExportService = Depends(get_export_service),
) -> StandardResponse[ExportResponse]:
    data = report_svc.inventory_summary(
        company_id=company_id, warehouse_id=warehouse_id
    )
    result = export_svc.export_and_upload(
        data["rows"],
        report_name="inventory_summary",
        fmt=body.format,
        company_id=str(company_id),
    )
    return StandardResponse(
        data=ExportResponse(**result),
        message=f"Exported to {body.format}",
        meta=_meta(),
    )


@router.post(
    "/reports/stock-ledger/export",
    response_model=StandardResponse[ExportResponse],
    summary="Export Stock Ledger to CSV or Excel",
)
def export_stock_ledger(
    company_id: UUID = Path(...),
    body: _ExportBody = Body(...),
    product_id: UUID | None = None,
    warehouse_id: UUID | None = None,
    current_user: CurrentUser = Depends(require_authenticated),
    report_svc: ReportQueryService = Depends(get_report_service),
    export_svc: ExportService = Depends(get_export_service),
) -> StandardResponse[ExportResponse]:
    data = report_svc.stock_ledger(
        company_id=company_id, product_id=product_id, warehouse_id=warehouse_id
    )
    result = export_svc.export_and_upload(
        data["rows"],
        report_name="stock_ledger",
        fmt=body.format,
        company_id=str(company_id),
    )
    return StandardResponse(
        data=ExportResponse(**result),
        message=f"Exported to {body.format}",
        meta=_meta(),
    )


# =============================================================================
# Lookup / scanner API (Phase 10 — T263 / T264)
# =============================================================================


def _build_lookup_result(
    product: Product,
    barcode_value: str | None,
    stock_svc: StockLedgerService,
    company_id: UUID,
) -> LookupResult:
    """Build a LookupResult from a Product ORM object."""

    positions = stock_svc.list_positions_for_product(
        company_id=company_id, product_id=product.id
    )
    stock_positions = [
        {
            "warehouse_id": str(p.warehouse_id),
            "qty_on_hand": str(p.qty_on_hand),
            "qty_reserved": str(p.qty_reserved),
            "unit_cost": str(p.unit_cost) if p.unit_cost is not None else None,
        }
        for p in positions
    ]
    return LookupResult(
        product_id=str(product.id),
        product_code=product.product_code,
        product_name=product.name,
        product_type=product.product_type,
        status=product.status,
        base_uom_id=str(product.base_uom_id),
        barcode_value=barcode_value,
        stock_positions=stock_positions,
    )


@router.get(
    "/lookup/barcode/{barcode_value}",
    response_model=StandardResponse[LookupResult],
    summary="Scanner barcode lookup",
    description=(
        "Resolve a barcode value to the matching product and its current "
        "stock positions.  Uses the B-tree index on inventory_product_barcodes "
        "for sub-millisecond lookup. Returns 404 if not found."
    ),
)
def lookup_by_barcode(
    company_id: UUID = Path(...),
    barcode_value: str = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    product_svc: ProductService = Depends(get_product_service),
    stock_svc: StockLedgerService = Depends(get_stock_ledger_service),
) -> StandardResponse[LookupResult]:
    product = product_svc._repo.get_by_barcode(
        company_id=company_id, barcode_value=barcode_value
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No product found for barcode '{barcode_value}'",
        )
    result = _build_lookup_result(
        product=product,
        barcode_value=barcode_value,
        stock_svc=stock_svc,
        company_id=company_id,
    )
    return StandardResponse(data=result, message="Product found", meta=_meta())


@router.get(
    "/lookup/sku/{sku}",
    response_model=StandardResponse[LookupResult],
    summary="Scanner SKU lookup",
    description=(
        "Resolve a product SKU (product_code) to the matching product and "
        "its current stock positions.  Case-insensitive B-tree lookup. "
        "Returns 404 if not found."
    ),
)
def lookup_by_sku(
    company_id: UUID = Path(...),
    sku: str = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    product_svc: ProductService = Depends(get_product_service),
    stock_svc: StockLedgerService = Depends(get_stock_ledger_service),
) -> StandardResponse[LookupResult]:
    product = product_svc._repo.get_by_code(company_id=company_id, product_code=sku)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No product found for SKU '{sku}'",
        )
    result = _build_lookup_result(
        product=product,
        barcode_value=None,
        stock_svc=stock_svc,
        company_id=company_id,
    )
    return StandardResponse(data=result, message="Product found", meta=_meta())


@router.get(
    "/products/{product_id}/label-data",
    response_model=StandardResponse[LabelData],
    summary="Product label data",
    description=(
        "Return the minimal data required to render a barcode label for a "
        "product: name, SKU, primary barcode, and unit of measure."
    ),
)
def get_label_data(
    company_id: UUID = Path(...),
    product_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_authenticated),
    product_svc: ProductService = Depends(get_product_service),
    uom_svc: UOMService = Depends(get_uom_service),
) -> StandardResponse[LabelData]:
    product = product_svc.get_product(company_id=company_id, product_id=product_id)

    # Get primary barcode (or first barcode)
    barcodes = product_svc.list_barcodes(company_id=company_id, product_id=product_id)
    primary = next(
        (b for b in barcodes if b.is_primary), barcodes[0] if barcodes else None
    )

    # Get UOM details
    uom = uom_svc.get_by_id(company_id=company_id, uom_id=UUID(product.base_uom_id))

    label = LabelData(
        product_id=str(product.id),
        product_code=product.product_code,
        product_name=product.name,
        barcode_value=primary.barcode_value if primary else None,
        barcode_type=primary.barcode_type if primary else None,
        uom_code=uom.code,
        uom_name=uom.name,
    )
    return StandardResponse(data=label, message="Label data retrieved", meta=_meta())

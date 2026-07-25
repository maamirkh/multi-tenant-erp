"""FastAPI dependency injection functions for the Inventory module.

All DI factories are synchronous, matching the sync ``Session`` / ``get_db``
pattern used throughout the backend.

Spec ref: specs/005-inventory-management/spec.md
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from core.database.session import get_db
from modules.inventory.repositories.adjustment_repository import AdjustmentRepository
from modules.inventory.repositories.alerts_repository import (
    LowStockAlertRepository,
    ReorderRuleRepository,
    ReorderSuggestionRepository,
)
from modules.inventory.repositories.attribute_repository import (
    AttributeDefinitionRepository,
    AttributeSetMembershipRepository,
    AttributeSetRepository,
)
from modules.inventory.repositories.brand_repository import BrandRepository
from modules.inventory.repositories.category_repository import CategoryRepository
from modules.inventory.repositories.custom_field_repository import (
    CustomFieldDefinitionRepository,
)
from modules.inventory.repositories.feature_flag_repository import FeatureFlagRepository
from modules.inventory.repositories.product_enrichment_repository import (
    ImportJobRepository,
    ProductCustomFieldValueRepository,
    ProductInternalNoteRepository,
    ProductTagRepository,
)
from modules.inventory.repositories.product_repository import (
    ProductBarcodeRepository,
    ProductRepository,
    ProductVariantRepository,
)
from modules.inventory.repositories.reason_code_repository import ReasonCodeRepository
from modules.inventory.repositories.stock_repository import (
    SnapshotRepository,
    StockMovementRepository,
    StockPositionRepository,
)
from modules.inventory.repositories.tag_repository import TagRepository
from modules.inventory.repositories.transfer_repository import TransferRepository
from modules.inventory.repositories.uom_repository import (
    UOMConversionRepository,
    UOMRepository,
)
from modules.inventory.repositories.warehouse_repository import (
    WarehouseLocationRepository,
    WarehouseRepository,
)
from modules.inventory.services.adjustment_service import AdjustmentService
from modules.inventory.services.alert_service import AlertEvaluationService
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
from modules.inventory.services.product_enrichment_service import (
    ProductEnrichmentService,
)
from modules.inventory.services.product_service import ProductService
from modules.inventory.services.report_service import ReportQueryService
from modules.inventory.services.stock_service import StockLedgerService
from modules.inventory.services.transfer_service import TransferService
from modules.inventory.services.warehouse_service import WarehouseService

# ---------------------------------------------------------------------------
# Repository factories
# ---------------------------------------------------------------------------


def get_feature_flag_repo(db: Session = Depends(get_db)) -> FeatureFlagRepository:
    return FeatureFlagRepository(db)


def get_category_repo(db: Session = Depends(get_db)) -> CategoryRepository:
    return CategoryRepository(db)


def get_brand_repo(db: Session = Depends(get_db)) -> BrandRepository:
    return BrandRepository(db)


def get_uom_repo(db: Session = Depends(get_db)) -> UOMRepository:
    return UOMRepository(db)


def get_uom_conversion_repo(db: Session = Depends(get_db)) -> UOMConversionRepository:
    return UOMConversionRepository(db)


def get_tag_repo(db: Session = Depends(get_db)) -> TagRepository:
    return TagRepository(db)


def get_reason_code_repo(db: Session = Depends(get_db)) -> ReasonCodeRepository:
    return ReasonCodeRepository(db)


def get_custom_field_repo(
    db: Session = Depends(get_db),
) -> CustomFieldDefinitionRepository:
    return CustomFieldDefinitionRepository(db)


def get_attr_definition_repo(
    db: Session = Depends(get_db),
) -> AttributeDefinitionRepository:
    return AttributeDefinitionRepository(db)


def get_attr_set_repo(db: Session = Depends(get_db)) -> AttributeSetRepository:
    return AttributeSetRepository(db)


def get_attr_set_membership_repo(
    db: Session = Depends(get_db),
) -> AttributeSetMembershipRepository:
    return AttributeSetMembershipRepository(db)


# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------


def get_feature_flag_service(db: Session = Depends(get_db)) -> FeatureFlagService:
    return FeatureFlagService(db=db, flag_repo=FeatureFlagRepository(db))


def get_category_service(db: Session = Depends(get_db)) -> CategoryService:
    return CategoryService(db=db, category_repo=CategoryRepository(db))


def get_brand_service(db: Session = Depends(get_db)) -> BrandService:
    return BrandService(db=db, brand_repo=BrandRepository(db))


def get_uom_service(db: Session = Depends(get_db)) -> UOMService:
    return UOMService(db=db, uom_repo=UOMRepository(db))


def get_uom_conversion_service(db: Session = Depends(get_db)) -> UOMConversionService:
    return UOMConversionService(
        db=db,
        uom_repo=UOMRepository(db),
        conversion_repo=UOMConversionRepository(db),
    )


def get_tag_service(db: Session = Depends(get_db)) -> TagService:
    return TagService(db=db, tag_repo=TagRepository(db))


def get_reason_code_service(db: Session = Depends(get_db)) -> ReasonCodeService:
    return ReasonCodeService(db=db, reason_code_repo=ReasonCodeRepository(db))


def get_custom_field_service(db: Session = Depends(get_db)) -> CustomFieldService:
    return CustomFieldService(
        db=db, custom_field_repo=CustomFieldDefinitionRepository(db)
    )


def get_attr_definition_service(
    db: Session = Depends(get_db),
) -> AttributeDefinitionService:
    return AttributeDefinitionService(
        db=db, attr_repo=AttributeDefinitionRepository(db)
    )


def get_attr_set_service(db: Session = Depends(get_db)) -> AttributeSetService:
    return AttributeSetService(
        db=db,
        attr_set_repo=AttributeSetRepository(db),
        membership_repo=AttributeSetMembershipRepository(db),
        attr_repo=AttributeDefinitionRepository(db),
    )


# ---------------------------------------------------------------------------
# Product module factories (Phase 2)
# ---------------------------------------------------------------------------


def get_product_repo(db: Session = Depends(get_db)) -> ProductRepository:
    return ProductRepository(db)


def get_product_variant_repo(db: Session = Depends(get_db)) -> ProductVariantRepository:
    return ProductVariantRepository(db)


def get_product_barcode_repo(db: Session = Depends(get_db)) -> ProductBarcodeRepository:
    return ProductBarcodeRepository(db)


def get_product_service(db: Session = Depends(get_db)) -> ProductService:
    return ProductService(
        db=db,
        product_repo=ProductRepository(db),
        variant_repo=ProductVariantRepository(db),
        barcode_repo=ProductBarcodeRepository(db),
        uom_repo=UOMRepository(db),
    )


# ---------------------------------------------------------------------------
# Phase 3 enrichment factories
# ---------------------------------------------------------------------------


def get_product_tag_repo(db: Session = Depends(get_db)) -> ProductTagRepository:
    return ProductTagRepository(db)


def get_product_cfv_repo(
    db: Session = Depends(get_db),
) -> ProductCustomFieldValueRepository:
    return ProductCustomFieldValueRepository(db)


def get_product_note_repo(
    db: Session = Depends(get_db),
) -> ProductInternalNoteRepository:
    return ProductInternalNoteRepository(db)


def get_import_job_repo(db: Session = Depends(get_db)) -> ImportJobRepository:
    return ImportJobRepository(db)


def get_product_enrichment_service(
    db: Session = Depends(get_db),
) -> ProductEnrichmentService:
    return ProductEnrichmentService(
        db=db,
        product_repo=ProductRepository(db),
        tag_repo=ProductTagRepository(db),
        cfv_repo=ProductCustomFieldValueRepository(db),
        note_repo=ProductInternalNoteRepository(db),
    )


def get_bulk_import_service(db: Session = Depends(get_db)) -> BulkImportService:
    return BulkImportService(
        db=db,
        product_repo=ProductRepository(db),
        job_repo=ImportJobRepository(db),
        product_service=ProductService(
            db=db,
            product_repo=ProductRepository(db),
            variant_repo=ProductVariantRepository(db),
            barcode_repo=ProductBarcodeRepository(db),
            uom_repo=UOMRepository(db),
        ),
    )


# ---------------------------------------------------------------------------
# Phase 4 warehouse factories
# ---------------------------------------------------------------------------


def get_warehouse_repo(db: Session = Depends(get_db)) -> WarehouseRepository:
    return WarehouseRepository(db)


def get_warehouse_location_repo(
    db: Session = Depends(get_db),
) -> WarehouseLocationRepository:
    return WarehouseLocationRepository(db)


def get_warehouse_service(db: Session = Depends(get_db)) -> WarehouseService:
    return WarehouseService(
        db=db,
        warehouse_repo=WarehouseRepository(db),
        location_repo=WarehouseLocationRepository(db),
    )


# ---------------------------------------------------------------------------
# Phase 5 stock factories
# ---------------------------------------------------------------------------


def get_stock_position_repo(db: Session = Depends(get_db)) -> StockPositionRepository:
    return StockPositionRepository(db)


def get_stock_movement_repo(db: Session = Depends(get_db)) -> StockMovementRepository:
    return StockMovementRepository(db)


def get_snapshot_repo(db: Session = Depends(get_db)) -> SnapshotRepository:
    return SnapshotRepository(db)


def get_stock_ledger_service(db: Session = Depends(get_db)) -> StockLedgerService:
    return StockLedgerService(
        db=db,
        position_repo=StockPositionRepository(db),
        movement_repo=StockMovementRepository(db),
        snapshot_repo=SnapshotRepository(db),
        warehouse_repo=WarehouseRepository(db),
        alert_svc=AlertEvaluationService(
            db=db,
            alert_repo=LowStockAlertRepository(db),
            rule_repo=ReorderRuleRepository(db),
            suggestion_repo=ReorderSuggestionRepository(db),
            flag_repo=FeatureFlagRepository(db),
        ),
    )


# ---------------------------------------------------------------------------
# Phase 6 adjustment factories
# ---------------------------------------------------------------------------


def get_adjustment_repo(db: Session = Depends(get_db)) -> AdjustmentRepository:
    return AdjustmentRepository(db)


def get_transfer_repo(db: Session = Depends(get_db)) -> TransferRepository:
    return TransferRepository(db)


# ---------------------------------------------------------------------------
# Phase 8 alert factories
# ---------------------------------------------------------------------------


def get_alert_repo(db: Session = Depends(get_db)) -> LowStockAlertRepository:
    return LowStockAlertRepository(db)


def get_reorder_rule_repo(db: Session = Depends(get_db)) -> ReorderRuleRepository:
    return ReorderRuleRepository(db)


def get_suggestion_repo(db: Session = Depends(get_db)) -> ReorderSuggestionRepository:
    return ReorderSuggestionRepository(db)


def get_alert_evaluation_service(
    db: Session = Depends(get_db),
) -> AlertEvaluationService:
    return AlertEvaluationService(
        db=db,
        alert_repo=LowStockAlertRepository(db),
        rule_repo=ReorderRuleRepository(db),
        suggestion_repo=ReorderSuggestionRepository(db),
        flag_repo=FeatureFlagRepository(db),
    )


def _make_alert_svc(db: Session) -> AlertEvaluationService:
    """Helper: build AlertEvaluationService without FastAPI Depends."""
    return AlertEvaluationService(
        db=db,
        alert_repo=LowStockAlertRepository(db),
        rule_repo=ReorderRuleRepository(db),
        suggestion_repo=ReorderSuggestionRepository(db),
        flag_repo=FeatureFlagRepository(db),
    )


def get_transfer_service(db: Session = Depends(get_db)) -> TransferService:
    return TransferService(
        db=db,
        transfer_repo=TransferRepository(db),
        stock_ledger=StockLedgerService(
            db=db,
            position_repo=StockPositionRepository(db),
            movement_repo=StockMovementRepository(db),
            snapshot_repo=SnapshotRepository(db),
            warehouse_repo=WarehouseRepository(db),
            alert_svc=_make_alert_svc(db),
        ),
        position_repo=StockPositionRepository(db),
        warehouse_repo=WarehouseRepository(db),
    )


def get_report_service(db: Session = Depends(get_db)) -> ReportQueryService:
    return ReportQueryService(db=db)


def get_kpi_service(db: Session = Depends(get_db)) -> KPIService:
    return KPIService(db=db)


def get_export_service() -> ExportService:
    return ExportService(storage=None)


def get_adjustment_service(db: Session = Depends(get_db)) -> AdjustmentService:
    return AdjustmentService(
        db=db,
        adjustment_repo=AdjustmentRepository(db),
        stock_ledger=StockLedgerService(
            db=db,
            position_repo=StockPositionRepository(db),
            movement_repo=StockMovementRepository(db),
            snapshot_repo=SnapshotRepository(db),
            warehouse_repo=WarehouseRepository(db),
            alert_svc=_make_alert_svc(db),
        ),
        position_repo=StockPositionRepository(db),
        warehouse_repo=WarehouseRepository(db),
        flag_service=FeatureFlagService(
            db=db,
            flag_repo=FeatureFlagRepository(db),
        ),
    )

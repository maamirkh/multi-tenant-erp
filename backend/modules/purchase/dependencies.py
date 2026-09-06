"""FastAPI dependency injection functions for the Purchase module.

All DI factories are synchronous, matching the sync ``Session`` / ``get_db``
pattern used throughout the backend.

Spec ref: specs/006-purchase-management/plan.md — Application Layer
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from core.database.session import get_db
from modules.purchase.repositories.approval import (
    ApprovalDelegateRepository,
    ApprovalLevelRepository,
    ApprovalMatrixRepository,
    ApprovalRecordRepository,
    MatrixRuleRepository,
)
from modules.purchase.repositories.feature_flag_repository import (
    PurchaseFeatureFlagRepository,
)
from modules.purchase.repositories.goods_receipt import (
    GoodsReceiptRepository,
    GRLineRepository,
)
from modules.purchase.repositories.master import (
    PaymentTermsRepository,
    PurchasePolicyRepository,
    PurchaseReasonCodeRepository,
    SupplierCategoryRepository,
)
from modules.purchase.repositories.purchase_order import (
    POAdditionalChargeRepository,
    POAmendmentRepository,
    POLineRepository,
    PurchaseOrderRepository,
)
from modules.purchase.repositories.purchase_request import (
    PRLineRepository,
    PurchaseRequestRepository,
)
from modules.purchase.repositories.supplier import (
    SupplierAddressRepository,
    SupplierContactRepository,
    SupplierRepository,
)
from modules.purchase.repositories.supplier_enrichment import (
    BankDetailsRepository,
    CreditLimitRepository,
    SupplierDocumentRepository,
    SupplierLeadTimeRepository,
    SupplierRatingRepository,
)
from modules.purchase.repositories.vendor_return import (
    ReturnLineRepository,
    VendorReturnRepository,
)
from modules.purchase.services.approval_service import ApprovalService
from modules.purchase.services.cost_service import CostService
from modules.purchase.services.feature_flag_service import PurchaseFeatureFlagService
from modules.purchase.services.gr_service import GRService
from modules.purchase.services.kpi_service import KPIService
from modules.purchase.services.master_data_service import (
    PaymentTermsService,
    PurchaseReasonCodeService,
    SupplierCategoryService,
)
from modules.purchase.services.po_service import POService
from modules.purchase.services.policy_service import PurchasePolicyService
from modules.purchase.services.pr_service import PRService
from modules.purchase.services.report_export_service import ReportExportService
from modules.purchase.services.report_service import ReportService
from modules.purchase.services.rma_service import RMAService
from modules.purchase.services.sequence_service import PurchaseSequenceService
from modules.purchase.services.supplier_document_service import SupplierDocumentService
from modules.purchase.services.supplier_import_service import SupplierImportService
from modules.purchase.services.supplier_rating_service import SupplierRatingService
from modules.purchase.services.supplier_service import SupplierService

# ---------------------------------------------------------------------------
# Repository factories
# ---------------------------------------------------------------------------


def get_purchase_feature_flag_repo(
    db: Session = Depends(get_db),
) -> PurchaseFeatureFlagRepository:
    return PurchaseFeatureFlagRepository(db)


def get_supplier_category_repo(
    db: Session = Depends(get_db),
) -> SupplierCategoryRepository:
    return SupplierCategoryRepository(db)


def get_payment_terms_repo(
    db: Session = Depends(get_db),
) -> PaymentTermsRepository:
    return PaymentTermsRepository(db)


def get_purchase_reason_code_repo(
    db: Session = Depends(get_db),
) -> PurchaseReasonCodeRepository:
    return PurchaseReasonCodeRepository(db)


def get_purchase_policy_repo(
    db: Session = Depends(get_db),
) -> PurchasePolicyRepository:
    return PurchasePolicyRepository(db)


# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------


def get_purchase_feature_flag_service(
    db: Session = Depends(get_db),
) -> PurchaseFeatureFlagService:
    return PurchaseFeatureFlagService(
        db=db,
        flag_repo=PurchaseFeatureFlagRepository(db),
    )


def get_supplier_category_service(
    db: Session = Depends(get_db),
) -> SupplierCategoryService:
    return SupplierCategoryService(
        db=db,
        category_repo=SupplierCategoryRepository(db),
    )


def get_payment_terms_service(
    db: Session = Depends(get_db),
) -> PaymentTermsService:
    return PaymentTermsService(
        db=db,
        terms_repo=PaymentTermsRepository(db),
    )


def get_purchase_reason_code_service(
    db: Session = Depends(get_db),
) -> PurchaseReasonCodeService:
    return PurchaseReasonCodeService(
        db=db,
        reason_repo=PurchaseReasonCodeRepository(db),
    )


def get_purchase_policy_service(
    db: Session = Depends(get_db),
) -> PurchasePolicyService:
    return PurchasePolicyService(
        db=db,
        policy_repo=PurchasePolicyRepository(db),
    )


def get_purchase_sequence_service(
    db: Session = Depends(get_db),
) -> PurchaseSequenceService:
    return PurchaseSequenceService(db=db)


def get_supplier_repo(
    db: Session = Depends(get_db),
) -> SupplierRepository:
    return SupplierRepository(db)


def get_supplier_contact_repo(
    db: Session = Depends(get_db),
) -> SupplierContactRepository:
    return SupplierContactRepository(db)


def get_supplier_address_repo(
    db: Session = Depends(get_db),
) -> SupplierAddressRepository:
    return SupplierAddressRepository(db)


def get_supplier_service(
    db: Session = Depends(get_db),
) -> SupplierService:
    return SupplierService(
        db=db,
        supplier_repo=SupplierRepository(db),
        contact_repo=SupplierContactRepository(db),
        address_repo=SupplierAddressRepository(db),
    )


def get_credit_limit_repo(
    db: Session = Depends(get_db),
) -> CreditLimitRepository:
    return CreditLimitRepository(db)


def get_bank_details_repo(
    db: Session = Depends(get_db),
) -> BankDetailsRepository:
    return BankDetailsRepository(db)


def get_supplier_rating_repo(
    db: Session = Depends(get_db),
) -> SupplierRatingRepository:
    return SupplierRatingRepository(db)


def get_supplier_document_repo(
    db: Session = Depends(get_db),
) -> SupplierDocumentRepository:
    return SupplierDocumentRepository(db)


def get_supplier_lead_time_repo(
    db: Session = Depends(get_db),
) -> SupplierLeadTimeRepository:
    return SupplierLeadTimeRepository(db)


def get_supplier_rating_service(
    db: Session = Depends(get_db),
) -> SupplierRatingService:
    return SupplierRatingService(db=db)


def get_supplier_document_service(
    db: Session = Depends(get_db),
) -> SupplierDocumentService:
    return SupplierDocumentService(db=db)


def get_approval_matrix_repo(
    db: Session = Depends(get_db),
) -> ApprovalMatrixRepository:
    return ApprovalMatrixRepository(db)


def get_matrix_rule_repo(
    db: Session = Depends(get_db),
) -> MatrixRuleRepository:
    return MatrixRuleRepository(db)


def get_approval_level_repo(
    db: Session = Depends(get_db),
) -> ApprovalLevelRepository:
    return ApprovalLevelRepository(db)


def get_approval_record_repo(
    db: Session = Depends(get_db),
) -> ApprovalRecordRepository:
    return ApprovalRecordRepository(db)


def get_approval_delegate_repo(
    db: Session = Depends(get_db),
) -> ApprovalDelegateRepository:
    return ApprovalDelegateRepository(db)


def get_approval_service(
    db: Session = Depends(get_db),
) -> ApprovalService:
    return ApprovalService(
        db=db,
        matrix_repo=ApprovalMatrixRepository(db),
        rule_repo=MatrixRuleRepository(db),
        level_repo=ApprovalLevelRepository(db),
        record_repo=ApprovalRecordRepository(db),
        delegate_repo=ApprovalDelegateRepository(db),
        policy_repo=PurchasePolicyRepository(db),
    )


def get_purchase_request_repo(
    db: Session = Depends(get_db),
) -> PurchaseRequestRepository:
    return PurchaseRequestRepository(db)


def get_pr_line_repo(
    db: Session = Depends(get_db),
) -> PRLineRepository:
    return PRLineRepository(db)


def get_pr_service(
    db: Session = Depends(get_db),
) -> PRService:
    return PRService(
        db=db,
        pr_repo=PurchaseRequestRepository(db),
        line_repo=PRLineRepository(db),
        sequence_service=PurchaseSequenceService(db),
    )


def get_po_repo(
    db: Session = Depends(get_db),
) -> PurchaseOrderRepository:
    return PurchaseOrderRepository(db)


def get_po_line_repo(
    db: Session = Depends(get_db),
) -> POLineRepository:
    return POLineRepository(db)


def get_po_charge_repo(
    db: Session = Depends(get_db),
) -> POAdditionalChargeRepository:
    return POAdditionalChargeRepository(db)


def get_po_amendment_repo(
    db: Session = Depends(get_db),
) -> POAmendmentRepository:
    return POAmendmentRepository(db)


def get_po_service(
    db: Session = Depends(get_db),
) -> POService:
    return POService(
        db=db,
        po_repo=PurchaseOrderRepository(db),
        line_repo=POLineRepository(db),
        charge_repo=POAdditionalChargeRepository(db),
        amendment_repo=POAmendmentRepository(db),
        sequence_service=PurchaseSequenceService(db),
    )


def get_gr_repo(
    db: Session = Depends(get_db),
) -> GoodsReceiptRepository:
    return GoodsReceiptRepository(db)


def get_gr_line_repo(
    db: Session = Depends(get_db),
) -> GRLineRepository:
    return GRLineRepository(db)


def get_gr_service(
    db: Session = Depends(get_db),
) -> GRService:
    from modules.purchase.services.cost_service import CostService
    from modules.purchase.services.po_service import POService
    from modules.purchase.services.supplier_rating_service import SupplierRatingService

    po_svc = POService(
        db=db,
        po_repo=PurchaseOrderRepository(db),
        line_repo=POLineRepository(db),
        charge_repo=POAdditionalChargeRepository(db),
        amendment_repo=POAmendmentRepository(db),
        sequence_service=PurchaseSequenceService(db),
    )
    rating_svc = SupplierRatingService(db=db)
    cost_svc = CostService(
        db=db,
        po_repo=PurchaseOrderRepository(db),
        po_line_repo=POLineRepository(db),
        po_charge_repo=POAdditionalChargeRepository(db),
        gr_repo=GoodsReceiptRepository(db),
        gr_line_repo=GRLineRepository(db),
        policy_repo=PurchasePolicyRepository(db),
    )

    return GRService(
        db=db,
        gr_repo=GoodsReceiptRepository(db),
        line_repo=GRLineRepository(db),
        po_repo=PurchaseOrderRepository(db),
        po_line_repo=POLineRepository(db),
        sequence_service=PurchaseSequenceService(db),
        po_service=po_svc,
        rating_service=rating_svc,
        cost_service=cost_svc,
    )


def get_rma_service(
    db: Session = Depends(get_db),
) -> RMAService:
    return RMAService(
        db=db,
        rma_repo=VendorReturnRepository(db),
        line_repo=ReturnLineRepository(db),
        gr_repo=GoodsReceiptRepository(db),
        gr_line_repo=GRLineRepository(db),
        sequence_service=PurchaseSequenceService(db),
    )


def get_cost_service(
    db: Session = Depends(get_db),
) -> CostService:
    return CostService(
        db=db,
        po_repo=PurchaseOrderRepository(db),
        po_line_repo=POLineRepository(db),
        po_charge_repo=POAdditionalChargeRepository(db),
        gr_repo=GoodsReceiptRepository(db),
        gr_line_repo=GRLineRepository(db),
        policy_repo=PurchasePolicyRepository(db),
    )


def get_report_service(
    db: Session = Depends(get_db),
) -> ReportService:
    return ReportService(db=db)


def get_kpi_service(
    db: Session = Depends(get_db),
) -> KPIService:
    return KPIService(db=db)


def get_report_export_service() -> ReportExportService:
    return ReportExportService()


def get_supplier_import_service(
    db: Session = Depends(get_db),
) -> SupplierImportService:
    supplier_repo = SupplierRepository(db)
    supplier_svc = SupplierService(
        db=db,
        supplier_repo=supplier_repo,
        contact_repo=SupplierContactRepository(db),
        address_repo=SupplierAddressRepository(db),
    )
    return SupplierImportService(
        db=db,
        supplier_service=supplier_svc,
        supplier_repo=supplier_repo,
    )

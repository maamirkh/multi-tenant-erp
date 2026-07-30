"""Purchase module ORM models.

All models are imported here to ensure Alembic auto-discovery works correctly
when running ``alembic revision --autogenerate``.

Import order follows dependency order (parent before child tables).
"""

from modules.purchase.models.approval import (
    ApprovalDelegate,
    ApprovalLevel,
    ApprovalMatrix,
    ApprovalRecord,
    MatrixRule,
)
from modules.purchase.models.cost import PurchaseCostEntry
from modules.purchase.models.feature_flag import PurchaseFeatureFlag
from modules.purchase.models.goods_receipt import GoodsReceipt, GRLine
from modules.purchase.models.policy import PurchasePolicy, PurchaseSequence
from modules.purchase.models.purchase_order import (
    POAdditionalCharge,
    POAmendment,
    POLine,
    PurchaseOrder,
)
from modules.purchase.models.purchase_request import PRLine, PurchaseRequest
from modules.purchase.models.supplier import (
    PaymentTerms,
    PurchaseReasonCode,
    Supplier,
    SupplierAddress,
    SupplierCategory,
    SupplierContact,
)
from modules.purchase.models.supplier_enrichment import (
    BankDetails,
    CreditLimit,
    SupplierDocument,
    SupplierLeadTime,
    SupplierRating,
)
from modules.purchase.models.vendor_return import ReturnLine, VendorReturn

__all__ = [
    "ApprovalDelegate",
    "ApprovalLevel",
    "ApprovalMatrix",
    "ApprovalRecord",
    "BankDetails",
    "CreditLimit",
    "GoodsReceipt",
    "GRLine",
    "MatrixRule",
    "POAdditionalCharge",
    "POAmendment",
    "POLine",
    "PRLine",
    "PurchaseOrder",
    "PurchaseRequest",
    "PaymentTerms",
    "PurchaseFeatureFlag",
    "PurchasePolicy",
    "PurchaseReasonCode",
    "PurchaseSequence",
    "Supplier",
    "SupplierAddress",
    "SupplierCategory",
    "SupplierContact",
    "SupplierDocument",
    "SupplierLeadTime",
    "SupplierRating",
    "VendorReturn",
    "ReturnLine",
    "PurchaseCostEntry",
]

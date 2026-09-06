"""Sales module ORM models.

All models are imported here to ensure Alembic auto-discovery works correctly
when running ``alembic revision --autogenerate``.

Import order follows dependency order (parent before child tables).
"""

from modules.sales.models.approval import (
    SalesApprovalMatrix,
    SalesApprovalRecord,
    SalesMatrixRule,
)
from modules.sales.models.customer import (
    Customer,
    CustomerAddress,
    CustomerBankDetail,
    CustomerContact,
    CustomerNote,
)
from modules.sales.models.delivery import DeliveryNote, DeliveryNoteLine
from modules.sales.models.feature_flag import SalesFeatureFlag
from modules.sales.models.invoice import InvoiceCharge, InvoiceLine, SalesInvoice
from modules.sales.models.master import (
    CustomerCategory,
    CustomerGroup,
    SalesConfiguration,
    SalesPaymentTerm,
    SalesReasonCode,
    SalesSequence,
)
from modules.sales.models.order import OrderLine, SalesOrder
from modules.sales.models.pricing import (
    CustomerSpecificPrice,
    DiscountRule,
    PriceEntry,
    PriceList,
)
from modules.sales.models.quotation import (
    QuotationLine,
    QuotationRevision,
    SalesQuotation,
)
from modules.sales.models.sales_return import ReturnLine, SalesReturn

__all__ = [
    "Customer",
    "CustomerAddress",
    "CustomerBankDetail",
    "CustomerCategory",
    "CustomerContact",
    "CustomerGroup",
    "CustomerNote",
    "CustomerSpecificPrice",
    "DiscountRule",
    "PriceEntry",
    "PriceList",
    "QuotationLine",
    "QuotationRevision",
    "SalesConfiguration",
    "SalesFeatureFlag",
    "SalesPaymentTerm",
    "SalesQuotation",
    "SalesReasonCode",
    "SalesSequence",
    "SalesOrder",
    "OrderLine",
    "SalesApprovalMatrix",
    "SalesApprovalRecord",
    "SalesMatrixRule",
    "DeliveryNote",
    "DeliveryNoteLine",
    "SalesInvoice",
    "InvoiceLine",
    "InvoiceCharge",
    "SalesReturn",
    "ReturnLine",
]

"""FastAPI dependency injection functions for the Sales module.

All DI factories are synchronous, matching the sync ``Session`` / ``get_db``
pattern used throughout the backend.

Spec ref: specs/007-sales-management/plan.md — Application Layer
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from core.database.session import get_db
from modules.sales.repositories.customer import (
    CustomerAddressRepository,
    CustomerBankDetailRepository,
    CustomerContactRepository,
    CustomerNoteRepository,
    CustomerRepository,
)
from modules.sales.repositories.feature_flag_repository import (
    SalesFeatureFlagRepository,
)
from modules.sales.repositories.master import (
    CustomerCategoryRepository,
    CustomerGroupRepository,
    SalesConfigurationRepository,
    SalesPaymentTermRepository,
    SalesReasonCodeRepository,
)
from modules.sales.repositories.pricing import (
    CustomerSpecificPriceRepository,
    DiscountRuleRepository,
    PriceEntryRepository,
    PriceListRepository,
)
from modules.sales.repositories.quotation import (
    QuotationLineRepository,
    QuotationRevisionRepository,
    SalesQuotationRepository,
)
from modules.sales.services.approval_service import ApprovalService
from modules.sales.services.credit_check_service import CreditCheckService
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
from modules.sales.services.pricing_service import (
    CustomerSpecificPriceService,
    DiscountRuleService,
    DiscountService,
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
from modules.sales.services.sequence_service import SalesSequenceService

# ---------------------------------------------------------------------------
# Repository factories
# ---------------------------------------------------------------------------


def get_sales_feature_flag_repo(
    db: Session = Depends(get_db),
) -> SalesFeatureFlagRepository:
    return SalesFeatureFlagRepository(db)


def get_customer_category_repo(
    db: Session = Depends(get_db),
) -> CustomerCategoryRepository:
    return CustomerCategoryRepository(db)


def get_customer_group_repo(
    db: Session = Depends(get_db),
) -> CustomerGroupRepository:
    return CustomerGroupRepository(db)


def get_sales_payment_term_repo(
    db: Session = Depends(get_db),
) -> SalesPaymentTermRepository:
    return SalesPaymentTermRepository(db)


def get_sales_reason_code_repo(
    db: Session = Depends(get_db),
) -> SalesReasonCodeRepository:
    return SalesReasonCodeRepository(db)


def get_sales_configuration_repo(
    db: Session = Depends(get_db),
) -> SalesConfigurationRepository:
    return SalesConfigurationRepository(db)


# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------


def get_sales_feature_flag_service(
    db: Session = Depends(get_db),
) -> SalesFeatureFlagService:
    return SalesFeatureFlagService(
        db=db,
        flag_repo=SalesFeatureFlagRepository(db),
    )


def get_customer_category_service(
    db: Session = Depends(get_db),
) -> CustomerCategoryService:
    return CustomerCategoryService(
        db=db,
        category_repo=CustomerCategoryRepository(db),
    )


def get_customer_group_service(
    db: Session = Depends(get_db),
) -> CustomerGroupService:
    return CustomerGroupService(
        db=db,
        group_repo=CustomerGroupRepository(db),
    )


def get_sales_payment_term_service(
    db: Session = Depends(get_db),
) -> SalesPaymentTermService:
    return SalesPaymentTermService(
        db=db,
        terms_repo=SalesPaymentTermRepository(db),
    )


def get_sales_reason_code_service(
    db: Session = Depends(get_db),
) -> SalesReasonCodeService:
    return SalesReasonCodeService(
        db=db,
        reason_repo=SalesReasonCodeRepository(db),
    )


def get_sales_configuration_service(
    db: Session = Depends(get_db),
) -> SalesConfigurationService:
    return SalesConfigurationService(
        db=db,
        config_repo=SalesConfigurationRepository(db),
    )


def get_sales_sequence_service(
    db: Session = Depends(get_db),
) -> SalesSequenceService:
    return SalesSequenceService(db=db)


# ---------------------------------------------------------------------------
# Customer Phase 1 — Repository factories
# ---------------------------------------------------------------------------


def get_customer_repo(
    db: Session = Depends(get_db),
) -> CustomerRepository:
    return CustomerRepository(db)


def get_customer_contact_repo(
    db: Session = Depends(get_db),
) -> CustomerContactRepository:
    return CustomerContactRepository(db)


def get_customer_address_repo(
    db: Session = Depends(get_db),
) -> CustomerAddressRepository:
    return CustomerAddressRepository(db)


def get_customer_bank_detail_repo(
    db: Session = Depends(get_db),
) -> CustomerBankDetailRepository:
    return CustomerBankDetailRepository(db)


def get_customer_note_repo(
    db: Session = Depends(get_db),
) -> CustomerNoteRepository:
    return CustomerNoteRepository(db)


# ---------------------------------------------------------------------------
# Customer Phase 1 — Service factories
# ---------------------------------------------------------------------------


def get_customer_service(
    db: Session = Depends(get_db),
) -> CustomerService:
    return CustomerService(
        db=db,
        customer_repo=CustomerRepository(db),
        contact_repo=CustomerContactRepository(db),
        address_repo=CustomerAddressRepository(db),
        sequence_service=SalesSequenceService(db=db),
    )


def get_customer_contact_service(
    db: Session = Depends(get_db),
) -> CustomerContactService:
    return CustomerContactService(
        db=db,
        contact_repo=CustomerContactRepository(db),
    )


def get_customer_address_service(
    db: Session = Depends(get_db),
) -> CustomerAddressService:
    return CustomerAddressService(
        db=db,
        address_repo=CustomerAddressRepository(db),
    )


def get_customer_bank_detail_service(
    db: Session = Depends(get_db),
) -> CustomerBankDetailService:
    return CustomerBankDetailService(
        db=db,
        bank_repo=CustomerBankDetailRepository(db),
    )


def get_customer_note_service(
    db: Session = Depends(get_db),
) -> CustomerNoteService:
    return CustomerNoteService(
        db=db,
        note_repo=CustomerNoteRepository(db),
    )


def get_customer_import_service(
    db: Session = Depends(get_db),
) -> CustomerImportService:
    return CustomerImportService(
        db=db,
        customer_service=CustomerService(
            db=db,
            customer_repo=CustomerRepository(db),
            contact_repo=CustomerContactRepository(db),
            address_repo=CustomerAddressRepository(db),
            sequence_service=SalesSequenceService(db=db),
        ),
        customer_repo=CustomerRepository(db),
        category_repo=CustomerCategoryRepository(db),
        group_repo=CustomerGroupRepository(db),
        payment_term_repo=SalesPaymentTermRepository(db),
    )


def get_customer_export_service(
    db: Session = Depends(get_db),
) -> CustomerExportService:
    return CustomerExportService(
        db=db,
        customer_repo=CustomerRepository(db),
    )


# ---------------------------------------------------------------------------
# Pricing Phase 2 — Repository factories
# ---------------------------------------------------------------------------


def get_price_list_repo(db: Session = Depends(get_db)) -> PriceListRepository:
    return PriceListRepository(db)


def get_price_entry_repo(db: Session = Depends(get_db)) -> PriceEntryRepository:
    return PriceEntryRepository(db)


def get_customer_specific_price_repo(
    db: Session = Depends(get_db),
) -> CustomerSpecificPriceRepository:
    return CustomerSpecificPriceRepository(db)


def get_discount_rule_repo(db: Session = Depends(get_db)) -> DiscountRuleRepository:
    return DiscountRuleRepository(db)


# ---------------------------------------------------------------------------
# Pricing Phase 2 — Service factories
# ---------------------------------------------------------------------------


def get_price_list_service(db: Session = Depends(get_db)) -> PriceListService:
    return PriceListService(
        db=db,
        price_list_repo=PriceListRepository(db),
        entry_repo=PriceEntryRepository(db),
    )


def get_pricing_service(db: Session = Depends(get_db)) -> PricingService:
    return PricingService(
        db=db,
        price_list_repo=PriceListRepository(db),
        entry_repo=PriceEntryRepository(db),
        specific_repo=CustomerSpecificPriceRepository(db),
    )


def get_discount_service(db: Session = Depends(get_db)) -> DiscountService:
    return DiscountService(
        db=db,
        discount_repo=DiscountRuleRepository(db),
    )


def get_margin_guard_service() -> MarginGuardService:
    return MarginGuardService()


def get_customer_specific_price_service(
    db: Session = Depends(get_db),
) -> CustomerSpecificPriceService:
    return CustomerSpecificPriceService(
        db=db,
        repo=CustomerSpecificPriceRepository(db),
    )


def get_discount_rule_service(db: Session = Depends(get_db)) -> DiscountRuleService:
    return DiscountRuleService(
        db=db,
        repo=DiscountRuleRepository(db),
    )


# ---------------------------------------------------------------------------
# Quotation Phase 3 — Repository factories
# ---------------------------------------------------------------------------


def get_sales_quotation_repo(
    db: Session = Depends(get_db),
) -> SalesQuotationRepository:
    return SalesQuotationRepository(db)


def get_quotation_line_repo(
    db: Session = Depends(get_db),
) -> QuotationLineRepository:
    return QuotationLineRepository(db)


def get_quotation_revision_repo(
    db: Session = Depends(get_db),
) -> QuotationRevisionRepository:
    return QuotationRevisionRepository(db)


# ---------------------------------------------------------------------------
# Quotation Phase 3 — Service factories
# ---------------------------------------------------------------------------


def get_quotation_service(db: Session = Depends(get_db)) -> QuotationService:
    return QuotationService(db=db)


def get_quotation_line_service(
    db: Session = Depends(get_db),
) -> QuotationLineService:
    return QuotationLineService(db=db)


# ---------------------------------------------------------------------------
# Order Phase 4 — Service factories
# ---------------------------------------------------------------------------


def get_order_service(db: Session = Depends(get_db)) -> OrderService:
    return OrderService(db=db)


def get_order_line_service(db: Session = Depends(get_db)) -> OrderLineService:
    return OrderLineService(db=db)


def get_approval_service(db: Session = Depends(get_db)) -> ApprovalService:
    return ApprovalService(db=db)


def get_credit_check_service(db: Session = Depends(get_db)) -> CreditCheckService:
    return CreditCheckService(db=db)


# ---------------------------------------------------------------------------
# Delivery Phase 5 — Service factories
# ---------------------------------------------------------------------------


def get_delivery_service(db: Session = Depends(get_db)) -> DeliveryService:
    return DeliveryService(db=db)


# ---------------------------------------------------------------------------
# Invoice Phase 6 — Service factories
# ---------------------------------------------------------------------------


def get_invoice_service(db: Session = Depends(get_db)) -> InvoiceService:
    return InvoiceService(db=db)


# ---------------------------------------------------------------------------
# Return Phase 7 — Service factories
# ---------------------------------------------------------------------------


def get_return_service(db: Session = Depends(get_db)) -> ReturnService:
    return ReturnService(db=db)


# ---------------------------------------------------------------------------
# Reporting Phase 8 — Service factories
# ---------------------------------------------------------------------------


def get_report_service(db: Session = Depends(get_db)) -> ReportService:
    return ReportService(db=db)


def get_kpi_service(db: Session = Depends(get_db)) -> KPIService:
    return KPIService(db=db)


def get_report_export_service() -> ReportExportService:
    return ReportExportService()

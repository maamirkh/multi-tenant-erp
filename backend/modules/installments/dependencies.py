"""FastAPI dependency injection functions for the Installments module.

All DI factories are synchronous, matching the sync ``Session`` /
``get_db`` pattern used throughout the backend. Extended incrementally in
every later phase as new repositories/services are added, mirroring
``modules/crm/dependencies.py``'s own incremental-growth convention.

Spec ref: specs/010-installments/plan.md §2, §12.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from core.database.session import get_db
from modules.accounting.dependencies import get_ar_service
from modules.accounting.services.ar_service import AccountsReceivableService
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.configuration import (
    InstallmentConfigurationRepository,
)
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.feature_flag import (
    InstallmentsFeatureFlagRepository,
)
from modules.installments.repositories.plan_template import (
    InstallmentPlanTemplateRepository,
)
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.repositories.sequence import InstallmentSequenceRepository
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)
from modules.installments.services.audit_service import InstallmentAuditService
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
from modules.installments.services.plan_template_service import (
    InstallmentPlanTemplateService,
)
from modules.installments.services.quote_service import InstallmentQuoteService
from modules.installments.services.sales_read_gateway import (
    SalesCustomerReadGateway,
    SalesInvoiceReadGateway,
)

# ---------------------------------------------------------------------------
# Repository factories
# ---------------------------------------------------------------------------


def get_installment_configuration_repo(
    db: Session = Depends(get_db),
) -> InstallmentConfigurationRepository:
    return InstallmentConfigurationRepository(db)


def get_installment_plan_template_repo(
    db: Session = Depends(get_db),
) -> InstallmentPlanTemplateRepository:
    return InstallmentPlanTemplateRepository(db)


def get_installments_feature_flag_repo(
    db: Session = Depends(get_db),
) -> InstallmentsFeatureFlagRepository:
    return InstallmentsFeatureFlagRepository(db)


def get_installment_audit_log_repo(
    db: Session = Depends(get_db),
) -> InstallmentAuditLogRepository:
    return InstallmentAuditLogRepository(db)


def get_installment_contract_repo(
    db: Session = Depends(get_db),
) -> InstallmentContractRepository:
    return InstallmentContractRepository(db)


def get_installment_sequence_repo(
    db: Session = Depends(get_db),
) -> InstallmentSequenceRepository:
    return InstallmentSequenceRepository(db)


def get_installment_schedule_repo(
    db: Session = Depends(get_db),
) -> InstallmentScheduleRepository:
    return InstallmentScheduleRepository(db)


# ---------------------------------------------------------------------------
# Cross-module read-only gateway factories
# ---------------------------------------------------------------------------


def get_sales_invoice_read_gateway(
    db: Session = Depends(get_db),
) -> SalesInvoiceReadGateway:
    return SalesInvoiceReadGateway(db)


def get_sales_customer_read_gateway(
    db: Session = Depends(get_db),
) -> SalesCustomerReadGateway:
    return SalesCustomerReadGateway(db)


def get_accounting_integration_gateway(
    ar_service: AccountsReceivableService = Depends(get_ar_service),
) -> AccountingIntegrationGateway:
    """Reuses Accounting's own ``get_ar_service`` DI factory unchanged,
    never a new Accounting endpoint or a cached financial value —
    mirrors ``modules.crm.dependencies.get_customer_360_service``'s
    identical convention."""
    return AccountingIntegrationGateway(ar_service=ar_service)


# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------


def get_installment_configuration_service(
    repo: InstallmentConfigurationRepository = Depends(
        get_installment_configuration_repo
    ),
) -> InstallmentConfigurationService:
    return InstallmentConfigurationService(repo=repo)


def get_installment_plan_template_service(
    repo: InstallmentPlanTemplateRepository = Depends(
        get_installment_plan_template_repo
    ),
) -> InstallmentPlanTemplateService:
    return InstallmentPlanTemplateService(repo=repo)


def get_installments_feature_flag_service(
    repo: InstallmentsFeatureFlagRepository = Depends(
        get_installments_feature_flag_repo
    ),
) -> InstallmentsFeatureFlagService:
    return InstallmentsFeatureFlagService(flag_repo=repo)


def get_installment_audit_service(
    db: Session = Depends(get_db),
    repo: InstallmentAuditLogRepository = Depends(get_installment_audit_log_repo),
) -> InstallmentAuditService:
    return InstallmentAuditService(db=db, audit_repo=repo)


def get_installment_eligibility_service(
    invoice_gateway: SalesInvoiceReadGateway = Depends(get_sales_invoice_read_gateway),
    customer_gateway: SalesCustomerReadGateway = Depends(
        get_sales_customer_read_gateway
    ),
    ar_gateway: AccountingIntegrationGateway = Depends(
        get_accounting_integration_gateway
    ),
) -> InstallmentEligibilityService:
    return InstallmentEligibilityService(
        invoice_gateway=invoice_gateway,
        customer_gateway=customer_gateway,
        ar_gateway=ar_gateway,
    )


def get_installment_contract_service(
    repo: InstallmentContractRepository = Depends(get_installment_contract_repo),
    sequence_repo: InstallmentSequenceRepository = Depends(
        get_installment_sequence_repo
    ),
    eligibility_service: InstallmentEligibilityService = Depends(
        get_installment_eligibility_service
    ),
    accounting_gateway: AccountingIntegrationGateway = Depends(
        get_accounting_integration_gateway
    ),
) -> InstallmentContractService:
    return InstallmentContractService(
        repo=repo,
        sequence_repo=sequence_repo,
        eligibility_service=eligibility_service,
        accounting_gateway=accounting_gateway,
    )


def get_installment_quote_service(
    eligibility_service: InstallmentEligibilityService = Depends(
        get_installment_eligibility_service
    ),
    invoice_gateway: SalesInvoiceReadGateway = Depends(get_sales_invoice_read_gateway),
    configuration_service: InstallmentConfigurationService = Depends(
        get_installment_configuration_service
    ),
) -> InstallmentQuoteService:
    return InstallmentQuoteService(
        eligibility_service=eligibility_service,
        invoice_gateway=invoice_gateway,
        configuration_service=configuration_service,
    )

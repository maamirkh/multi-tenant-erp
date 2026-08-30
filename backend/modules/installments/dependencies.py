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
from core.events.outbox import EventOutboxRepository
from modules.accounting.dependencies import (
    get_allocation_engine,
    get_ar_service,
    get_payment_service,
)
from modules.accounting.services.allocation_engine import AllocationEngine
from modules.accounting.services.ar_service import AccountsReceivableService
from modules.accounting.services.payment_service import PaymentService
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.configuration import (
    InstallmentConfigurationRepository,
)
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.feature_flag import (
    InstallmentsFeatureFlagRepository,
)
from modules.installments.repositories.late_charge import (
    InstallmentLateChargeRepository,
)
from modules.installments.repositories.plan_template import (
    InstallmentPlanTemplateRepository,
)
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.repositories.sequence import InstallmentSequenceRepository
from modules.installments.services.access_policy import InstallmentAccessPolicy
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.collection_service import (
    InstallmentCollectionService,
)
from modules.installments.services.configuration_service import (
    InstallmentConfigurationService,
)
from modules.installments.services.contract_service import InstallmentContractService
from modules.installments.services.delinquency_service import (
    InstallmentDelinquencyService,
)
from modules.installments.services.eligibility_service import (
    InstallmentEligibilityService,
)
from modules.installments.services.feature_flag_service import (
    InstallmentsFeatureFlagService,
)
from modules.installments.services.idempotency_service import (
    InstallmentIdempotencyService,
)
from modules.installments.services.outstanding_service import (
    InstallmentOutstandingService,
)
from modules.installments.services.plan_template_service import (
    InstallmentPlanTemplateService,
)
from modules.installments.services.quote_service import InstallmentQuoteService
from modules.installments.services.rescheduling_service import (
    InstallmentReschedulingService,
)
from modules.installments.services.sales_read_gateway import (
    SalesCustomerReadGateway,
    SalesInvoiceReadGateway,
)
from modules.installments.services.settlement_service import (
    InstallmentSettlementService,
)
from modules.platform_admin.repositories.override_repository import (
    OverrideRepository,
)
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)
from modules.platform_admin.services.override_service import OverrideService
from modules.platform_admin.services.platform_audit_service import (
    PlatformAuditService,
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


def get_installment_allocation_reference_repo(
    db: Session = Depends(get_db),
) -> InstallmentAllocationReferenceRepository:
    return InstallmentAllocationReferenceRepository(db)


def get_installment_late_charge_repo(
    db: Session = Depends(get_db),
) -> InstallmentLateChargeRepository:
    return InstallmentLateChargeRepository(db)


def get_event_outbox_repo(
    db: Session = Depends(get_db),
) -> EventOutboxRepository:
    return EventOutboxRepository(db)


def get_installment_idempotency_service(
    db: Session = Depends(get_db),
) -> InstallmentIdempotencyService:
    return InstallmentIdempotencyService(db)


def get_installment_access_policy(
    db: Session = Depends(get_db),
) -> InstallmentAccessPolicy:
    """Mirrors ``require_capability_entitled``'s own
    ``PlatformEntitlementService`` construction (T188, plan.md §15.2) —
    same override/plan/subscription resolution chain, just invoked from
    inside each Installments service method instead of a router-mount
    dependency. Resolved fresh on every call (FR-9A-170); no
    request-scoped memoisation here (unlike ``require_capability_entitled``)
    since each request reaches at most one gated service method."""
    override_service = OverrideService(
        db=db,
        repo=OverrideRepository(db),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    )
    entitlement_service = PlatformEntitlementService(
        db=db,
        plan_repo=PlanRepository(db),
        subscription_repo=SubscriptionRepository(db),
        override_checker=override_service,
    )
    return InstallmentAccessPolicy(entitlement_service=entitlement_service)


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
    payment_service: PaymentService = Depends(get_payment_service),
    allocation_engine: AllocationEngine = Depends(get_allocation_engine),
) -> AccountingIntegrationGateway:
    """Reuses Accounting's own ``get_ar_service``/``get_payment_service``/
    ``get_allocation_engine`` DI factories unchanged, never a new
    Accounting endpoint or a cached financial value — mirrors
    ``modules.crm.dependencies.get_customer_360_service``'s identical
    convention. All three share the same request-scoped ``Session``
    (each factory ultimately depends on ``get_db``), which is what
    makes the staged/finalize atomicity across them possible."""
    return AccountingIntegrationGateway(
        ar_service=ar_service,
        payment_service=payment_service,
        allocation_engine=allocation_engine,
    )


# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------


def get_installment_outstanding_service(
    schedule_repo: InstallmentScheduleRepository = Depends(
        get_installment_schedule_repo
    ),
    accounting_gateway: AccountingIntegrationGateway = Depends(
        get_accounting_integration_gateway
    ),
    allocation_ref_repo: InstallmentAllocationReferenceRepository = Depends(
        get_installment_allocation_reference_repo
    ),
    late_charge_repo: InstallmentLateChargeRepository = Depends(
        get_installment_late_charge_repo
    ),
) -> InstallmentOutstandingService:
    return InstallmentOutstandingService(
        schedule_repo=schedule_repo,
        accounting_gateway=accounting_gateway,
        allocation_ref_repo=allocation_ref_repo,
        late_charge_repo=late_charge_repo,
    )


def get_installment_configuration_service(
    repo: InstallmentConfigurationRepository = Depends(
        get_installment_configuration_repo
    ),
    access_policy: InstallmentAccessPolicy = Depends(get_installment_access_policy),
) -> InstallmentConfigurationService:
    return InstallmentConfigurationService(repo=repo, access_policy=access_policy)


def get_installment_plan_template_service(
    repo: InstallmentPlanTemplateRepository = Depends(
        get_installment_plan_template_repo
    ),
    access_policy: InstallmentAccessPolicy = Depends(get_installment_access_policy),
) -> InstallmentPlanTemplateService:
    return InstallmentPlanTemplateService(repo=repo, access_policy=access_policy)


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
    access_policy: InstallmentAccessPolicy = Depends(get_installment_access_policy),
) -> InstallmentEligibilityService:
    return InstallmentEligibilityService(
        invoice_gateway=invoice_gateway,
        customer_gateway=customer_gateway,
        ar_gateway=ar_gateway,
        access_policy=access_policy,
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
    configuration_service: InstallmentConfigurationService = Depends(
        get_installment_configuration_service
    ),
    audit_service: InstallmentAuditService = Depends(get_installment_audit_service),
    schedule_repo: InstallmentScheduleRepository = Depends(
        get_installment_schedule_repo
    ),
    idempotency_service: InstallmentIdempotencyService = Depends(
        get_installment_idempotency_service
    ),
    outbox_repo: EventOutboxRepository = Depends(get_event_outbox_repo),
    allocation_ref_repo: InstallmentAllocationReferenceRepository = Depends(
        get_installment_allocation_reference_repo
    ),
    access_policy: InstallmentAccessPolicy = Depends(get_installment_access_policy),
) -> InstallmentContractService:
    return InstallmentContractService(
        repo=repo,
        sequence_repo=sequence_repo,
        eligibility_service=eligibility_service,
        accounting_gateway=accounting_gateway,
        configuration_service=configuration_service,
        audit_service=audit_service,
        schedule_repo=schedule_repo,
        idempotency_service=idempotency_service,
        outbox_repo=outbox_repo,
        allocation_ref_repo=allocation_ref_repo,
        access_policy=access_policy,
    )


def get_installment_collection_service(
    db: Session = Depends(get_db),
    contract_repo: InstallmentContractRepository = Depends(
        get_installment_contract_repo
    ),
    schedule_repo: InstallmentScheduleRepository = Depends(
        get_installment_schedule_repo
    ),
    allocation_ref_repo: InstallmentAllocationReferenceRepository = Depends(
        get_installment_allocation_reference_repo
    ),
    accounting_gateway: AccountingIntegrationGateway = Depends(
        get_accounting_integration_gateway
    ),
    outstanding_service: InstallmentOutstandingService = Depends(
        get_installment_outstanding_service
    ),
    idempotency_service: InstallmentIdempotencyService = Depends(
        get_installment_idempotency_service
    ),
    audit_service: InstallmentAuditService = Depends(get_installment_audit_service),
    outbox_repo: EventOutboxRepository = Depends(get_event_outbox_repo),
    contract_service: InstallmentContractService = Depends(
        get_installment_contract_service
    ),
    late_charge_repo: InstallmentLateChargeRepository = Depends(
        get_installment_late_charge_repo
    ),
    access_policy: InstallmentAccessPolicy = Depends(get_installment_access_policy),
) -> InstallmentCollectionService:
    return InstallmentCollectionService(
        db=db,
        contract_repo=contract_repo,
        schedule_repo=schedule_repo,
        allocation_ref_repo=allocation_ref_repo,
        accounting_gateway=accounting_gateway,
        outstanding_service=outstanding_service,
        idempotency_service=idempotency_service,
        audit_service=audit_service,
        outbox_repo=outbox_repo,
        contract_service=contract_service,
        late_charge_repo=late_charge_repo,
        access_policy=access_policy,
    )


def get_installment_delinquency_service(
    db: Session = Depends(get_db),
    contract_repo: InstallmentContractRepository = Depends(
        get_installment_contract_repo
    ),
    schedule_repo: InstallmentScheduleRepository = Depends(
        get_installment_schedule_repo
    ),
    allocation_ref_repo: InstallmentAllocationReferenceRepository = Depends(
        get_installment_allocation_reference_repo
    ),
    late_charge_repo: InstallmentLateChargeRepository = Depends(
        get_installment_late_charge_repo
    ),
    accounting_gateway: AccountingIntegrationGateway = Depends(
        get_accounting_integration_gateway
    ),
    audit_service: InstallmentAuditService = Depends(get_installment_audit_service),
    outbox_repo: EventOutboxRepository = Depends(get_event_outbox_repo),
    access_policy: InstallmentAccessPolicy = Depends(get_installment_access_policy),
) -> InstallmentDelinquencyService:
    return InstallmentDelinquencyService(
        db=db,
        contract_repo=contract_repo,
        schedule_repo=schedule_repo,
        allocation_ref_repo=allocation_ref_repo,
        late_charge_repo=late_charge_repo,
        accounting_gateway=accounting_gateway,
        audit_service=audit_service,
        outbox_repo=outbox_repo,
        access_policy=access_policy,
    )


def get_installment_settlement_service(
    db: Session = Depends(get_db),
    contract_repo: InstallmentContractRepository = Depends(
        get_installment_contract_repo
    ),
    outstanding_service: InstallmentOutstandingService = Depends(
        get_installment_outstanding_service
    ),
    collection_service: InstallmentCollectionService = Depends(
        get_installment_collection_service
    ),
    configuration_service: InstallmentConfigurationService = Depends(
        get_installment_configuration_service
    ),
    idempotency_service: InstallmentIdempotencyService = Depends(
        get_installment_idempotency_service
    ),
    audit_service: InstallmentAuditService = Depends(get_installment_audit_service),
    access_policy: InstallmentAccessPolicy = Depends(get_installment_access_policy),
) -> InstallmentSettlementService:
    return InstallmentSettlementService(
        db=db,
        contract_repo=contract_repo,
        outstanding_service=outstanding_service,
        collection_service=collection_service,
        configuration_service=configuration_service,
        idempotency_service=idempotency_service,
        audit_service=audit_service,
        access_policy=access_policy,
    )


def get_installment_quote_service(
    eligibility_service: InstallmentEligibilityService = Depends(
        get_installment_eligibility_service
    ),
    invoice_gateway: SalesInvoiceReadGateway = Depends(get_sales_invoice_read_gateway),
    configuration_service: InstallmentConfigurationService = Depends(
        get_installment_configuration_service
    ),
    access_policy: InstallmentAccessPolicy = Depends(get_installment_access_policy),
) -> InstallmentQuoteService:
    return InstallmentQuoteService(
        eligibility_service=eligibility_service,
        invoice_gateway=invoice_gateway,
        configuration_service=configuration_service,
        access_policy=access_policy,
    )


def get_installment_rescheduling_service(
    db: Session = Depends(get_db),
    contract_repo: InstallmentContractRepository = Depends(
        get_installment_contract_repo
    ),
    schedule_repo: InstallmentScheduleRepository = Depends(
        get_installment_schedule_repo
    ),
    allocation_ref_repo: InstallmentAllocationReferenceRepository = Depends(
        get_installment_allocation_reference_repo
    ),
    configuration_service: InstallmentConfigurationService = Depends(
        get_installment_configuration_service
    ),
    idempotency_service: InstallmentIdempotencyService = Depends(
        get_installment_idempotency_service
    ),
    audit_service: InstallmentAuditService = Depends(get_installment_audit_service),
    outbox_repo: EventOutboxRepository = Depends(get_event_outbox_repo),
    access_policy: InstallmentAccessPolicy = Depends(get_installment_access_policy),
) -> InstallmentReschedulingService:
    return InstallmentReschedulingService(
        db=db,
        contract_repo=contract_repo,
        schedule_repo=schedule_repo,
        allocation_ref_repo=allocation_ref_repo,
        configuration_service=configuration_service,
        idempotency_service=idempotency_service,
        audit_service=audit_service,
        outbox_repo=outbox_repo,
        access_policy=access_policy,
    )

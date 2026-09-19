"""``Customer360Service`` — the Customer 360 composite read model (spec
§20, plan.md §14, tasks.md T161-T164).

Section-level compound authorization: four independent section
evaluators, never an all-or-nothing gate (FR-RPT-111). Nothing is cached,
persisted, or blended — every call is a fresh composite read (NG2).

**Boundary (T161, T174)**: the base customer lookup calls Sales'
``CustomerService.get_by_id()`` — never ``CustomerRepository`` — so a
cross-tenant or nonexistent ``customer_id`` raises the platform's own
``NotFoundException`` (IDOR-safe: identical for both cases, no new
error-message-distinguishability risk, FR-RPT-271) directly from Sales,
with zero Reports-owned translation layer. This is the **only** privileged
lookup in this service — every other domain call below is independently
tenant-scoped by its own existing service method.

Order of checks in each section mirrors the base gate's own rationale
(T162): the cheaper/structural check runs first, so an unauthorized
request never triggers an unnecessary cross-module call — but the
*reason* reported for a failed section always reflects entitlement over
permission (an unentitled domain reports ``not_entitled`` even if the
caller would also lack the specific permission), matching FR-RPT-041's
priority and T168's own dedicated regression test.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from modules.accounting.dependencies import (
    build_allocation_engine,
    build_ar_service,
    build_payment_service,
)
from modules.accounting.exceptions import CustomerLedgerNotFoundError
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.crm.dependencies import get_opportunity_repository
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.late_charge import (
    InstallmentLateChargeRepository,
)
from modules.installments.repositories.plan_template import (
    InstallmentPlanTemplateRepository,
)
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)
from modules.installments.services.reporting_service import InstallmentReportingService
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)
from modules.reports.exceptions import ReportPermissionDeniedError
from modules.reports.registry.definitions import ReportDomain
from modules.reports.schemas.customer_360 import (
    AccountingArSection,
    CrmSection,
    Customer360Response,
    InstallmentsSection,
    OmittedSection,
    PresentAccountingArSection,
    PresentCrmSection,
    PresentInstallmentsSection,
    PresentSalesSection,
    SalesSection,
    UnavailableSection,
)
from modules.reports.schemas.sales import SalesSummaryFilter, SalesSummaryRow
from modules.reports.services.adapters.base import (
    ADAPTER_REGISTRY,
    PaginatedReportResult,
)
from modules.reports.services.installments_continuity_gate import (
    InstallmentsAccessState,
    InstallmentsServicingContinuityGate,
)
from modules.reports.services.permission_check import user_has_reports_permission
from modules.sales.dependencies import get_customer_service

#: Mirrors ``InstallmentsAdapter``'s own bound (largest realistic
#: live-obligation population for any tenant).
_INSTALLMENTS_POPULATION_BOUND = 50_000

_BASE_PERMISSION = "reports.customer_360.view"


def _build_entitlement_service(db: Session) -> PlatformEntitlementService:
    return PlatformEntitlementService(
        db=db,
        plan_repo=PlanRepository(db),
        subscription_repo=SubscriptionRepository(db),
    )


def _build_installments_reporting_service(db: Session) -> InstallmentReportingService:
    """Mirrors ``execution_service.py``/``dashboard_service.py``'s own
    local copy — kept separate rather than cross-imported, matching those
    files' own stated rationale."""
    gateway = AccountingIntegrationGateway(
        ar_service=build_ar_service(db),
        payment_service=build_payment_service(db),
        allocation_engine=build_allocation_engine(db),
    )
    return InstallmentReportingService(
        contract_repo=InstallmentContractRepository(db),
        schedule_repo=InstallmentScheduleRepository(db),
        allocation_ref_repo=InstallmentAllocationReferenceRepository(db),
        late_charge_repo=InstallmentLateChargeRepository(db),
        audit_repo=InstallmentAuditLogRepository(db),
        plan_template_repo=InstallmentPlanTemplateRepository(db),
        accounting_gateway=gateway,
        access_policy=None,
    )


def _domain_entitled(
    entitlement_service: PlatformEntitlementService,
    company_id: UUID,
    capability_key: str,
) -> bool:
    return entitlement_service.resolve_effective_entitlement(
        company_id=company_id, capability_key=capability_key
    ).available


def _permitted(
    db: Session,
    company_id: UUID,
    user_id: UUID | None,
    user_roles: list[str] | None,
    permission_code: str,
) -> bool:
    return user_has_reports_permission(
        db, company_id, user_id, permission_code, user_roles=user_roles
    )


def _sales_section(
    db: Session,
    entitlement_service: PlatformEntitlementService,
    company_id: UUID,
    user_id: UUID | None,
    user_roles: list[str] | None,
    customer_id: UUID,
) -> SalesSection:
    if not _domain_entitled(entitlement_service, company_id, "sales"):
        return OmittedSection(reason="not_entitled")
    if not _permitted(db, company_id, user_id, user_roles, "reports.sales.view"):
        return OmittedSection(reason="not_permitted")

    filters = SalesSummaryFilter(customer_id=str(customer_id))
    probe = ADAPTER_REGISTRY[ReportDomain.SALES].run(
        db, company_id, "sales.summary", filters, 1, 1, None, None
    )
    assert isinstance(probe, PaginatedReportResult)
    if probe.total == 0:
        return PresentSalesSection(total_revenue=Decimal("0"), invoice_count=0)
    full = ADAPTER_REGISTRY[ReportDomain.SALES].run(
        db, company_id, "sales.summary", filters, 1, probe.total, None, None
    )
    assert isinstance(full, PaginatedReportResult)
    total_revenue = Decimal("0")
    invoice_count = 0
    for row in full.items:
        assert isinstance(row, SalesSummaryRow)
        total_revenue += row.revenue
        invoice_count += row.invoice_count
    return PresentSalesSection(total_revenue=total_revenue, invoice_count=invoice_count)


def _accounting_ar_section(
    db: Session,
    entitlement_service: PlatformEntitlementService,
    company_id: UUID,
    user_id: UUID | None,
    user_roles: list[str] | None,
    customer_id: UUID,
) -> AccountingArSection:
    if not _domain_entitled(entitlement_service, company_id, "accounting"):
        return OmittedSection(reason="not_entitled")
    if not _permitted(db, company_id, user_id, user_roles, "reports.accounting.view"):
        return OmittedSection(reason="not_permitted")

    config = AccountingConfigurationRepository(db).get_for_company(
        company_id=company_id
    )
    if config is None:
        return UnavailableSection(reason="not_configured")

    ar_service = build_ar_service(db)
    try:
        row = ar_service.get_customer_aging(
            company_id, customer_id, as_of_date=date.today()
        )
    except CustomerLedgerNotFoundError:
        row = None
    balance = row.total if row is not None else Decimal("0")
    return PresentAccountingArSection(balance=balance)


def _crm_section(
    db: Session,
    entitlement_service: PlatformEntitlementService,
    company_id: UUID,
    user_id: UUID | None,
    user_roles: list[str] | None,
    customer_id: UUID,
) -> CrmSection:
    if not _domain_entitled(entitlement_service, company_id, "crm"):
        return OmittedSection(reason="not_entitled")
    if not _permitted(db, company_id, user_id, user_roles, "reports.crm.view"):
        return OmittedSection(reason="not_permitted")

    repo = get_opportunity_repository(db)
    _probe_items, total = repo.list_filtered(
        company_id, customer_id=customer_id, status="OPEN", page=1, page_size=1
    )
    if total == 0:
        return PresentCrmSection(
            open_opportunity_count=0, open_opportunity_value=Decimal("0")
        )
    items, _total = repo.list_filtered(
        company_id, customer_id=customer_id, status="OPEN", page=1, page_size=total
    )
    open_value = sum((o.value for o in items), Decimal("0"))
    return PresentCrmSection(
        open_opportunity_count=total, open_opportunity_value=open_value
    )


def _installments_section(
    db: Session,
    gate: InstallmentsServicingContinuityGate,
    company_id: UUID,
    user_id: UUID | None,
    user_roles: list[str] | None,
    customer_id: UUID,
) -> InstallmentsSection:
    state = gate.evaluate(company_id)
    if state is InstallmentsAccessState.UNAVAILABLE:
        return OmittedSection(reason="not_entitled")
    if not _permitted(db, company_id, user_id, user_roles, "reports.installments.view"):
        return OmittedSection(reason="not_permitted")
    # Explicit per-report-reference check (plan.md §14) — fails closed if a
    # future addition to this section ever exceeds Case B's own allow-list,
    # even though both keys are always allowed at this point today.
    for report_key in ("installments.register", "installments.aging"):
        if not InstallmentsServicingContinuityGate.is_allowed(report_key, state):
            return OmittedSection(reason="not_entitled")

    service = _build_installments_reporting_service(db)
    register_rows, _register_total = service.get_contract_register(
        company_id, skip=0, limit=_INSTALLMENTS_POPULATION_BOUND
    )
    contract_count = sum(
        1 for r in register_rows if r["customer_id"] == str(customer_id)
    )
    aging_rows, _aging_total = service.get_aging_report(
        company_id,
        as_of_date=date.today(),
        skip=0,
        limit=_INSTALLMENTS_POPULATION_BOUND,
    )
    outstanding_principal = sum(
        (
            Decimal(str(r["outstanding_amount"]))
            for r in aging_rows
            if r["customer_id"] == str(customer_id)
        ),
        Decimal("0"),
    )
    return PresentInstallmentsSection(
        outstanding_principal=outstanding_principal,
        contract_count=contract_count,
        read_only_servicing_continuity=state
        is InstallmentsAccessState.SERVICING_CONTINUITY,
    )


class Customer360Service:
    """Stateless — every method takes ``db`` explicitly, matching every
    other Phase 2-4 service's own convention."""

    def get(
        self,
        db: Session,
        *,
        company_id: UUID,
        user_id: UUID | None,
        customer_id: UUID,
        user_roles: list[str] | None = None,
    ) -> Customer360Response:
        # Base gate (T162): permission checked before Sales lookup —
        # minimizes unnecessary cross-module calls on an unauthorized
        # request.
        if not _permitted(db, company_id, user_id, user_roles, _BASE_PERMISSION):
            raise ReportPermissionDeniedError(_BASE_PERMISSION)

        # Customer master lookup (T161) — Sales' own NotFoundException
        # propagates uncaught: the platform's existing IDOR-safe not-found,
        # identical for "doesn't exist" and "wrong tenant".
        customer = get_customer_service(db).get_by_id(company_id, customer_id)

        entitlement_service = _build_entitlement_service(db)
        installments_gate = InstallmentsServicingContinuityGate(
            entitlement_service=entitlement_service,
            reporting_service=_build_installments_reporting_service(db),
        )

        sales = _sales_section(
            db, entitlement_service, company_id, user_id, user_roles, customer_id
        )
        accounting_ar = _accounting_ar_section(
            db, entitlement_service, company_id, user_id, user_roles, customer_id
        )
        crm = _crm_section(
            db, entitlement_service, company_id, user_id, user_roles, customer_id
        )
        installments = _installments_section(
            db, installments_gate, company_id, user_id, user_roles, customer_id
        )

        return Customer360Response(
            customer_id=customer.id,
            customer_name=customer.legal_name,
            sales=sales,
            accounting_ar=accounting_ar,
            crm=crm,
            installments=installments,
        )


customer_360_service = Customer360Service()

#: See ``dashboard_service.py``'s identical note: a Python bound-method
#: access creates a *new* object every evaluation, so pinning it once to a
#: stable module-level name is what lets T032's registry-consistency
#: identity check hold between ``COMPOSITE_REPORT_HANDLERS`` and
#: ``ReportDefinition.authoritative_source``.
get_customer_360 = customer_360_service.get

"""T116 (corrected — adapter-level) — ``InstallmentReportingService``
called directly vs. ``InstallmentsAdapter.run()`` — identical for
``installments.register``/``installments.dashboard``. (Business-logic
correctness of the dashboard's 13-metric derivation is already covered
by Installments' own existing test suite — this test only proves the
adapter is a faithful, non-lossy wrapper, matching the CRM/Accounting/
Purchase equivalence tests' established scope.)"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from modules.accounting.dependencies import (
    build_allocation_engine,
    build_ar_service,
    build_payment_service,
)
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
from modules.reports.schemas.installments import (
    ContractRegisterFilter,
    InstallmentDashboardFilter,
)
from modules.reports.services.adapters.base import (
    AggregateReportResult,
    PaginatedReportResult,
)
from modules.reports.services.adapters.installments_adapter import InstallmentsAdapter


def _direct_service(db: Session) -> InstallmentReportingService:
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


def test_register_equivalence(db_session: Session) -> None:
    company_id = uuid.uuid4()
    direct_rows, direct_total = _direct_service(db_session).get_contract_register(
        company_id
    )

    adapter = InstallmentsAdapter()
    result = adapter.run(
        db_session,
        company_id,
        "installments.register",
        ContractRegisterFilter(),
        page=1,
        page_size=20,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, PaginatedReportResult)
    assert result.total == direct_total
    assert len(result.items) == len(direct_rows)


def test_dashboard_equivalence(db_session: Session) -> None:
    company_id = uuid.uuid4()
    direct = _direct_service(db_session).get_dashboard(company_id)

    adapter = InstallmentsAdapter()
    result = adapter.run(
        db_session,
        company_id,
        "installments.dashboard",
        InstallmentDashboardFilter(),
        page=1,
        page_size=1,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, AggregateReportResult)
    assert result.data.active_contract_count == direct.active_contract_count
    assert result.data.outstanding_amount == direct.outstanding_amount
    assert result.data.overdue_amount == direct.overdue_amount
    assert result.data.overdue_count == direct.overdue_count

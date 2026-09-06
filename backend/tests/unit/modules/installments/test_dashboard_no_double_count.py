"""[Epic 10, Phase 12, T211] Service test — dashboard KPI buckets never
double-count (FR-INST-081): an amount that has crossed into OVERDUE is
excluded from "due this month," never counted in both buckets.

Real PostgreSQL (schedule persistence requires it).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.installments.models.schedule import InstallmentScheduleLine
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
from modules.installments.services.business_date import get_business_date
from modules.installments.services.reporting_service import (
    InstallmentReportingService,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)


def _build_reporting_service(pg_db_session: Session) -> InstallmentReportingService:
    from modules.accounting.dependencies import (
        build_allocation_engine,
        build_ar_service,
        build_payment_service,
    )

    gateway = AccountingIntegrationGateway(
        ar_service=build_ar_service(pg_db_session, with_sales_sync=False),
        payment_service=build_payment_service(pg_db_session),
        allocation_engine=build_allocation_engine(pg_db_session),
    )
    return InstallmentReportingService(
        contract_repo=InstallmentContractRepository(pg_db_session),
        schedule_repo=InstallmentScheduleRepository(pg_db_session),
        allocation_ref_repo=InstallmentAllocationReferenceRepository(pg_db_session),
        late_charge_repo=InstallmentLateChargeRepository(pg_db_session),
        audit_repo=InstallmentAuditLogRepository(pg_db_session),
        plan_template_repo=InstallmentPlanTemplateRepository(pg_db_session),
        accounting_gateway=gateway,
    )


class TestDashboardNoDoubleCounting:
    def test_overdue_line_excluded_from_due_this_month(
        self, pg_db_session: Session
    ) -> None:
        business_date = get_business_date()
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        lines = (
            pg_db_session.query(InstallmentScheduleLine)
            .filter_by(schedule_version_id=ctx["schedule_version"].id)
            .order_by(InstallmentScheduleLine.sequence)
            .all()
        )
        assert len(lines) == 2

        # Force the FIRST line (originally due today) 10 days into the
        # past — now genuinely OVERDUE. The SECOND line (due in 30 days)
        # remains a legitimate "due this month" candidate only if within
        # the current calendar month — left untouched either way; this
        # test only asserts the overdue line's own amount never also
        # appears in due_today/due_this_month.
        overdue_line = lines[0]
        overdue_line.due_date = business_date - timedelta(days=10)
        pg_db_session.add(overdue_line)
        pg_db_session.commit()

        svc = _build_reporting_service(pg_db_session)
        dashboard = svc.get_dashboard(ctx["company_id"], as_of_date=business_date)

        assert dashboard.overdue_amount == Decimal("100.00")
        assert dashboard.overdue_count == 1

        # The overdue amount must never ALSO be counted in due_today or
        # due_this_month — the exact FR-INST-081 guarantee.
        assert dashboard.due_today_amount != Decimal("100.00")
        assert dashboard.due_today_amount == Decimal("0")

        # Total non-double-counted obligation reconciles: overdue +
        # due_this_month + upcoming == the two lines' combined
        # scheduled_amount (200.00), never double- or under-counted.
        total_tracked = (
            dashboard.overdue_amount
            + dashboard.due_this_month_amount
            + dashboard.upcoming_receivables_amount
        )
        assert total_tracked == Decimal("200.00")

    def test_aging_distribution_matches_overdue_amount_exactly(
        self, pg_db_session: Session
    ) -> None:
        """The aging distribution's own bucket sum must equal
        overdue_amount exactly — the same underlying overdue lines,
        counted once, bucketed once, never summed twice."""
        business_date = get_business_date()
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("250.00")
        )
        line = (
            pg_db_session.query(InstallmentScheduleLine)
            .filter_by(schedule_version_id=ctx["schedule_version"].id)
            .one()
        )
        line.due_date = business_date - timedelta(days=45)
        pg_db_session.add(line)
        pg_db_session.commit()

        svc = _build_reporting_service(pg_db_session)
        dashboard = svc.get_dashboard(ctx["company_id"], as_of_date=business_date)

        assert dashboard.overdue_amount == Decimal("250.00")
        bucket_sum = sum(dashboard.aging_distribution.values(), Decimal("0"))
        assert bucket_sum == dashboard.overdue_amount == Decimal("250.00")
        assert dashboard.aging_distribution["days_31_60"] == Decimal("250.00")

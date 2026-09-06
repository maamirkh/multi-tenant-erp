"""[Epic 10, Phase 12 closure follow-up] Performance regression test for
``InstallmentReportingService._sum_late_charge_outstanding()`` — the one
remaining N+1 defect flagged (but not fixed, as out of scope) by the
Phase-12 closure commit 4c42136: it issued one
``AccountingIntegrationGateway.get_ar_transaction()`` round trip PER LATE
CHARGE, empirically confirmed to scale linearly with late-charge count.

Fixed by ``AccountingIntegrationGateway.sum_ar_transactions_outstanding()``
-> ``AccountsReceivableService.sum_outstanding_by_ids()`` ->
``ARTransactionRepository.sum_outstanding_excluding_written_off()`` — one
bounded aggregate query regardless of late-charge count.

Real PostgreSQL (schedule/AR tables require it); real SQL statement
counting via a ``before_cursor_execute`` listener, never runtime duration
as the primary proof (a duration assertion would pass even under linear
growth at these small row counts).
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import event, insert, select
from sqlalchemy.orm import Session

from modules.accounting.dependencies import (
    build_allocation_engine,
    build_ar_service,
    build_payment_service,
)
from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.installments.models.late_charge import InstallmentLateCharge
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
from modules.installments.services.reporting_service import (
    InstallmentReportingService,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)

_LATE_CHARGE_AMOUNT = Decimal("25.00")


def _build_reporting_service(db_session: Session) -> InstallmentReportingService:
    gateway = AccountingIntegrationGateway(
        ar_service=build_ar_service(db_session, with_sales_sync=False),
        payment_service=build_payment_service(db_session),
        allocation_engine=build_allocation_engine(db_session),
    )
    return InstallmentReportingService(
        contract_repo=InstallmentContractRepository(db_session),
        schedule_repo=InstallmentScheduleRepository(db_session),
        allocation_ref_repo=InstallmentAllocationReferenceRepository(db_session),
        late_charge_repo=InstallmentLateChargeRepository(db_session),
        audit_repo=InstallmentAuditLogRepository(db_session),
        plan_template_repo=InstallmentPlanTemplateRepository(db_session),
        accounting_gateway=gateway,
    )


def _seed_late_charges(
    db: Session,
    *,
    company_id: uuid.UUID,
    customer_id: uuid.UUID,
    contract_id: uuid.UUID,
    schedule_line_id: uuid.UUID,
    count: int,
) -> None:
    """Bulk-insert ``count`` OPEN ``DEBIT_NOTE`` ``ARTransaction`` rows
    (one per late charge, each independently collectible/outstanding —
    mirrors what ``AccountingIntegrationGateway.post_late_charge()``
    would have created) plus ``count`` ``InstallmentLateCharge`` rows
    referencing them via ``accounting_ar_transaction_id`` — the exact
    shape ``_sum_late_charge_outstanding()`` reads. All share the same
    ``schedule_line_id`` with distinct ``overdue_occurrence_date`` values
    (the table's real uniqueness constraint), avoiding the need for a
    separate schedule line per late charge."""
    if count == 0:
        return
    today = date.today()
    ledger_id = db.execute(
        select(CustomerLedger.id).where(
            CustomerLedger.company_id == company_id,
            CustomerLedger.customer_id == customer_id,
        )
    ).scalar_one()

    ar_transaction_ids = [uuid.uuid4() for _ in range(count)]
    ar_rows = [
        {
            "id": ar_transaction_ids[i],
            "company_id": company_id,
            "customer_ledger_id": ledger_id,
            "transaction_type": "DEBIT_NOTE",
            "transaction_date": today,
            "currency_code": "USD",
            "exchange_rate": Decimal("1"),
            "amount_foreign": _LATE_CHARGE_AMOUNT,
            "amount_base": _LATE_CHARGE_AMOUNT,
            "outstanding_amount": _LATE_CHARGE_AMOUNT,
            "status": "OPEN",
            "source_document_type": "InstallmentLateCharge",
        }
        for i in range(count)
    ]
    db.execute(insert(ARTransaction), ar_rows)

    late_charge_rows = [
        {
            "company_id": company_id,
            "contract_id": contract_id,
            "schedule_line_id": schedule_line_id,
            "charge_amount": _LATE_CHARGE_AMOUNT,
            "overdue_occurrence_date": today - timedelta(days=i),
            "accounting_ar_transaction_id": ar_transaction_ids[i],
        }
        for i in range(count)
    ]
    db.execute(insert(InstallmentLateCharge), late_charge_rows)
    db.commit()


class _QueryCounter:
    def __init__(self) -> None:
        self.count = 0

    def __call__(self, *args: object, **kwargs: object) -> None:
        self.count += 1


def _run_dashboard_with_n_late_charges(
    db_session: Session, count: int
) -> tuple[int, Decimal]:
    ctx = build_active_contract_with_schedule(db_session, installment_count=1)
    _seed_late_charges(
        db_session,
        company_id=ctx["company_id"],
        customer_id=ctx["customer_id"],
        contract_id=ctx["contract"].id,
        schedule_line_id=ctx["schedule_lines"][0].id,
        count=count,
    )
    svc = _build_reporting_service(db_session)

    counter = _QueryCounter()
    event.listen(db_session.bind, "before_cursor_execute", counter)
    try:
        dashboard = svc.get_dashboard(ctx["company_id"])
    finally:
        event.remove(db_session.bind, "before_cursor_execute", counter)

    return counter.count, dashboard.outstanding_amount


class TestLateChargeOutstandingPerformance:
    """Query count must stay flat (O(1)) as late-charge count grows —
    the pre-fix implementation issued one extra Accounting query per late
    charge, so this would FAIL at higher counts against that code
    (linear growth: ~9 + N queries). Post-fix it stays within the same
    small constant used by every other Phase-12 O(1) guard in this
    suite (test_report_pagination.py)."""

    def test_query_count_bounded_across_0_1_10_50_100_late_charges(
        self, db_session: Session
    ) -> None:
        results: dict[int, int] = {}
        for count in (0, 1, 10, 50, 100):
            queries, outstanding = _run_dashboard_with_n_late_charges(db_session, count)
            results[count] = queries
            assert outstanding >= _LATE_CHARGE_AMOUNT * count

        print(f"\nget_dashboard() query counts by late-charge count: {results}")

        baseline = results[0]
        for count in (1, 10, 50, 100):
            assert results[count] < 15, (
                f"expected O(1) queries for get_dashboard() regardless of "
                f"late-charge count, got {results[count]} queries for "
                f"{count} late charges (0-late-charge baseline was "
                f"{baseline})"
            )
            assert results[count] <= baseline + 2, (
                f"query count grew from {baseline} (0 late charges) to "
                f"{results[count]} ({count} late charges) — this is the "
                f"linear-growth signature of the per-late-charge N+1 "
                f"pattern this test guards against "
                f"(_sum_late_charge_outstanding() calling "
                f"get_ar_transaction() once per row)"
            )

    def test_query_count_does_not_scale_linearly_10_vs_100(
        self, db_session: Session
    ) -> None:
        """A second, independent seed/measurement pair (not reusing the
        table above) directly comparing a small and a large late-charge
        population within the same test — the same before/after-style
        comparison ``test_report_pagination.py`` uses for its own N+1
        guards."""
        small_queries, _ = _run_dashboard_with_n_late_charges(db_session, 10)
        large_queries, _ = _run_dashboard_with_n_late_charges(db_session, 100)

        assert large_queries <= small_queries + 2, (
            f"query count grew from {small_queries} (10 late charges) to "
            f"{large_queries} (100 late charges) — expected O(1), not "
            f"linear, growth"
        )

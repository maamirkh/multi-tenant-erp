"""[Epic 10, Phase 12, T204/T205] Correctness tests for
``InstallmentReportingService`` — each of the 8 report types plus the
dashboard, proving figures trace to the correct authoritative source
(plan.md §25).

Real PostgreSQL throughout (schedule persistence requires it).
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.accounting.dependencies import (
    build_allocation_engine,
    build_ar_service,
    build_payment_service,
)
from modules.installments.models.contract import InstallmentContract
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
    build_collection_service,
)


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


class TestContractRegisterReport:
    def test_contract_register_lists_contract_with_correct_fields(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = _build_reporting_service(db_session)

        rows, total = svc.get_contract_register(ctx["company_id"], skip=0, limit=20)

        assert total == 1
        assert rows[0]["contract_id"] == str(ctx["contract"].id)
        assert rows[0]["contract_number"] == ctx["contract"].contract_number
        assert rows[0]["status"] == "ACTIVE"
        assert rows[0]["contractual_total"] == "100.000000"

    def test_contract_register_status_filter_excludes_other_statuses(
        self, db_session: Session
    ) -> None:
        ctx_active = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = _build_reporting_service(db_session)

        rows, total = svc.get_contract_register(
            ctx_active["company_id"], status="DEFAULTED", skip=0, limit=20
        )
        assert total == 0
        assert rows == []


class TestCollectionReport:
    def test_collection_report_sources_amount_from_accounting_payment(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        collection_svc = build_collection_service(db_session)
        result = collection_svc.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        svc = _build_reporting_service(db_session)

        rows, total = svc.get_collection_report(ctx["company_id"], skip=0, limit=20)

        assert total == 1
        assert rows[0]["contract_id"] == str(ctx["contract"].id)
        assert rows[0]["allocated_amount"] == "100.000000"
        assert rows[0]["accounting_payment_id"] == result["accounting_payment_id"]
        assert rows[0]["payment_method"] == "BANK_TRANSFER"

    def test_collection_report_includes_reversal_rows(
        self, db_session: Session
    ) -> None:
        """[Phase-13-closure real-browser verification finding]
        ``get_collection_report`` is the sole read path the frontend
        contract-detail page's "Payments" section uses — before this
        fix it called ``list_for_company()`` without
        ``include_reversals=True`` (default ``False``), so a
        successfully-reversed collection (proven here via the real
        ``reverse_collection()`` service call, not a direct DB write)
        vanished from the report exactly as if it had never been
        reversed, and its "Reverse" action stayed offered on an
        already-reversed row.

        Two installments so the collection below is a partial payment —
        ``record_collection()`` auto-completes the contract at zero
        outstanding (its own docstring), and ``reverse_collection()``
        correctly refuses to reverse against a COMPLETED contract; the
        collection here must leave the contract ACTIVE for the reversal
        itself (not the report-visibility fix under test) to succeed."""
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        collection_svc = build_collection_service(db_session)
        result = collection_svc.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        collection_svc.reverse_collection(
            ctx["company_id"],
            uuid.UUID(result["accounting_payment_id"]),
            reason="Test reversal",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )
        svc = _build_reporting_service(db_session)

        rows, total = svc.get_collection_report(ctx["company_id"], skip=0, limit=20)

        assert total == 2
        reversal_rows = [r for r in rows if r["is_reversal"]]
        original_rows = [r for r in rows if not r["is_reversal"]]
        assert len(reversal_rows) == 1
        assert len(original_rows) == 1
        assert (
            reversal_rows[0]["accounting_payment_id"] == result["accounting_payment_id"]
        )
        assert reversal_rows[0]["allocated_amount"] == "100.000000"


class TestDueOverdueReports:
    def test_due_report_includes_line_due_today(
        self, db_session: Session, monkeypatch
    ) -> None:
        # build_active_contract_with_schedule() seeds the first line's
        # due_date from local date.today() (Phase 7 fixture, unrelated
        # to this phase); production reads business date from UTC
        # (business_date.py, FR-INST-115). Pin get_business_date() to
        # the exact same local "today" the fixture used so this
        # assertion is deterministic regardless of which side of the
        # UTC/local midnight boundary the test happens to run on.
        today = date.today()
        monkeypatch.setattr(
            "modules.installments.services.reporting_service.get_business_date",
            lambda: today,
        )
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = _build_reporting_service(db_session)

        rows, total = svc.get_due_report(ctx["company_id"], skip=0, limit=20)

        assert total == 1
        assert rows[0]["state"] == "DUE"
        assert rows[0]["contract_id"] == str(ctx["contract"].id)

    def test_overdue_report_excludes_a_line_still_within_grace(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            grace_period_days=30,
        )
        business_date = get_business_date()
        line = (
            db_session.query(InstallmentScheduleLine)
            .filter_by(schedule_version_id=ctx["schedule_version"].id)
            .one()
        )
        line.due_date = business_date - timedelta(days=5)
        db_session.add(line)
        db_session.commit()
        svc = _build_reporting_service(db_session)

        overdue_rows, overdue_total = svc.get_overdue_report(
            ctx["company_id"], skip=0, limit=20
        )
        due_rows, due_total = svc.get_due_report(ctx["company_id"], skip=0, limit=20)

        assert overdue_total == 0
        assert due_total == 1
        assert due_rows[0]["state"] == "DUE"

    def test_overdue_report_includes_a_line_past_grace(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        business_date = get_business_date()
        line = (
            db_session.query(InstallmentScheduleLine)
            .filter_by(schedule_version_id=ctx["schedule_version"].id)
            .one()
        )
        line.due_date = business_date - timedelta(days=10)
        db_session.add(line)
        db_session.commit()
        svc = _build_reporting_service(db_session)

        rows, total = svc.get_overdue_report(ctx["company_id"], skip=0, limit=20)

        assert total == 1
        assert rows[0]["state"] == "OVERDUE"
        assert rows[0]["days_overdue"] == 10


class TestAgingReport:
    def test_aging_report_buckets_an_overdue_line_correctly(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        business_date = get_business_date()
        line = (
            db_session.query(InstallmentScheduleLine)
            .filter_by(schedule_version_id=ctx["schedule_version"].id)
            .one()
        )
        line.due_date = business_date - timedelta(days=45)
        db_session.add(line)
        db_session.commit()
        svc = _build_reporting_service(db_session)

        rows, total = svc.get_aging_report(
            ctx["company_id"], as_of_date=business_date, skip=0, limit=20
        )

        assert total == 1
        assert rows[0]["bucket"] == "days_31_60"
        assert rows[0]["outstanding_amount"] == "100.000000"

    def test_aging_report_excludes_fully_paid_line(self, db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        collection_svc = build_collection_service(db_session)
        collection_svc.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        svc = _build_reporting_service(db_session)

        rows, total = svc.get_aging_report(ctx["company_id"], skip=0, limit=20)

        assert total == 0


class TestSettlementReport:
    def test_settlement_report_lists_a_settled_contract(
        self, db_session: Session
    ) -> None:
        from tests.integration.api.v1.installments.conftest import (
            build_settlement_service,
        )

        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        settlement_svc = build_settlement_service(db_session)
        from datetime import date as _date

        quote = settlement_svc.generate_quote(
            ctx["company_id"], ctx["contract"].id, _date.today()
        )
        settlement_svc.execute(
            ctx["company_id"],
            ctx["contract"].id,
            quote.settlement_amount,
            quote.as_of_date,
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        svc = _build_reporting_service(db_session)

        rows, total = svc.get_settlement_report(ctx["company_id"], skip=0, limit=20)

        assert total == 1
        assert rows[0]["contract_id"] == str(ctx["contract"].id)

    def test_ordinary_collection_never_appears_in_settlement_report(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        collection_svc = build_collection_service(db_session)
        collection_svc.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        svc = _build_reporting_service(db_session)

        rows, total = svc.get_settlement_report(ctx["company_id"], skip=0, limit=20)

        assert total == 0


class TestDefaultWriteoffReport:
    def test_writeoff_report_amount_reconciles_to_pre_writeoff_outstanding(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        contract = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        contract.status = "DEFAULTED"
        contract.defaulted_at = contract.contract_date  # type: ignore[assignment]
        db_session.add(contract)
        db_session.commit()

        contract_svc = _build_contract_service_with_writeoff(db_session)
        contract_svc.writeoff(
            ctx["company_id"],
            ctx["contract"].id,
            "Uncollectible",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )
        svc = _build_reporting_service(db_session)

        rows, total = svc.get_default_writeoff_report(
            ctx["company_id"], skip=0, limit=20
        )

        assert total == 1
        assert rows[0]["written_off_amount"] == "500.000000"
        assert rows[0]["written_off_at"] is not None


def _build_contract_service_with_writeoff(db_session: Session):
    from core.events.outbox import EventOutboxRepository
    from modules.installments.repositories.audit import InstallmentAuditLogRepository
    from modules.installments.repositories.configuration import (
        InstallmentConfigurationRepository,
    )
    from modules.installments.services.audit_service import InstallmentAuditService
    from modules.installments.services.configuration_service import (
        InstallmentConfigurationService,
    )
    from modules.installments.services.contract_service import (
        InstallmentContractService,
    )
    from modules.installments.services.idempotency_service import (
        InstallmentIdempotencyService,
    )

    gateway = AccountingIntegrationGateway(
        ar_service=build_ar_service(db_session, with_sales_sync=False),
        payment_service=build_payment_service(db_session),
        allocation_engine=build_allocation_engine(db_session),
    )
    return InstallmentContractService(
        repo=InstallmentContractRepository(db_session),
        sequence_repo=None,  # type: ignore[arg-type]
        eligibility_service=None,  # type: ignore[arg-type]
        accounting_gateway=gateway,
        configuration_service=InstallmentConfigurationService(
            repo=InstallmentConfigurationRepository(db_session)
        ),
        audit_service=InstallmentAuditService(
            db=db_session, audit_repo=InstallmentAuditLogRepository(db_session)
        ),
        schedule_repo=InstallmentScheduleRepository(db_session),
        idempotency_service=InstallmentIdempotencyService(db_session),
        outbox_repo=EventOutboxRepository(db_session),
        allocation_ref_repo=InstallmentAllocationReferenceRepository(db_session),
    )


class TestPlanPerformanceReport:
    def test_plan_performance_groups_custom_contracts_under_null_template(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = _build_reporting_service(db_session)

        rows, _total = svc.get_plan_performance_report(ctx["company_id"])

        assert len(rows) == 1
        assert rows[0]["plan_template_id"] is None
        assert rows[0]["contract_count"] == 1
        assert rows[0]["total_contractual_amount"] == "100.000000"


class TestDashboardSourcing:
    def test_active_contract_count_matches_real_count(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = _build_reporting_service(db_session)

        dashboard = svc.get_dashboard(ctx["company_id"])

        assert dashboard.active_contract_count == 1
        assert dashboard.outstanding_amount == Decimal("100.00")

    def test_written_off_balance_reflects_a_written_off_contract_without_per_contract_query(
        self, db_session: Session
    ) -> None:
        """Dashboard's written_off_balance must equal the same amount
        get_default_writeoff_report() reports for the contract (single
        aggregate query, never a per-contract loop — see
        _sum_written_off_balance()'s docstring)."""
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        contract = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        contract.status = "DEFAULTED"
        contract.defaulted_at = contract.contract_date  # type: ignore[assignment]
        db_session.add(contract)
        db_session.commit()

        contract_svc = _build_contract_service_with_writeoff(db_session)
        contract_svc.writeoff(
            ctx["company_id"],
            ctx["contract"].id,
            "Uncollectible",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )
        svc = _build_reporting_service(db_session)

        dashboard = svc.get_dashboard(ctx["company_id"])

        assert dashboard.written_off_balance == Decimal("500.00")

    def test_collected_today_reflects_real_collection(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        collection_svc = build_collection_service(db_session)
        collection_svc.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        svc = _build_reporting_service(db_session)

        dashboard = svc.get_dashboard(ctx["company_id"])

        assert dashboard.collected_today_amount == Decimal("100.00")
        assert dashboard.collected_this_month_amount == Decimal("100.00")
        # The contract completed (zero outstanding) — no longer counted
        # as an "outstanding" balance.
        assert dashboard.outstanding_amount == Decimal("0")

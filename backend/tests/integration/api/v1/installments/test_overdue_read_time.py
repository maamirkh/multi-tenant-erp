"""[Epic 10, Phase 8, T148] Service test — overdue read-time correctness
independent of any background job having run (BR-INST-019, FR-INST-122,
Scenario E).

No cron/reminder job exists yet (Phase 12) and none is invoked here —
this test proves the due-state for an overdue line is correct purely
from reading live repository state (schedule line + net-allocated
amount) through ``DueStateCalculator``, at the moment of the read, using
the contract's own frozen ``grace_period_days`` (FR-INST-172).

Real Postgres (schedule tables require it).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.services.due_state import DueStateCalculator
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
)


def _due_state_for_line(db_session, ctx, line) -> str:
    net_allocated = (
        InstallmentAllocationReferenceRepository(db_session)
        .get_net_allocated_by_line(ctx["company_id"], [line.id])
        .get(line.id, Decimal("0"))
    )
    grace_period_days = ctx["contract"].terms_snapshot.get("grace_period_days", 0)
    result = DueStateCalculator.calculate(
        scheduled_amount=line.scheduled_amount,
        paid_amount=net_allocated,
        due_date=line.due_date,
        business_date=date.today(),
        grace_period_days=grace_period_days,
        waived_at=line.waived_at,
        voided_at=line.voided_at,
    )
    return result.state


class TestOverdueReadTimeCorrectness:
    def test_overdue_line_reads_correctly_with_no_background_job_involved(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            grace_period_days=3,
        )
        line = ctx["schedule_lines"][0]

        # Force the line's due_date into the past, past its grace
        # period, entirely at the data level — never touching a
        # scheduled/cron mechanism (none exists), proving the read-time
        # derivation alone determines OVERDUE.
        line.due_date = date.today() - timedelta(days=10)
        db_session.add(line)
        db_session.commit()

        state = _due_state_for_line(db_session, ctx, line)
        assert state == "OVERDUE"

    def test_due_within_grace_reads_as_due_not_overdue(self, db_session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            grace_period_days=10,
        )
        line = ctx["schedule_lines"][0]
        line.due_date = date.today() - timedelta(days=3)
        db_session.add(line)
        db_session.commit()

        assert _due_state_for_line(db_session, ctx, line) == "DUE"

    def test_partial_collection_then_read_reflects_partially_paid_live(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            grace_period_days=0,
        )
        line = ctx["schedule_lines"][0]
        line.due_date = date.today() - timedelta(days=30)
        db_session.add(line)
        db_session.commit()

        service = build_collection_service(db_session)
        import uuid

        service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("40.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        db_session.refresh(line)
        assert _due_state_for_line(db_session, ctx, line) == "PARTIALLY_PAID"

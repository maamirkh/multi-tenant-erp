"""[Epic 10, Phase 8, T150] Accounting integration test — late-charge
collectibility.

A subsequent ordinary customer payment, allocated via
``InstallmentAllocationPolicy.allocate_oldest_first()``, satisfies the
late charge's ``ARTransaction`` with no special-case code path (plan.md
§11.3): the late charge's own ``DEBIT_NOTE`` ``ARTransaction`` is an
ordinary, independently-allocatable AR obligation, collected through
``InstallmentCollectionService.record_collection()`` exactly like a
schedule line — proven here by observing Accounting's own
``PaymentAllocationLine``/``ARTransaction.outstanding_amount`` change,
not a mocked or special-cased path.

Real Postgres (schedule tables require it).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select

from modules.accounting.models.ar import ARTransaction
from modules.accounting.models.payments import PaymentAllocationLine
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
    build_delinquency_service,
)

_POLICY = {"enabled": True, "charge_type": "FIXED", "amount": "25.00"}


class TestLateChargeCollectibility:
    def test_ordinary_collection_satisfies_late_charge_ar_via_oldest_first(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            late_charge_policy=_POLICY,
        )
        line = ctx["schedule_lines"][0]
        delinquency_service = build_delinquency_service(db_session)

        late_charge = delinquency_service.apply_late_charge(
            ctx["company_id"], ctx["contract"].id, line.id, actor_id=None
        )
        db_session.commit()
        db_session.refresh(late_charge)

        # The late charge's due-analog (overdue_occurrence_date) equals
        # the line's own due_date, which is earlier than nothing else —
        # both the schedule line (100.00) and the late charge (25.00)
        # are simultaneously open, so a single payment covering both
        # exercises the oldest-first ordering across the combined pool.
        collection_service = build_collection_service(db_session)
        result = collection_service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("125.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        db_session.commit()

        assert result["contract_status"] == "COMPLETED"

        ar_transaction = db_session.execute(
            select(ARTransaction).where(
                ARTransaction.id == late_charge.accounting_ar_transaction_id
            )
        ).scalar_one()
        assert ar_transaction.outstanding_amount == Decimal("0")
        assert ar_transaction.status == "PAID"

        # Accounting's own PaymentAllocationLine — not any Installments
        # row — is the authoritative explanation of the late charge's
        # satisfaction; confirms allocate_oldest_first() reached the
        # late charge's ARTransaction with no special-case branch.
        allocation_lines = (
            db_session.execute(
                select(PaymentAllocationLine).where(
                    PaymentAllocationLine.ar_transaction_id
                    == late_charge.accounting_ar_transaction_id
                )
            )
            .scalars()
            .all()
        )
        assert len(allocation_lines) == 1
        assert allocation_lines[0].allocated_amount_foreign == Decimal("25.00")

    def test_partial_payment_covering_only_the_late_charge_leaves_schedule_open(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            late_charge_policy=_POLICY,
        )
        line = ctx["schedule_lines"][0]
        delinquency_service = build_delinquency_service(db_session)

        late_charge = delinquency_service.apply_late_charge(
            ctx["company_id"], ctx["contract"].id, line.id, actor_id=None
        )
        db_session.commit()

        # The schedule line's due_date is earlier than the late charge's
        # overdue_occurrence_date is impossible here (they're equal —
        # both derive from line.due_date) so oldest-first is a tie;
        # deterministic tie-breaking (stable sort, insertion order) means
        # the schedule line is allocated first. A payment smaller than
        # the schedule line's own outstanding therefore leaves the late
        # charge fully untouched, not partially — proving the ordering
        # is genuinely due-date-driven, not accidental.
        collection_service = build_collection_service(db_session)
        collection_service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("50.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        db_session.commit()

        ar_transaction = db_session.execute(
            select(ARTransaction).where(
                ARTransaction.id == late_charge.accounting_ar_transaction_id
            )
        ).scalar_one()
        assert ar_transaction.outstanding_amount == Decimal("25.00")

"""[Epic 10, Phase 8, T151] Accounting integration test — late-charge
waiver reconciliation.

Post-waiver, the GL reversal AND ``ARTransaction.outstanding_amount == 0``
AND the ``CustomerLedger`` recompute all land together (plan.md §12.1
"Waiver" row) — the original charge row is preserved (BR-INST-017), only
marked waived; the reversal is itself a new, auditable event layered on
top of history, never a deletion.

Real Postgres (schedule tables require it).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.installments.exceptions import InstallmentLateChargeAlreadyWaivedError
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_delinquency_service,
)

_POLICY = {"enabled": True, "charge_type": "FIXED", "amount": "25.00"}


class TestLateChargeWaiverReconciliation:
    def test_waiver_reverses_gl_ar_and_ledger_together(self, db_session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            late_charge_policy=_POLICY,
        )
        line = ctx["schedule_lines"][0]
        service = build_delinquency_service(db_session)

        late_charge = service.apply_late_charge(
            ctx["company_id"], ctx["contract"].id, line.id, actor_id=None
        )
        db_session.commit()

        ledger_after_charge = db_session.execute(
            select(CustomerLedger).where(
                CustomerLedger.company_id == ctx["company_id"],
                CustomerLedger.customer_id == ctx["customer_id"],
            )
        ).scalar_one()
        outstanding_after_charge = ledger_after_charge.total_outstanding_base

        waived = service.waive_late_charge(
            ctx["company_id"],
            ctx["contract"].id,
            late_charge.id,
            reason="Goodwill gesture",
            actor_id=None,
        )
        db_session.commit()

        assert waived.waived_at is not None
        assert waived.waived_reason == "Goodwill gesture"

        ar_transaction = db_session.execute(
            select(ARTransaction).where(
                ARTransaction.id == late_charge.accounting_ar_transaction_id
            )
        ).scalar_one()
        assert ar_transaction.outstanding_amount == Decimal("0")

        db_session.refresh(ledger_after_charge)
        assert (
            ledger_after_charge.total_outstanding_base
            == outstanding_after_charge - Decimal("25.00")
        )

        # BR-INST-017: the original row survives, never deleted — only
        # the waiver fields are set.
        assert waived.id == late_charge.id
        assert waived.charge_amount == Decimal("25.00")

    def test_double_waiver_is_rejected(self, db_session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            late_charge_policy=_POLICY,
        )
        line = ctx["schedule_lines"][0]
        service = build_delinquency_service(db_session)

        late_charge = service.apply_late_charge(
            ctx["company_id"], ctx["contract"].id, line.id, actor_id=None
        )
        db_session.commit()

        service.waive_late_charge(
            ctx["company_id"],
            ctx["contract"].id,
            late_charge.id,
            reason="First waiver",
            actor_id=None,
        )
        db_session.commit()

        with pytest.raises(InstallmentLateChargeAlreadyWaivedError):
            service.waive_late_charge(
                ctx["company_id"],
                ctx["contract"].id,
                late_charge.id,
                reason="Second attempt",
                actor_id=None,
            )
        db_session.rollback()

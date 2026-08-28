"""[Epic 10, Phase 8, T149] Accounting integration test — late-charge
GL/AR consistency.

Posting a late charge must produce exactly one ``JournalEntry`` AND
exactly one ``DEBIT_NOTE``-type ``ARTransaction`` AND one
``CustomerLedger.total_outstanding_base`` recompute — all three present
together, never a partial subset (plan.md §12.1/§12.2).

Real Postgres (schedule tables require it).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.accounting.models.gl import JournalEntry
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_delinquency_service,
)

_POLICY = {"enabled": True, "charge_type": "FIXED", "amount": "25.00"}


class TestLateChargeGlArConsistency:
    def test_posting_a_late_charge_produces_exactly_one_journal_entry_and_ar_transaction(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            late_charge_policy=_POLICY,
        )
        line = ctx["schedule_lines"][0]
        service = build_delinquency_service(db_session)

        # Baseline ledger snapshot before the charge — captured before
        # posting so the recompute can be proven to have actually
        # changed it.
        customer_ledger_before = db_session.execute(
            select(CustomerLedger).where(
                CustomerLedger.company_id == ctx["company_id"],
                CustomerLedger.customer_id == ctx["customer_id"],
            )
        ).scalar_one()
        outstanding_before = customer_ledger_before.total_outstanding_base

        late_charge = service.apply_late_charge(
            ctx["company_id"], ctx["contract"].id, line.id, actor_id=None
        )
        db_session.commit()

        assert late_charge.accounting_journal_entry_id is not None
        assert late_charge.accounting_ar_transaction_id is not None

        journal_entries = (
            db_session.execute(
                select(JournalEntry)
                .where(JournalEntry.company_id == ctx["company_id"])
                .where(JournalEntry.id == late_charge.accounting_journal_entry_id)
            )
            .scalars()
            .all()
        )
        assert len(journal_entries) == 1

        ar_transactions = (
            db_session.execute(
                select(ARTransaction)
                .where(ARTransaction.company_id == ctx["company_id"])
                .where(ARTransaction.id == late_charge.accounting_ar_transaction_id)
            )
            .scalars()
            .all()
        )
        assert len(ar_transactions) == 1
        ar_transaction = ar_transactions[0]
        assert ar_transaction.transaction_type == "DEBIT_NOTE"
        assert ar_transaction.outstanding_amount == Decimal("25.00")
        assert ar_transaction.source_document_type == "InstallmentLateCharge"
        assert ar_transaction.source_document_id == late_charge.id

        db_session.refresh(customer_ledger_before)
        assert (
            customer_ledger_before.total_outstanding_base
            == outstanding_before + Decimal("25.00")
        )

        # No unrelated duplicate JournalEntry/ARTransaction exists for
        # this company beyond the invoice's own baseline row + this
        # exact charge — confirms no partial/duplicate subset.
        all_payment_sourced_journal_entries = (
            db_session.execute(
                select(JournalEntry)
                .where(JournalEntry.company_id == ctx["company_id"])
                .where(JournalEntry.posting_source == "MANUAL")
            )
            .scalars()
            .all()
        )
        assert len(all_payment_sourced_journal_entries) == 1

    def test_percentage_policy_computes_amount_from_line_outstanding(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("200.00"),
            late_charge_policy={
                "enabled": True,
                "charge_type": "PERCENTAGE",
                "amount": "5",
            },
        )
        line = ctx["schedule_lines"][0]
        service = build_delinquency_service(db_session)

        late_charge = service.apply_late_charge(
            ctx["company_id"], ctx["contract"].id, line.id, actor_id=None
        )
        db_session.commit()

        assert late_charge.charge_amount == Decimal("10.00")

    def test_cap_amount_limits_the_computed_charge(self, db_session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("1000.00"),
            late_charge_policy={
                "enabled": True,
                "charge_type": "PERCENTAGE",
                "amount": "10",
                "cap_amount": "20.00",
            },
        )
        line = ctx["schedule_lines"][0]
        service = build_delinquency_service(db_session)

        late_charge = service.apply_late_charge(
            ctx["company_id"], ctx["contract"].id, line.id, actor_id=None
        )
        db_session.commit()

        assert late_charge.charge_amount == Decimal("20.00")

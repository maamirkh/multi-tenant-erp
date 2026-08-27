"""[Epic 10, Phase 7, T135] Accounting integration test: no duplicate
``Payment``/``ARTransaction``/``JournalEntry`` per collection — Installments
never creates a parallel financial-truth record (BR-INST-004/007,
FR-INST-142). Real Postgres (schedule tables require it).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_ar_service
from modules.accounting.models.ar import ARTransaction
from modules.accounting.models.gl import JournalEntry
from modules.accounting.models.payments import Payment
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
)


class TestCollectionNoDuplication:
    def test_exactly_one_payment_and_journal_entry_per_collection(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=3, installment_amount=Decimal("100.00")
        )
        service = build_collection_service(db_session)

        payment_count_before = (
            db_session.execute(
                select(Payment).where(Payment.company_id == ctx["company_id"])
            )
            .scalars()
            .all()
        )
        assert len(payment_count_before) == 0

        result = service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        payments = (
            db_session.execute(
                select(Payment).where(Payment.company_id == ctx["company_id"])
            )
            .scalars()
            .all()
        )
        assert len(payments) == 1
        assert str(payments[0].id) == result["accounting_payment_id"]

        journal_entries = (
            db_session.execute(
                select(JournalEntry)
                .where(JournalEntry.company_id == ctx["company_id"])
                .where(JournalEntry.id == payments[0].journal_entry_id)
            )
            .scalars()
            .all()
        )
        assert len(journal_entries) == 1

        ar_transactions = (
            db_session.execute(
                select(ARTransaction).where(
                    ARTransaction.company_id == ctx["company_id"]
                )
            )
            .scalars()
            .all()
        )
        # Exactly the two rows Accounting always creates for a collection
        # against an existing invoice: the original invoice ARTransaction
        # (reused, never duplicated) and the payment's own credit
        # ARTransaction — never a third, Installments-created row.
        assert len(ar_transactions) == 2
        invoice_transaction = next(
            t for t in ar_transactions if t.transaction_type == "INVOICE"
        )
        assert invoice_transaction.id == ctx["invoice"].id

    def test_multiple_collections_reuse_the_same_invoice_ar_transaction(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        service = build_collection_service(db_session)

        service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        payments = (
            db_session.execute(
                select(Payment).where(Payment.company_id == ctx["company_id"])
            )
            .scalars()
            .all()
        )
        assert len(payments) == 2  # one Payment per collection, never merged

        invoice_transactions = (
            db_session.execute(
                select(ARTransaction)
                .where(ARTransaction.company_id == ctx["company_id"])
                .where(ARTransaction.transaction_type == "INVOICE")
            )
            .scalars()
            .all()
        )
        # Still exactly one invoice ARTransaction across both collections
        # — never duplicated per collection.
        assert len(invoice_transactions) == 1
        assert invoice_transactions[0].id == ctx["invoice"].id
        assert invoice_transactions[0].outstanding_amount == Decimal("0")

        ar_service = build_ar_service(db_session, with_sales_sync=False)
        reconciled = ar_service.reconcile_ar_control_account(ctx["company_id"])
        assert reconciled == Decimal("0")

"""[Epic 10, Phase 7, T137] Real-Postgres concurrency test — two
concurrent full-amount collections against the last remaining
installment. Exactly one succeeds via the ``FOR UPDATE`` lock on
``InstallmentContract`` (Scenario J, BR-INST-011).
"""

from __future__ import annotations

import threading
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from modules.accounting.models.ar import ARTransaction
from modules.accounting.models.gl import JournalEntry
from modules.accounting.models.payments import Payment
from modules.installments.exceptions import (
    InstallmentActivationFailedError,
    InstallmentOverCollectionError,
)
from modules.installments.models.allocation_reference import (
    InstallmentAllocationReference,
)
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
)


class TestConcurrentFullAmountCollections:
    def test_exactly_one_of_two_concurrent_full_collections_succeeds(
        self, db_session, pg_engine
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        company_id = ctx["company_id"]
        contract_id = ctx["contract"].id
        bank_account_id = ctx["bank_account"].id

        session_factory = sessionmaker(bind=pg_engine)
        session_a = session_factory()
        session_b = session_factory()

        results: dict[str, object] = {}

        def _attempt(label: str, session) -> None:
            try:
                service = build_collection_service(session)
                result = service.record_collection(
                    company_id,
                    contract_id,
                    amount=Decimal("500.00"),
                    payment_method="BANK_TRANSFER",
                    idempotency_key=str(uuid.uuid4()),
                    actor_id=None,
                    bank_account_id=bank_account_id,
                )
                results[label] = ("success", result)
            except Exception as exc:  # noqa: BLE001 — capturing for assertion
                session.rollback()
                results[label] = ("error", exc)

        thread_a = threading.Thread(target=_attempt, args=("a", session_a))
        thread_b = threading.Thread(target=_attempt, args=("b", session_b))
        thread_a.start()
        thread_b.start()
        thread_a.join(timeout=30)
        thread_b.join(timeout=30)

        session_a.close()
        session_b.close()

        outcomes = [results["a"][0], results["b"][0]]
        assert (
            outcomes.count("success") == 1
        ), f"expected exactly one success, got: {results}"
        assert outcomes.count("error") == 1

        loser_label = "a" if results["a"][0] == "error" else "b"
        loser_exc = results[loser_label][1]
        # The FOR UPDATE lock serializes the two attempts: the winner
        # commits first, so the loser's own subsequent read (after the
        # lock releases) sees the now-fully-satisfied state. Since this
        # is a single-line, full-amount collection, the winner's
        # commit already auto-completed the contract (FR-INST-104) —
        # the loser therefore correctly sees a COMPLETED contract
        # (InstallmentActivationFailedError's servicing-status guard)
        # rather than a stale ACTIVE-with-zero-outstanding view that
        # would instead raise InstallmentOverCollectionError. Both
        # outcomes equally prove BR-INST-011 (never over-collected) —
        # which specific typed exception surfaces depends only on
        # whether the contract's single line was the last one.
        assert isinstance(
            loser_exc,
            InstallmentOverCollectionError | InstallmentActivationFailedError,
        )

        verify_session = session_factory()
        try:
            refs = InstallmentAllocationReferenceRepository(
                verify_session
            ).list_for_contract(company_id, contract_id)
            # Never over-collected: exactly one allocation-reference row
            # exists (BR-INST-011) — not two, not zero.
            assert len(refs) == 1
            assert refs[0].allocated_amount == Decimal("500.00")
            winning_payment_id = refs[0].accounting_payment_id

            # Exactly-once Accounting effect, not merely one Installments
            # reference row — authoritative filters (company_id +
            # customer_id, and the specific winning payment id from the
            # reference row above) so unrelated fixture data in the same
            # throwaway database cannot produce a false positive.
            payments = (
                verify_session.execute(
                    select(Payment)
                    .where(Payment.company_id == company_id)
                    .where(Payment.party_id == ctx["customer_id"])
                )
                .scalars()
                .all()
            )
            assert (
                len(payments) == 1
            ), f"expected exactly 1 Payment, found {len(payments)}"
            assert payments[0].id == winning_payment_id
            assert payments[0].amount_foreign == Decimal("500.00")

            winning_payment_journal_entry_id = payments[0].journal_entry_id
            journal_entries_for_payment = (
                verify_session.execute(
                    select(JournalEntry)
                    .where(JournalEntry.company_id == company_id)
                    .where(JournalEntry.id == winning_payment_journal_entry_id)
                )
                .scalars()
                .all()
            )
            assert len(journal_entries_for_payment) == 1

            # Exactly one credit ARTransaction sourced from this specific
            # winning Payment (the invoice's own ARTransaction is a
            # separate, pre-existing row from fixture setup — filtered
            # out here by source_document_type).
            credit_ar_transactions = (
                verify_session.execute(
                    select(ARTransaction)
                    .where(ARTransaction.company_id == company_id)
                    .where(ARTransaction.source_document_type == "Payment")
                    .where(ARTransaction.source_document_id == winning_payment_id)
                )
                .scalars()
                .all()
            )
            assert len(credit_ar_transactions) == 1

            # No duplicate Payment/JournalEntry exists anywhere for this
            # company at all — the loser genuinely created zero financial
            # rows, not merely zero allocation-reference rows.
            all_payments_for_company = (
                verify_session.execute(
                    select(Payment).where(Payment.company_id == company_id)
                )
                .scalars()
                .all()
            )
            assert len(all_payments_for_company) == 1

            # Fully unconditional, company-wide exactly-once proof — none
            # of the four queries below filter by the winning row's own
            # id, so a second row left behind by a genuinely broken lock
            # (rather than a cleanly rolled-back loser) cannot hide from
            # them. The only filters are company_id plus the smallest
            # authoritative Phase-7 type/source criteria needed to
            # exclude the fixture's own pre-existing invoice rows
            # (transaction_type="INVOICE"/source_document_type=
            # "SalesInvoice" for the ARTransaction, posting_source="SALES"
            # for its JournalEntry) — never the winning payment/journal id.
            all_refs_for_company = (
                verify_session.execute(
                    select(InstallmentAllocationReference).where(
                        InstallmentAllocationReference.company_id == company_id
                    )
                )
                .scalars()
                .all()
            )
            assert (
                len(all_refs_for_company) == 1
            ), f"expected exactly 1 InstallmentAllocationReference, found {len(all_refs_for_company)}"

            all_payment_journal_entries = (
                verify_session.execute(
                    select(JournalEntry)
                    .where(JournalEntry.company_id == company_id)
                    .where(JournalEntry.posting_source == "PAYMENT")
                )
                .scalars()
                .all()
            )
            assert (
                len(all_payment_journal_entries) == 1
            ), f"expected exactly 1 payment-sourced JournalEntry, found {len(all_payment_journal_entries)}"
            assert all_payment_journal_entries[0].id == winning_payment_journal_entry_id

            all_payment_ar_transactions = (
                verify_session.execute(
                    select(ARTransaction)
                    .where(ARTransaction.company_id == company_id)
                    .where(ARTransaction.transaction_type == "PAYMENT")
                    .where(ARTransaction.source_document_type == "Payment")
                )
                .scalars()
                .all()
            )
            assert (
                len(all_payment_ar_transactions) == 1
            ), f"expected exactly 1 payment-sourced ARTransaction, found {len(all_payment_ar_transactions)}"
            assert (
                all_payment_ar_transactions[0].source_document_id == winning_payment_id
            )
        finally:
            verify_session.close()

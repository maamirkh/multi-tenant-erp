"""[Epic 10, Phase 9, gap-closing] Real-Postgres concurrency test — two
concurrent ``InstallmentSettlementService.execute()`` calls against the
SAME contract, using the exact two-thread/two-session pattern Phase 7's
``test_concurrent_collections.py`` established for
``InstallmentCollectionService.record_collection()``.

Closes the "SETTLEMENT CONCURRENCY EVIDENCE GAP" identified during
Phase 9 closure verification: no prior test exercised
``InstallmentSettlementService.execute()`` itself under real concurrency
— only ``record_collection()`` (which ``execute()`` internally reuses)
had been proven this way. Architectural inference that the shared
``FOR UPDATE`` lock in ``execute_collection_sequence()`` would behave
identically is not accepted as a substitute for direct evidence; this
test supplies it.

Both threads submit the SAME ``quoted_amount``/``quoted_as_of_date``
(from one shared prior quote) but DIFFERENT idempotency keys — the
realistic race of two independent user sessions settling the same
contract at once, not a same-key retry (already covered by
``test_settlement_execution.py``'s replay test). This also isolates the
proof to the ``FOR UPDATE`` lock alone: two distinct idempotency keys
never conflict with each other at the reservation step, so if the race
is correctly resolved, it can only be the row lock doing it.
"""

from __future__ import annotations

import threading
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from modules.accounting.models.ar import ARTransaction
from modules.accounting.models.gl import JournalEntry
from modules.accounting.models.payments import Payment
from modules.installments.exceptions import InstallmentSettlementNotAllowedError
from modules.installments.models.allocation_reference import (
    InstallmentAllocationReference,
)
from modules.installments.models.contract import InstallmentContract
from modules.installments.models.idempotency import InstallmentIdempotencyKey
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_settlement_service,
)


class TestConcurrentSettlementExecutions:
    def test_exactly_one_of_two_concurrent_settlements_succeeds(
        self, db_session, pg_engine
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        company_id = ctx["company_id"]
        contract_id = ctx["contract"].id
        bank_account_id = ctx["bank_account"].id
        customer_id = ctx["customer_id"]

        # One shared, prior quote — both concurrent attempts submit the
        # identical quoted_amount/quoted_as_of_date a real client would
        # have gotten from a single /settlement/quote call.
        quote_service = build_settlement_service(db_session)
        quote = quote_service.generate_quote(company_id, contract_id, date.today())
        assert quote.settlement_amount == Decimal("500.00")

        session_factory = sessionmaker(bind=pg_engine)
        session_a = session_factory()
        session_b = session_factory()

        results: dict[str, object] = {}

        def _attempt(label: str, session) -> None:
            try:
                service = build_settlement_service(session)
                contract = service.execute(
                    company_id,
                    contract_id,
                    quote.settlement_amount,
                    quote.as_of_date,
                    idempotency_key=str(uuid.uuid4()),
                    actor_id=None,
                    bank_account_id=bank_account_id,
                )
                # Extract primitives now — the ORM instance is bound to
                # this thread's own session, about to be closed below.
                results[label] = (
                    "success",
                    {"id": contract.id, "status": contract.status},
                )
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
        assert outcomes.count("success") == 1, (
            f"expected exactly one success, got: {results}"
        )
        assert outcomes.count("error") == 1

        winner_label = "a" if results["a"][0] == "success" else "b"
        loser_label = "b" if winner_label == "a" else "a"
        winner_payload = results[winner_label][1]
        loser_exc = results[loser_label][1]

        # Deterministic, approved loser behavior: the winner's commit
        # already transitioned the contract to COMPLETED (a full,
        # single-installment settlement with no late charge), so the
        # loser's own post-lock re-read sees a non-settleable status and
        # is rejected by execute()'s own settleable-status guard —
        # never a stale-quote mismatch (the amounts were identical) and
        # never an over-collection error (settlement has no such check).
        assert isinstance(loser_exc, InstallmentSettlementNotAllowedError)
        assert winner_payload["status"] == "COMPLETED"

        verify_session = session_factory()
        try:
            # --- Winner-linked checks -----------------------------------
            refs = InstallmentAllocationReferenceRepository(
                verify_session
            ).list_for_contract(company_id, contract_id)
            assert len(refs) == 1
            assert refs[0].allocated_amount == Decimal("500.00")
            winning_payment_id = refs[0].accounting_payment_id

            payments = (
                verify_session.execute(
                    select(Payment)
                    .where(Payment.company_id == company_id)
                    .where(Payment.party_id == customer_id)
                )
                .scalars()
                .all()
            )
            assert len(payments) == 1, (
                f"expected exactly 1 Payment, found {len(payments)}"
            )
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

            # --- Fully unconditional, company-wide exactly-once proof ---
            # None of these four queries filter by the winning row's own
            # id — a second row left behind by a genuinely broken lock
            # (rather than a cleanly rolled-back loser) cannot hide from
            # them. Only company_id plus the minimal authoritative
            # type/source discriminators needed to exclude the fixture's
            # own pre-existing invoice rows.
            all_payments_for_company = (
                verify_session.execute(
                    select(Payment).where(Payment.company_id == company_id)
                )
                .scalars()
                .all()
            )
            assert len(all_payments_for_company) == 1, (
                f"expected exactly 1 Payment company-wide, found {len(all_payments_for_company)}"
            )

            all_refs_for_company = (
                verify_session.execute(
                    select(InstallmentAllocationReference).where(
                        InstallmentAllocationReference.company_id == company_id
                    )
                )
                .scalars()
                .all()
            )
            assert len(all_refs_for_company) == 1, (
                f"expected exactly 1 InstallmentAllocationReference, found {len(all_refs_for_company)}"
            )

            all_payment_journal_entries = (
                verify_session.execute(
                    select(JournalEntry)
                    .where(JournalEntry.company_id == company_id)
                    .where(JournalEntry.posting_source == "PAYMENT")
                )
                .scalars()
                .all()
            )
            assert len(all_payment_journal_entries) == 1, (
                f"expected exactly 1 payment-sourced JournalEntry, found {len(all_payment_journal_entries)}"
            )
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
            assert len(all_payment_ar_transactions) == 1, (
                f"expected exactly 1 payment-sourced ARTransaction, found {len(all_payment_ar_transactions)}"
            )
            assert (
                all_payment_ar_transactions[0].source_document_id == winning_payment_id
            )

            # --- Contract's final authoritative state --------------------
            refreshed_contract = (
                verify_session.execute(
                    select(InstallmentContract).where(
                        InstallmentContract.id == contract_id
                    )
                )
                .scalars()
                .one()
            )
            assert refreshed_contract.status == "COMPLETED"
            assert refreshed_contract.closed_at is not None
            assert refreshed_contract.id == winner_payload["id"]

            # --- Idempotency reservation interaction with FOR UPDATE -----
            # Exactly one settlement.execute reservation exists — the
            # winner's, COMPLETED. The loser's own reservation (a
            # different idempotency_key, successfully inserted before
            # either thread ever reached the row lock) was rolled back
            # along with the rest of its failed transaction: it was
            # never a stranded IN_PROGRESS row, it simply does not exist
            # — proving the FOR UPDATE lock, not the idempotency
            # mechanism, is what resolved this race (two distinct keys
            # never contend with each other at the reservation step).
            settlement_reservations = (
                verify_session.execute(
                    select(InstallmentIdempotencyKey)
                    .where(InstallmentIdempotencyKey.company_id == company_id)
                    .where(InstallmentIdempotencyKey.operation == "settlement.execute")
                )
                .scalars()
                .all()
            )
            assert len(settlement_reservations) == 1, (
                f"expected exactly 1 settlement.execute reservation, found {len(settlement_reservations)}"
            )
            assert settlement_reservations[0].status == "COMPLETED"
        finally:
            verify_session.close()

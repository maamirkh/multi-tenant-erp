"""[Epic 10, Phase 14, T239] Real-Postgres concurrency test — collection
vs. settlement execution race on the SAME contract. No double-execution:
settlement execution *is* a collection at the full remaining amount
(plan.md §19's "Double settlement" row), so both
``InstallmentCollectionService.record_collection()`` and
``InstallmentSettlementService.execute()`` compete for the exact same
``FOR UPDATE`` lock on ``InstallmentContract``. Whichever acquires it
first fully pays off and auto-completes the contract; the second,
re-reading a now-``COMPLETED`` status post-lock, is rejected by its own
status guard — never both executing, never a torn double-payoff.

Repeated 5 times (fresh contract each repetition) to exercise both lock
orderings under genuine OS thread-scheduling variance, not one
hand-picked outcome.
"""

from __future__ import annotations

import threading
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from modules.accounting.models.ar import ARTransaction
from modules.accounting.models.gl import JournalEntry
from modules.accounting.models.payments import Payment
from modules.installments.exceptions import (
    InstallmentActivationFailedError,
    InstallmentOverCollectionError,
    InstallmentSettlementNotAllowedError,
)
from modules.installments.models.allocation_reference import (
    InstallmentAllocationReference,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
    build_settlement_service,
)
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)

_REPETITIONS = 5


@pytest.fixture
def pg_engine(request: pytest.FixtureRequest):
    pg_url = request.getfixturevalue("pg_test_db")
    alembic_upgrade(pg_url, "072")
    engine = db_engine(pg_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(pg_engine) -> Session:
    session_factory = sessionmaker(bind=pg_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


class TestConcurrentCollectionVsSettlementAtScale:
    def test_five_repetitions_never_double_execute(self, db_session, pg_engine) -> None:
        session_factory = sessionmaker(bind=pg_engine)

        for rep in range(_REPETITIONS):
            ctx = build_active_contract_with_schedule(
                db_session, installment_count=1, installment_amount=Decimal("500.00")
            )
            company_id = ctx["company_id"]
            contract_id = ctx["contract"].id
            bank_account_id = ctx["bank_account"].id
            customer_id = ctx["customer_id"]

            # Non-mutating quote generated up front, exactly as a real
            # client's settlement UI would have obtained it before the
            # race between the two independent user actions begins.
            quote_service = build_settlement_service(db_session)
            quote = quote_service.generate_quote(company_id, contract_id, date.today())
            assert quote.settlement_amount == Decimal("500.00")

            session_a = session_factory()
            session_b = session_factory()
            results: dict[str, tuple[str, object]] = {}

            def _collect(session) -> None:
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
                    results["collection"] = ("success", result)
                except Exception as exc:  # noqa: BLE001 — capturing for assertion
                    session.rollback()
                    results["collection"] = ("error", exc)

            def _settle(session) -> None:
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
                    results["settlement"] = ("success", contract.status)
                except Exception as exc:  # noqa: BLE001 — capturing for assertion
                    session.rollback()
                    results["settlement"] = ("error", exc)

            thread_a = threading.Thread(target=_collect, args=(session_a,))
            thread_b = threading.Thread(target=_settle, args=(session_b,))
            thread_a.start()
            thread_b.start()
            thread_a.join(timeout=30)
            thread_b.join(timeout=30)
            session_a.close()
            session_b.close()

            outcomes = [results["collection"][0], results["settlement"][0]]
            assert outcomes.count("success") == 1, (
                f"repetition {rep}: expected exactly one success, got: {results}"
            )
            assert outcomes.count("error") == 1, f"repetition {rep}: {results}"

            loser_key = (
                "collection" if results["collection"][0] == "error" else "settlement"
            )
            loser_exc = results[loser_key][1]
            if loser_key == "collection":
                assert isinstance(
                    loser_exc,
                    InstallmentOverCollectionError | InstallmentActivationFailedError,
                ), f"repetition {rep}: {results}"
            else:
                assert isinstance(loser_exc, InstallmentSettlementNotAllowedError), (
                    f"repetition {rep}: {results}"
                )

            # No matter which operation won, the durable financial
            # effect is exactly-once, company-wide — never a double
            # execution regardless of which code path got there first.
            verify_session = session_factory()
            try:
                all_refs = (
                    verify_session.execute(
                        select(InstallmentAllocationReference).where(
                            InstallmentAllocationReference.company_id == company_id
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(all_refs) == 1, (
                    f"repetition {rep}: expected exactly 1 allocation reference, "
                    f"found {len(all_refs)}"
                )
                winning_payment_id = all_refs[0].accounting_payment_id

                all_payments = (
                    verify_session.execute(
                        select(Payment)
                        .where(Payment.company_id == company_id)
                        .where(Payment.party_id == customer_id)
                    )
                    .scalars()
                    .all()
                )
                assert len(all_payments) == 1, (
                    f"repetition {rep}: expected exactly 1 Payment, found {len(all_payments)}"
                )
                assert all_payments[0].id == winning_payment_id

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
                    f"repetition {rep}: expected exactly 1 payment-sourced JournalEntry, "
                    f"found {len(all_payment_journal_entries)}"
                )

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
                    f"repetition {rep}: expected exactly 1 payment-sourced ARTransaction, "
                    f"found {len(all_payment_ar_transactions)}"
                )
            finally:
                verify_session.close()

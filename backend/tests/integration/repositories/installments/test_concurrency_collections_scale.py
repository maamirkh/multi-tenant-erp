"""[Epic 10, Phase 14, T237] Real-Postgres concurrency test — simultaneous
collections against the SAME contract from multiple sessions, AT SCALE.
No over-collection under sustained concurrent load (BR-INST-011),
extending Phase 7's ``test_concurrent_collections.py`` two-session proof
to 10 concurrent sessions each attempting to collect the full remaining
balance against a single-installment contract.

Only one attempt may succeed; the other 9 must each be cleanly rejected
(``InstallmentActivationFailedError`` once the winner has already
auto-completed the contract, or ``InstallmentOverCollectionError`` for
any attempt that observes a still-open-but-fully-claimed balance) —
never a partial/torn double-allocation, never more than one Payment/
JournalEntry/ARTransaction/InstallmentAllocationReference created
company-wide, regardless of arrival order under 10-way contention.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Generator
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
)
from modules.installments.models.allocation_reference import (
    InstallmentAllocationReference,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
)
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)

_CONCURRENCY = 10


# This directory (repositories/installments/) has no local conftest.py
# and the repo-root tests/conftest.py's own `db_session` is a DIFFERENT,
# SQLite-capable, savepoint-rollback fixture (test_db_engine-backed) —
# wrong for a genuine multi-connection real-Postgres race. These two
# fixtures shadow that name with the exact real-Postgres pair
# `tests/integration/api/v1/installments/conftest.py` defines, so the
# imported `build_active_contract_with_schedule`/`build_collection_
# service` helpers (which only need a plain `Session`, real Postgres)
# work identically here.
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
def db_session(pg_engine) -> Generator[Session, None, None]:
    session_factory = sessionmaker(bind=pg_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


class TestConcurrentFullAmountCollectionsAtScale:
    def test_ten_concurrent_full_collections_exactly_one_succeeds(
        self, db_session, pg_engine
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        company_id = ctx["company_id"]
        contract_id = ctx["contract"].id
        bank_account_id = ctx["bank_account"].id

        session_factory = sessionmaker(bind=pg_engine)
        sessions = [session_factory() for _ in range(_CONCURRENCY)]
        results: dict[int, tuple[str, object]] = {}

        def _attempt(idx: int, session) -> None:
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
                results[idx] = ("success", result)
            except Exception as exc:  # noqa: BLE001 — capturing for assertion
                session.rollback()
                results[idx] = ("error", exc)

        threads = [
            threading.Thread(target=_attempt, args=(i, sessions[i]))
            for i in range(_CONCURRENCY)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        for s in sessions:
            s.close()

        outcomes = [results[i][0] for i in range(_CONCURRENCY)]
        assert outcomes.count("success") == 1, (
            f"expected exactly one success out of {_CONCURRENCY}, got: {outcomes}"
        )
        assert outcomes.count("error") == _CONCURRENCY - 1

        for i in range(_CONCURRENCY):
            outcome, payload = results[i]
            if outcome != "error":
                continue
            assert isinstance(
                payload,
                InstallmentOverCollectionError | InstallmentActivationFailedError,
            ), f"attempt {i}: unexpected exception type {type(payload)}: {payload}"

        verify_session = session_factory()
        try:
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
                f"expected exactly 1 InstallmentAllocationReference after {_CONCURRENCY}-way "
                f"contention, found {len(all_refs_for_company)}"
            )
            assert all_refs_for_company[0].allocated_amount == Decimal("500.00")
            winning_payment_id = all_refs_for_company[0].accounting_payment_id

            all_payments_for_company = (
                verify_session.execute(
                    select(Payment)
                    .where(Payment.company_id == company_id)
                    .where(Payment.party_id == ctx["customer_id"])
                )
                .scalars()
                .all()
            )
            assert len(all_payments_for_company) == 1, (
                f"expected exactly 1 Payment company-wide, found {len(all_payments_for_company)}"
            )
            assert all_payments_for_company[0].id == winning_payment_id
            assert all_payments_for_company[0].amount_foreign == Decimal("500.00")

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
        finally:
            verify_session.close()

"""[Phase 3] Real-Postgres concurrency test — one-non-terminal-contract-
per-obligation invariant (BR-INST-042/ADR-INST-03).

Covers tasks.md T053. Partial unique indexes are PostgreSQL-specific;
SQLite cannot substitute (plan.md §31/§32). Two genuinely concurrent
DB sessions race to create an ``InstallmentContract`` against the same
``sales_invoice_id`` — the DB partial unique index
(``uq_installment_contracts_one_nonterminal_per_obligation``) must allow
exactly one to succeed, and the loser's raw ``IntegrityError`` must carry
precisely the constraint-name signature
``InstallmentContractService.create_draft()`` catches and translates
into a clean ``ConflictException`` (409) — proving the translation logic
added in T049 actually matches the real error Postgres raises under a
genuine race, not just the sequential/non-race case.
"""

from __future__ import annotations

import threading
import uuid
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from modules.installments.models.contract import InstallmentContract
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)


@pytest.fixture
def pg_engine(request: pytest.FixtureRequest):
    pg_url = request.getfixturevalue("pg_test_db")
    alembic_upgrade(pg_url, "072")
    engine = db_engine(pg_url)
    try:
        yield engine
    finally:
        engine.dispose()


def _draft_contract(
    company_id: uuid.UUID, sales_invoice_id: uuid.UUID, suffix: str
) -> InstallmentContract:
    return InstallmentContract(
        company_id=company_id,
        contract_number=f"IC-2026-{suffix}",
        customer_id=uuid.uuid4(),
        sales_invoice_id=sales_invoice_id,
        contract_date="2026-01-01",
        principal_amount=Decimal("1000.00"),
        down_payment_amount=Decimal("100.00"),
        markup_amount=Decimal("0"),
        contractual_total=Decimal("1000.00"),
        installment_count=12,
        frequency="MONTHLY",
        first_due_date="2026-02-01",
        maturity_date="2027-01-01",
        currency_code="USD",
        status="DRAFT",
        terms_snapshot={"note": "race-test fixture"},
    )


class TestOneNonTerminalContractPerObligationRace:
    def test_concurrent_draft_creation_exactly_one_succeeds(self, pg_engine) -> None:
        company_id = uuid.uuid4()
        sales_invoice_id = uuid.uuid4()
        session_factory = sessionmaker(bind=pg_engine)

        session_a = session_factory()
        session_b = session_factory()

        # No manual barrier between INSERT and COMMIT: Postgres's own
        # row-level lock on the unique index is what serializes the two
        # sessions correctly. Whichever session's INSERT reaches Postgres
        # first proceeds to commit; the second session's INSERT blocks at
        # the database level until the first resolves, then immediately
        # raises IntegrityError on unblocking. A manual barrier placed
        # between a pre-flushed INSERT and the commit would risk a
        # deadlock (the second session could block inside flush() before
        # ever reaching the barrier, while the first waits at the barrier
        # for the second) — so each thread does INSERT+COMMIT as a single
        # uninterrupted step, with both threads simply started back-to-back.
        results: dict[str, object] = {}

        def _attempt(session, suffix: str, key: str) -> None:
            contract = _draft_contract(company_id, sales_invoice_id, suffix)
            session.add(contract)
            try:
                session.commit()
                results[key] = ("success", contract.id)
            except IntegrityError as exc:
                session.rollback()
                results[key] = ("integrity_error", exc)

        thread_a = threading.Thread(target=_attempt, args=(session_a, "000001", "a"))
        thread_b = threading.Thread(target=_attempt, args=(session_b, "000002", "b"))
        thread_a.start()
        thread_b.start()
        thread_a.join(timeout=15)
        thread_b.join(timeout=15)

        session_a.close()
        session_b.close()

        outcomes = [results["a"][0], results["b"][0]]
        assert (
            outcomes.count("success") == 1
        ), f"Expected exactly one success, got: {results}"
        assert (
            outcomes.count("integrity_error") == 1
        ), f"Expected exactly one IntegrityError, got: {results}"

        loser_key = "a" if results["a"][0] == "integrity_error" else "b"
        loser_exc: IntegrityError = results[loser_key][1]

        # The loser's error must carry exactly the constraint-name
        # signature InstallmentContractService.create_draft() detects
        # and translates into a clean 409 ConflictException.
        diag = getattr(getattr(loser_exc, "orig", None), "diag", None)
        constraint_name = getattr(diag, "constraint_name", None)
        assert (
            constraint_name == "uq_installment_contracts_one_nonterminal_per_obligation"
        ), f"Unexpected constraint name: {constraint_name!r} (full error: {loser_exc})"

        # Verify with a fresh session that exactly one row exists for
        # this (company_id, sales_invoice_id).
        verify_session = session_factory()
        try:
            rows = (
                verify_session.query(InstallmentContract)
                .filter(InstallmentContract.company_id == company_id)
                .filter(InstallmentContract.sales_invoice_id == sales_invoice_id)
                .all()
            )
            assert len(rows) == 1
        finally:
            verify_session.close()

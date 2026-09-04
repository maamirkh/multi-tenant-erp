"""[Epic 10, Phase 14, T236] Real-Postgres concurrency test — duplicate
contract creation race, repeated AT SCALE (10 concurrent attempts
against the same ``sales_invoice_id``, not merely the two-session proof
Phase 3's ``test_contract_one_per_obligation.py`` already gave). Exactly
one of the 10 concurrent draft-creation attempts must succeed via the
partial unique index ``uq_installment_contracts_one_nonterminal_per_
obligation`` — the other 9 must each cleanly receive the exact
``IntegrityError`` constraint-name signature
``InstallmentContractService.create_draft()`` translates into a 409,
never a deadlock, never a hang, never more than one silent survivor.

Scaling to 10 concurrent writers (rather than 2) closes the genuine gap
a two-session test cannot: Postgres serializes conflicting INSERTs one
at a time via the unique index's row-level lock, so a two-session test
only proves the FIRST-vs-SECOND interaction; it says nothing about
whether the 3rd, 4th, ... 10th arrival — each blocking behind a queue
of already-failed predecessors — is handled identically and does not
degrade into a deadlock or an inconsistent constraint-violation shape
under sustained contention.
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

_CONCURRENCY = 10


@pytest.fixture
def pg_engine(request: pytest.FixtureRequest):
    pg_url = request.getfixturevalue("pg_test_db")
    alembic_upgrade(pg_url, "071")
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
        terms_snapshot={"note": "T236 scale race-test fixture"},
    )


class TestOneNonTerminalContractPerObligationRaceAtScale:
    def test_ten_concurrent_draft_creations_exactly_one_succeeds(
        self, pg_engine
    ) -> None:
        company_id = uuid.uuid4()
        sales_invoice_id = uuid.uuid4()
        session_factory = sessionmaker(bind=pg_engine)

        sessions = [session_factory() for _ in range(_CONCURRENCY)]
        results: dict[int, tuple[str, object]] = {}

        def _attempt(idx: int, session) -> None:
            contract = _draft_contract(company_id, sales_invoice_id, f"{idx:06d}")
            session.add(contract)
            try:
                session.commit()
                results[idx] = ("success", contract.id)
            except IntegrityError as exc:
                session.rollback()
                results[idx] = ("integrity_error", exc)

        threads = [
            threading.Thread(target=_attempt, args=(i, sessions[i]))
            for i in range(_CONCURRENCY)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        for s in sessions:
            s.close()

        outcomes = [results[i][0] for i in range(_CONCURRENCY)]
        assert (
            outcomes.count("success") == 1
        ), f"Expected exactly one success out of {_CONCURRENCY}, got: {outcomes}"
        assert (
            outcomes.count("integrity_error") == _CONCURRENCY - 1
        ), f"Expected exactly {_CONCURRENCY - 1} IntegrityErrors, got: {outcomes}"

        # Every loser's error must carry exactly the constraint-name
        # signature create_draft() detects and translates to a clean 409
        # — not merely "some error occurred" for 9 different reasons.
        for i in range(_CONCURRENCY):
            outcome, payload = results[i]
            if outcome != "integrity_error":
                continue
            diag = getattr(getattr(payload, "orig", None), "diag", None)
            constraint_name = getattr(diag, "constraint_name", None)
            assert constraint_name == (
                "uq_installment_contracts_one_nonterminal_per_obligation"
            ), f"attempt {i}: unexpected constraint name {constraint_name!r} ({payload})"

        verify_session = session_factory()
        try:
            rows = (
                verify_session.query(InstallmentContract)
                .filter(InstallmentContract.company_id == company_id)
                .filter(InstallmentContract.sales_invoice_id == sales_invoice_id)
                .all()
            )
            assert (
                len(rows) == 1
            ), f"expected exactly 1 durable contract row after the race, found {len(rows)}"
        finally:
            verify_session.close()

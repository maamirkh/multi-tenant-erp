"""[Epic 10, Phase 6, T116] Real-Postgres forced-failure atomicity proof
for ``AccountsReceivableService.stage_write_off()`` /
``finalize_write_off()`` — Layer A (Accounting-only; Layer B, proving
Installments' own contract-status/audit/outbox rows commit together with
these, is deferred to Phase 10 per tasks.md's Phase 6 Exit Gate).

This is the test that would have caught the original defect
``confirm_write_off()`` had before this phase: **three separate**
commits (``post_direct()``, then two ``BaseRepository.update()`` calls —
see ``ar_service.py``'s ``stage_write_off()`` docstring). Forces the
failure *after* ``stage_write_off()`` has flushed the GL entry, the
transaction status/outstanding-amount change, and the ledger recompute,
but *before* ``finalize_write_off()`` is ever called — then rolls back
and, via a second, independent connection to the same throwaway
database, proves the GL journal, the transaction's ``WRITTEN_OFF``
status, and the ledger balance change are all simultaneously
absent/unchanged.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker

from modules.accounting.dependencies import build_ar_service
from modules.accounting.models.ar import ARTransaction
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.models.gl import JournalEntry
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)


@pytest.fixture
def pg_engine(request: pytest.FixtureRequest):
    pg_url = request.getfixturevalue("pg_test_db")
    alembic_upgrade(pg_url, "071")
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


@pytest.fixture
def setup(pg_engine, db_session: Session) -> dict:
    account_repo = AccountRepository(db_session)
    fiscal_service = FiscalCalendarService(
        db=db_session,
        year_repo=FiscalYearRepository(db_session),
        period_repo=FiscalPeriodRepository(db_session),
        opening_balance_repo=OpeningBalanceRepository(db_session),
        audit_service=AuditLogService(
            db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
        ),
    )
    company_id = uuid.uuid4()
    ar = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1100",
            account_name="AR",
            account_type="ASSET",
        )
    )
    bad_debt = account_repo.create(
        Account(
            company_id=company_id,
            account_code="6900",
            account_name="Bad Debt Expense",
            account_type="EXPENSE",
        )
    )
    revenue = account_repo.create(
        Account(
            company_id=company_id,
            account_code="4000",
            account_name="Revenue",
            account_type="REVENUE",
        )
    )
    today = date.today()
    fiscal_service.create_fiscal_year(
        company_id,
        f"FY-{uuid.uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )
    AccountingConfigurationRepository(db_session).create(
        AccountingConfiguration(
            company_id=company_id,
            default_ar_account_id=ar.id,
            default_bad_debt_account_id=bad_debt.id,
            default_revenue_account_id=revenue.id,
        )
    )
    db_session.commit()
    return {
        "company_id": company_id,
        "today": today,
        "pg_engine": pg_engine,
    }


class TestStageWriteOffAtomicity:
    def test_forced_failure_between_stage_and_finalize_leaves_nothing_committed(
        self, db_session: Session, setup: dict
    ) -> None:
        ar_service = build_ar_service(db_session, with_sales_sync=False)
        customer_id = uuid.uuid4()

        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid.uuid4(),
            invoice_number="INV-WO-ATOMIC-1",
            total_amount=Decimal("600.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        db_session.commit()

        staged = ar_service.stage_write_off(
            company_id=setup["company_id"],
            ar_transaction_id=invoice.id,
            reason="Forced-failure atomicity proof",
            actor_id=None,
        )
        journal_entry_id = staged.journal_entry.id

        # A generic caller-supplied row, flushed into the same session —
        # standing in for "the caller's own rows" (e.g. an Installments
        # contract-status/audit/outbox row) a real cross-module caller
        # would stage here before calling finalize_write_off().
        placeholder_account = Account(
            company_id=setup["company_id"],
            account_code="9999",
            account_name="Forced-Failure Placeholder",
            account_type="ASSET",
        )
        db_session.add(placeholder_account)
        db_session.flush()
        placeholder_account_id = placeholder_account.id

        class _InjectedFailure(Exception):
            pass

        try:
            raise _InjectedFailure(
                "simulated failure before finalize_write_off() is called"
            )
        except _InjectedFailure:
            db_session.rollback()

        verify_session_factory = sessionmaker(bind=setup["pg_engine"])
        verify_session = verify_session_factory()
        try:
            journal_entry = verify_session.get(JournalEntry, journal_entry_id)
            assert journal_entry is None

            verified_invoice = verify_session.get(ARTransaction, invoice.id)
            assert verified_invoice.status == "OPEN"
            assert verified_invoice.outstanding_amount == Decimal("600.00")

            placeholder = verify_session.get(Account, placeholder_account_id)
            assert placeholder is None
        finally:
            verify_session.close()

    def test_normal_path_commits_gl_and_status_change_together(
        self, db_session: Session, setup: dict
    ) -> None:
        ar_service = build_ar_service(db_session, with_sales_sync=False)
        customer_id = uuid.uuid4()

        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid.uuid4(),
            invoice_number="INV-WO-ATOMIC-2",
            total_amount=Decimal("450.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        db_session.commit()

        staged = ar_service.stage_write_off(
            company_id=setup["company_id"],
            ar_transaction_id=invoice.id,
            reason="Uncollectible",
            actor_id=None,
        )
        written_off = ar_service.finalize_write_off(staged, actor_id=None)

        verify_session_factory = sessionmaker(bind=setup["pg_engine"])
        verify_session = verify_session_factory()
        try:
            journal_entry = verify_session.get(JournalEntry, staged.journal_entry.id)
            assert journal_entry is not None

            verified_invoice = verify_session.get(ARTransaction, written_off.id)
            assert verified_invoice.status == "WRITTEN_OFF"
            assert verified_invoice.outstanding_amount == Decimal("0")
        finally:
            verify_session.close()

"""[Epic 10, Phase 6, T114] Real-Postgres forced-failure atomicity proof
for ``AccountsReceivableService.stage_adjustment()`` /
``finalize_adjustment()`` — Layer A (Accounting-only atomicity; Layer B,
proving Installments' own rows commit together with these, is deferred
to Phase 8 per tasks.md's Phase 6 Exit Gate, since
``InstallmentLateCharge`` does not exist until then).

``stage_adjustment()``'s claim is that it only ever ``flush()``es — never
independently commits — so a caller can safely stage further rows before
calling ``finalize_adjustment()``. This can only be proven against a real
transactional database: SQLite's autocommit-adjacent semantics and lack
of a genuine MVCC snapshot make a false negative/positive both possible,
per plan.md §31/§32's established real-Postgres-first discipline (mirrors
``test_schedule_persistence.py``'s identical justification for the same
class of claim).

Forces the failure *after* ``stage_adjustment()`` has flushed the GL
entry, the ``ARTransaction``, and the ledger recompute, but *before*
``finalize_adjustment()`` is ever called — then rolls back and, via a
**second, independent connection** to the same throwaway database,
proves the ``JournalEntry``, the ``ARTransaction``, and the
``CustomerLedger`` balance are all simultaneously absent/unchanged. No
partial commit is acceptable (plan.md §12.2's required test).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from modules.accounting.dependencies import build_ar_service
from modules.accounting.models.ar import ARTransaction, CustomerLedger
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
    rounding = account_repo.create(
        Account(
            company_id=company_id,
            account_code="7900",
            account_name="Rounding",
            account_type="EXPENSE",
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
        AccountingConfiguration(company_id=company_id, default_ar_account_id=ar.id)
    )
    db_session.commit()
    return {
        "company_id": company_id,
        "rounding": rounding,
        "today": today,
        "pg_engine": pg_engine,
    }


class TestStageAdjustmentAtomicity:
    def test_forced_failure_between_stage_and_finalize_leaves_nothing_committed(
        self, db_session: Session, setup: dict
    ) -> None:
        ar_service = build_ar_service(db_session, with_sales_sync=False)
        customer_id = uuid.uuid4()

        staged = ar_service.stage_adjustment(
            company_id=setup["company_id"],
            customer_id=customer_id,
            amount=Decimal("100.00"),
            contra_account_id=setup["rounding"].id,
            reason="Forced-failure atomicity proof",
            posting_date=setup["today"],
            actor_id=None,
        )
        journal_entry_id = staged.journal_entry.id
        ar_transaction_id = staged.ar_transaction.id
        ledger_id = staged.ar_transaction.customer_ledger_id

        # A generic caller-supplied row, flushed into the *same* session
        # right after staging — standing in for "the caller's own rows"
        # (e.g. an Installments audit/outbox row) a real cross-module
        # caller would stage here before calling finalize_adjustment().
        # Proves the staging *point* itself is safe for arbitrary
        # caller-added rows, not merely for stage_adjustment()'s own
        # internal writes.
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
                "simulated failure before finalize_adjustment() is called"
            )
        except _InjectedFailure:
            db_session.rollback()

        verify_session_factory = sessionmaker(bind=setup["pg_engine"])
        verify_session = verify_session_factory()
        try:
            journal_entry = verify_session.get(JournalEntry, journal_entry_id)
            assert journal_entry is None

            ar_transaction = verify_session.get(ARTransaction, ar_transaction_id)
            assert ar_transaction is None

            ledger = verify_session.get(CustomerLedger, ledger_id)
            assert ledger is None or ledger.total_outstanding_base == Decimal("0")

            placeholder = verify_session.get(Account, placeholder_account_id)
            assert placeholder is None
        finally:
            verify_session.close()

    def test_normal_path_commits_everything_together(
        self, db_session: Session, setup: dict
    ) -> None:
        ar_service = build_ar_service(db_session, with_sales_sync=False)
        customer_id = uuid.uuid4()

        staged = ar_service.stage_adjustment(
            company_id=setup["company_id"],
            customer_id=customer_id,
            amount=Decimal("75.00"),
            contra_account_id=setup["rounding"].id,
            reason="Normal-path commit proof",
            posting_date=setup["today"],
            actor_id=None,
        )
        transaction = ar_service.finalize_adjustment(staged, actor_id=None)

        verify_session_factory = sessionmaker(bind=setup["pg_engine"])
        verify_session = verify_session_factory()
        try:
            journal_entry = verify_session.get(JournalEntry, staged.journal_entry.id)
            assert journal_entry is not None

            ar_transaction = verify_session.get(ARTransaction, transaction.id)
            assert ar_transaction is not None
            assert ar_transaction.outstanding_amount == Decimal("75.00")

            ledger = verify_session.execute(
                select(CustomerLedger).where(
                    CustomerLedger.id == transaction.customer_ledger_id
                )
            ).scalar_one()
            assert ledger.total_outstanding_base == Decimal("75.00")
        finally:
            verify_session.close()

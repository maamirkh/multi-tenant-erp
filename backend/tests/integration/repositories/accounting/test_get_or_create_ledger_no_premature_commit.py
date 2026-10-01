"""[Epic 10, Phase 6 verification follow-up] Real-Postgres regression
guard for a defect found during Phase 6 hard-gate verification:
``AccountsReceivableService.get_or_create_ledger()`` used to call
``CustomerLedgerRepository.create()`` — which inherits
``BaseRepository.create()``'s internal ``db.commit()``. Because
``get_or_create_ledger()`` is ``stage_adjustment()``'s first statement,
this committed a new ``CustomerLedger`` (and anything else already
flushed in the same session by a caller) *before* any validation ran,
for any customer without a pre-existing ledger — the common case.

The original T114 atomicity test did not catch this: its assertion
(``ledger is None or ledger.total_outstanding_base == Decimal("0")``)
accepted a surviving-but-zero-balance ledger row, which is exactly what
a premature ``get_or_create_ledger()`` commit produces (the ledger
commits with its default zero balance; only the *later* balance
recompute is what gets rolled back). This file exists specifically so
that loophole can never mask a regression again — every assertion here
is a strict, unconditional absence check.

Fix: ``get_or_create_ledger()`` now uses ``db.add()``+``db.flush()``
directly, mirroring ``PaymentService._get_or_create_customer_ledger()``'s
already-correct pattern (never a committing repository call).
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.orm import Session, sessionmaker

from modules.accounting.dependencies import build_ar_service
from modules.accounting.exceptions import PostingValidationError
from modules.accounting.models.ar import CustomerLedger
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
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


@pytest.fixture
def setup(pg_engine, db_session: Session) -> dict[str, Any]:
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
    db_session.commit()
    return {
        "company_id": company_id,
        "rounding": rounding,
        "today": today,
        "pg_engine": pg_engine,
    }


class TestGetOrCreateLedgerNoPrematureCommit:
    def test_missing_config_failure_does_not_strand_a_committed_ledger(
        self, db_session: Session, setup: dict[str, Any]
    ) -> None:
        """No ``AccountingConfiguration`` row exists for this company at
        all, so ``stage_adjustment()`` raises ``PostingValidationError``
        immediately after ``get_or_create_ledger()`` runs — the exact
        sequence that previously left a committed, stranded
        ``CustomerLedger`` row behind."""
        ar_service = build_ar_service(db_session, with_sales_sync=False)
        customer_id = uuid.uuid4()

        with pytest.raises(PostingValidationError):
            ar_service.stage_adjustment(
                company_id=setup["company_id"],
                customer_id=customer_id,
                amount=Decimal("10.00"),
                contra_account_id=setup["rounding"].id,
                reason="regression guard — missing config",
                posting_date=setup["today"],
                actor_id=None,
            )
        db_session.rollback()

        verify_session_factory = sessionmaker(bind=setup["pg_engine"])
        verify_session = verify_session_factory()
        try:
            ledger = (
                verify_session.query(CustomerLedger)
                .filter_by(company_id=setup["company_id"], customer_id=customer_id)
                .one_or_none()
            )
            assert ledger is None
        finally:
            verify_session.close()

    def test_caller_staged_row_is_not_stranded_by_a_new_ledger_creation(
        self, db_session: Session, setup: dict[str, Any]
    ) -> None:
        """A generic caller-staged row (standing in for an Installments
        row) flushed into the session *before* ``stage_adjustment()`` is
        called must not survive a later rollback merely because
        ``get_or_create_ledger()`` needed to create a new ledger for
        this first-time customer."""
        ar_service = build_ar_service(db_session, with_sales_sync=False)
        customer_id = uuid.uuid4()

        caller_placeholder = Account(
            company_id=setup["company_id"],
            account_code="9996",
            account_name="Caller Placeholder",
            account_type="ASSET",
        )
        db_session.add(caller_placeholder)
        db_session.flush()
        caller_placeholder_id = caller_placeholder.id

        with pytest.raises(PostingValidationError):
            ar_service.stage_adjustment(
                company_id=setup["company_id"],
                customer_id=customer_id,
                amount=Decimal("10.00"),
                contra_account_id=setup["rounding"].id,
                reason="regression guard — caller row must not strand",
                posting_date=setup["today"],
                actor_id=None,
            )
        db_session.rollback()

        verify_session_factory = sessionmaker(bind=setup["pg_engine"])
        verify_session = verify_session_factory()
        try:
            ledger = (
                verify_session.query(CustomerLedger)
                .filter_by(company_id=setup["company_id"], customer_id=customer_id)
                .one_or_none()
            )
            assert ledger is None

            placeholder = verify_session.get(Account, caller_placeholder_id)
            assert placeholder is None
        finally:
            verify_session.close()

    def test_first_time_customer_ledger_still_created_and_committed_on_success(
        self, db_session: Session, setup: dict[str, Any]
    ) -> None:
        """Confirms the fix did not break the happy path: a first-time
        customer's ledger is still created, and still ends up committed,
        once ``finalize_adjustment()`` actually runs."""
        ar_service = build_ar_service(db_session, with_sales_sync=False)
        customer_id = uuid.uuid4()

        config_repo = AccountingConfigurationRepository(db_session)
        account_repo = AccountRepository(db_session)
        ar_account = account_repo.create(
            Account(
                company_id=setup["company_id"],
                account_code="1100",
                account_name="AR",
                account_type="ASSET",
            )
        )
        config_repo.create(
            AccountingConfiguration(
                company_id=setup["company_id"], default_ar_account_id=ar_account.id
            )
        )
        db_session.commit()

        staged = ar_service.stage_adjustment(
            company_id=setup["company_id"],
            customer_id=customer_id,
            amount=Decimal("25.00"),
            contra_account_id=setup["rounding"].id,
            reason="regression guard — happy path unaffected",
            posting_date=setup["today"],
            actor_id=None,
        )
        transaction = ar_service.finalize_adjustment(staged, actor_id=None)

        verify_session_factory = sessionmaker(bind=setup["pg_engine"])
        verify_session = verify_session_factory()
        try:
            ledger = verify_session.get(CustomerLedger, transaction.customer_ledger_id)
            assert ledger is not None
            assert ledger.total_outstanding_base == Decimal("25.00")
        finally:
            verify_session.close()

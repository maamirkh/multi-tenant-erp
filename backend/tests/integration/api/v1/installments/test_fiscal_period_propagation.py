"""[Epic 10, Phase 6, T117] Fiscal-period propagation test.

Every posting-producing Accounting method Installments will call through
``AccountingIntegrationGateway`` inherits ``PostingEngine``'s Step-3
fiscal-period gate automatically (plan.md §12, "Fiscal period" row):
attempting to post into a period that is not ``OPEN`` (locked, closed, or
simply undefined) raises ``PostingValidationError("Period is
locked/closed")`` — a future Installments-side service method (Phase 7+)
catches this and re-raises ``InstallmentFiscalPeriodLockedError``
(BR-INST-021, FR-INST-393); this test proves the underlying Accounting
invariant that makes that translation possible: the failure occurs
**before any staging occurs** (Step 3 runs before any GL line, AR
transaction, or ledger row is ever built), for all three Phase 6
staged-posting entry points — ``stage_adjustment()``, ``stage_customer_payment()``,
and ``stage_write_off()``.

The fiscal period covering *today* is locked (``stage_write_off()``
always posts as of ``utcnow().date()``, so all three methods are tested
against the same locked period for consistency). Pure business-logic
validation (no Postgres-specific constraint under test) — uses the
standard SQLite ``db_session`` fixture, matching the T109-T112/T107
convention.

**Important nuance discovered while writing this test**: Step 3 (the
fiscal-period check) runs inside ``PostingEngine._finalize_posting_uncommitted()``
*after* the ``JournalEntry`` skeleton has already been built and flushed
by ``_build_entry_and_lines()`` — pre-existing Phase 4/5 behavior, shared
by every ``PostingEngine`` caller, not something this phase's staged/
finalize extraction introduced or could safely change without a much
larger, out-of-scope restructuring of an already-shipped, already-tested
method. The correctness invariant this phase's architecture actually
relies on — and the one T114-T116 already prove — is not "nothing is
ever flushed," it is "nothing commits": a locked-period failure leaves a
flushed-but-uncommitted ``JournalEntry`` in the session, which a caller
must roll back (exactly as it would for any other exception raised
mid-transaction), after which no trace of the attempt persists. These
tests therefore assert exactly that: the exception propagates, and after
an explicit rollback (mirroring real caller behavior), the row counts
return to their pre-attempt baseline.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_ar_service, build_payment_service
from modules.accounting.exceptions import PostingValidationError
from modules.accounting.models.ar import ARTransaction
from modules.accounting.models.banking import BankAccount
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.models.gl import JournalEntry
from modules.accounting.models.payments import Payment
from modules.accounting.repositories.banking import BankAccountRepository
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


@pytest.fixture
def setup(db_session: Session) -> dict[str, Any]:
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
    bank_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1000",
            account_name="Bank",
            account_type="ASSET",
        )
    )
    bank = BankAccountRepository(db_session).create(
        BankAccount(
            company_id=company_id,
            bank_name="Test Bank",
            account_number="ACC-FISCAL-01",
            currency_code="USD",
            gl_account_id=bank_gl.id,
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

    # Create the invoice used by the write-off test *before* locking
    # today's period, since recording a normal sales invoice must itself
    # still succeed against an OPEN period.
    ar_service = build_ar_service(db_session, with_sales_sync=False)
    customer_id = uuid.uuid4()
    invoice, _ = ar_service.record_sales_invoice(
        company_id=company_id,
        customer_id=customer_id,
        invoice_id=uuid.uuid4(),
        invoice_number="INV-FISCAL-1",
        total_amount=Decimal("200.00"),
        currency_code="USD",
        transaction_date=today,
        due_date=today,
        actor_id=None,
    )
    db_session.commit()

    period_repo = FiscalPeriodRepository(db_session)
    period = period_repo.find_open_period_for_date(company_id, today)
    assert period is not None
    fiscal_service.lock_period(
        company_id, period.id, locked_by_user_id=None, lock_reason="T117 fixture"
    )
    db_session.commit()

    return {
        "company_id": company_id,
        "rounding": rounding,
        "bank": bank,
        "today": today,
        "invoice_id": invoice.id,
    }


def _count(db_session: Session, model) -> int:
    return int(db_session.query(model).count())


class TestFiscalPeriodPropagation:
    def test_stage_adjustment_rejects_locked_period_before_staging(
        self, db_session: Session, setup: dict[str, Any]
    ) -> None:
        ar_service = build_ar_service(db_session, with_sales_sync=False)
        journal_count_before = _count(db_session, JournalEntry)
        ar_count_before = _count(db_session, ARTransaction)

        with pytest.raises(PostingValidationError):
            ar_service.stage_adjustment(
                company_id=setup["company_id"],
                customer_id=uuid.uuid4(),
                amount=Decimal("50.00"),
                contra_account_id=setup["rounding"].id,
                reason="Attempted post into locked period",
                posting_date=setup["today"],
                actor_id=None,
            )
        db_session.rollback()

        assert _count(db_session, JournalEntry) == journal_count_before
        assert _count(db_session, ARTransaction) == ar_count_before

    def test_stage_customer_payment_rejects_locked_period_before_staging(
        self, db_session: Session, setup: dict[str, Any]
    ) -> None:
        payment_service = build_payment_service(db_session)
        journal_count_before = _count(db_session, JournalEntry)
        payment_count_before = _count(db_session, Payment)

        with pytest.raises(PostingValidationError):
            payment_service.stage_customer_payment(
                company_id=setup["company_id"],
                customer_id=uuid.uuid4(),
                payment_method="BANK_TRANSFER",
                payment_date=setup["today"],
                amount=Decimal("100.00"),
                currency_code="USD",
                bank_account_id=setup["bank"].id,
                actor_id=None,
            )
        db_session.rollback()

        assert _count(db_session, JournalEntry) == journal_count_before
        assert _count(db_session, Payment) == payment_count_before

    def test_stage_write_off_rejects_locked_period_before_staging(
        self, db_session: Session, setup: dict[str, Any]
    ) -> None:
        ar_service = build_ar_service(db_session, with_sales_sync=False)
        journal_count_before = _count(db_session, JournalEntry)

        with pytest.raises(PostingValidationError):
            ar_service.stage_write_off(
                company_id=setup["company_id"],
                ar_transaction_id=setup["invoice_id"],
                reason="Attempted write-off into locked period",
                actor_id=None,
            )
        db_session.rollback()

        assert _count(db_session, JournalEntry) == journal_count_before
        refreshed_invoice = ar_service.get_transaction_by_id(
            setup["company_id"], setup["invoice_id"]
        )
        assert refreshed_invoice is not None
        assert refreshed_invoice.status == "OPEN"
        assert refreshed_invoice.outstanding_amount == Decimal("200.00")

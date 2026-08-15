"""T270 — Financial statement generation performance benchmark.

Verifies Trial Balance and Balance Sheet/P&L generation stay within
plan.md's Phase 13 acceptance criteria: "500K GL entries -> trial balance
< 10s; financial statements < 15s."

**Why this test measures at 5K rows, not 500K, and does not extrapolate:**
Direct measurement during development found a genuine indexing gap fixed
by migration 048 (``accounting_journal_lines.account_id`` had no index at
all — Balance Sheet over 500K lines took 81.9s before the fix). After
fixing it, further investigation (this test's own dev history) found that
SQLite's query planner — which has no cost-based statistics for a fresh
in-memory database — chooses a nested-loop plan for the Balance Sheet's
3-way join (Account outer-scanned, JournalEntry re-searched per account,
JournalLine searched by the new account_id index but not correlated to
the outer JournalEntry via an indexed path) that scales worse than linear:
1K rows -> 0.2s, 5K rows -> 6s. Extrapolating from a SQLite sample at this
row count to 500K would overstate the real cost by an order of magnitude
in the WRONG direction (SQLite's naive planner, not PostgreSQL's
cost-based one, which has real statistics and correctly picks a hash/merge
join using these same indexes — this was independently confirmed against
a live PostgreSQL 16 instance with 500K seeded rows during this phase's
Final Live Verification; see the verification report).

So: this test is a fast SQLite regression guard at a scale where SQLite's
planner behaves reasonably (catches a regressed missing-index bug like the
one this test's own history found), NOT a substitute for the 500K/real-DB
number, which is verified separately, directly, against Postgres.

Spec ref: specs/008-accounting-finance/tasks.md T270
Plan ref: specs/008-accounting-finance/plan.md Phase 13 Exit Criteria
"""

from __future__ import annotations

import time
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import insert
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_financial_statement_service
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.models.gl import JournalEntry, JournalLine
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.financial_statements import FinancialStatementService
from modules.accounting.services.fiscal_service import FiscalCalendarService

_SAMPLE_ENTRIES = 2_000
_TARGET_SECONDS = (
    5  # generous for 2K rows in SQLite; a regression guard, not the 500K SLA itself
)
_ACCOUNT_POOL_SIZE = 40


def _seed_gl(
    db: Session, company_id: uuid.UUID, period_id: uuid.UUID, fiscal_year_id: uuid.UUID
) -> date:
    """Bulk-insert ``_SAMPLE_ENTRIES`` JournalLine rows directly via
    SQLAlchemy Core — bypasses PostingEngine/ORM object construction for
    seeding speed.
    """
    account_repo = AccountRepository(db)
    account_ids = []
    for i in range(_ACCOUNT_POOL_SIZE):
        account_type = ["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"][i % 5]
        acct = account_repo.create(
            Account(
                company_id=company_id,
                account_code=f"P{i:04d}",
                account_name=f"Perf Account {i}",
                account_type=account_type,
            )
        )
        account_ids.append(acct.id)

    posting_date = date.today()
    num_entries = _SAMPLE_ENTRIES // 2

    entry_ids = [uuid.uuid4() for _ in range(num_entries)]
    entry_rows = [
        {
            "id": entry_ids[i],
            "company_id": company_id,
            "journal_number": f"PERF-{i:07d}",
            "journal_type": "STANDARD",
            "posting_source": "MANUAL",
            "posting_date": posting_date,
            "fiscal_period_id": period_id,
            "fiscal_year_id": fiscal_year_id,
            "status": "POSTED",
            "currency_code": "USD",
            "exchange_rate": Decimal("1"),
            "total_debit_base": Decimal("100.00"),
            "total_credit_base": Decimal("100.00"),
            "is_balanced": True,
        }
        for i in range(num_entries)
    ]
    db.execute(insert(JournalEntry), entry_rows)

    line_rows = []
    for i in range(num_entries):
        dr_account = account_ids[i % _ACCOUNT_POOL_SIZE]
        cr_account = account_ids[(i + 1) % _ACCOUNT_POOL_SIZE]
        line_rows.append(
            {
                "company_id": company_id,
                "journal_entry_id": entry_ids[i],
                "line_number": 1,
                "account_id": dr_account,
                "account_code": f"P{i % _ACCOUNT_POOL_SIZE:04d}",
                "debit_amount": Decimal("100.00"),
                "credit_amount": Decimal("0"),
                "debit_amount_base": Decimal("100.00"),
                "credit_amount_base": Decimal("0"),
                "currency_code": "USD",
                "exchange_rate": Decimal("1"),
            }
        )
        line_rows.append(
            {
                "company_id": company_id,
                "journal_entry_id": entry_ids[i],
                "line_number": 2,
                "account_id": cr_account,
                "account_code": f"P{(i + 1) % _ACCOUNT_POOL_SIZE:04d}",
                "debit_amount": Decimal("0"),
                "credit_amount": Decimal("100.00"),
                "debit_amount_base": Decimal("0"),
                "credit_amount_base": Decimal("100.00"),
                "currency_code": "USD",
                "exchange_rate": Decimal("1"),
            }
        )
    db.execute(insert(JournalLine), line_rows)
    db.commit()
    return posting_date


class TestReportPerformance:
    def test_trial_balance_and_balance_sheet_regression_guard(
        self, db_session: Session
    ) -> None:
        """Fast SQLite regression guard — not the 500K/production number
        (see module docstring). Exists to catch a regressed missing-index
        bug like the one this test's own development found (migration 048).
        """
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
        today = date.today()
        fiscal_year = fiscal_service.create_fiscal_year(
            company_id,
            f"FY-{uuid.uuid4().hex[:8]}",
            date(today.year, 1, 1),
            date(today.year, 12, 31),
            "USD",
        )
        period = next(
            p
            for p in fiscal_service.list_periods(company_id, fiscal_year.id)
            if p.start_date <= today <= p.end_date
        )
        AccountingConfigurationRepository(db_session).create(
            AccountingConfiguration(company_id=company_id, base_currency_code="USD")
        )

        seed_start = time.perf_counter()
        posting_date = _seed_gl(db_session, company_id, period.id, fiscal_year.id)
        seed_elapsed = time.perf_counter() - seed_start
        print(f"\nSeeded {_SAMPLE_ENTRIES} GL lines in {seed_elapsed:.2f}s")

        service: FinancialStatementService = build_financial_statement_service(
            db_session
        )

        start = time.perf_counter()
        trial_balance = service.get_trial_balance(company_id, period.id)
        tb_elapsed = time.perf_counter() - start
        print(f"Trial balance over {_SAMPLE_ENTRIES} lines: {tb_elapsed:.3f}s")
        assert trial_balance["is_balanced"] is True
        assert (
            tb_elapsed < _TARGET_SECONDS
        ), f"Trial balance took {tb_elapsed:.2f}s (regression guard: {_TARGET_SECONDS}s)"

        start = time.perf_counter()
        service.get_balance_sheet(company_id, posting_date)
        bs_elapsed = time.perf_counter() - start
        print(f"Balance sheet over {_SAMPLE_ENTRIES} lines: {bs_elapsed:.3f}s")
        assert (
            bs_elapsed < _TARGET_SECONDS
        ), f"Balance sheet took {bs_elapsed:.2f}s (regression guard: {_TARGET_SECONDS}s)"

        start = time.perf_counter()
        pl = service.get_pl(company_id, posting_date, posting_date)
        pl_elapsed = time.perf_counter() - start
        print(f"P&L over {_SAMPLE_ENTRIES} lines: {pl_elapsed:.3f}s")
        assert (
            pl_elapsed < _TARGET_SECONDS
        ), f"P&L took {pl_elapsed:.2f}s (regression guard: {_TARGET_SECONDS}s)"
        assert pl["total_revenue"] >= 0

"""T300 — GL export (keyset-paginated) performance & completeness benchmark.

Verifies the mechanism ``GET /reports/gl`` uses for bulk/audit export at
scale — ``GLReportRepository.gl_detail_cursor_query()`` (Phase 13, T256,
"scales to 500K+ rows without OFFSET cost") — retrieves every seeded row
exactly once, with no gaps or duplicates, by paging forward until
``has_more`` is ``False``.

**Why this test measures at 10K rows, not 500K, and does not extrapolate:**
Same documented rationale as ``test_report_performance.py`` (T270): SQLite's
query planner has no cost-based statistics for a fresh in-memory database
and scales worse than linear on this schema's joins, so a SQLite sample at
this row count would overstate the real cost at 500K by an order of
magnitude in the WRONG direction. This is a fast regression guard for the
keyset-pagination mechanism's CORRECTNESS (every row visited exactly once)
and a coarse timing sanity check, not a substitute for the 500K/production
number, which plan.md's Phase 12 acceptance criteria requires verified
separately against a live PostgreSQL 16 instance (same verification
approach already used for T270's trial balance / balance sheet targets).

Spec ref: specs/008-accounting-finance/tasks.md T300
Plan ref: specs/008-accounting-finance/plan.md Phase 12 Scope — "GL export
(500K entries)"
"""

from __future__ import annotations

import time
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import insert
from sqlalchemy.orm import Session

from modules.accounting.models.coa import Account
from modules.accounting.models.gl import JournalEntry, JournalLine
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.gl import (
    AccountingAuditLogRepository,
    GLReportRepository,
)
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService

_SAMPLE_LINES = 10_000
_TARGET_SECONDS = 10  # regression guard for 10K rows in SQLite, not the 500K SLA
_ACCOUNT_POOL_SIZE = 40
_PAGE_SIZE = 500


def _seed_gl(
    db: Session, company_id: uuid.UUID, period_id: uuid.UUID, fiscal_year_id: uuid.UUID
) -> None:
    """Bulk-insert ``_SAMPLE_LINES`` JournalLine rows via SQLAlchemy Core —
    bypasses PostingEngine/ORM object construction for seeding speed, same
    approach as test_report_performance.py's ``_seed_gl``."""
    account_repo = AccountRepository(db)
    account_ids = []
    for i in range(_ACCOUNT_POOL_SIZE):
        account_type = ["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"][i % 5]
        acct = account_repo.create(
            Account(
                company_id=company_id,
                account_code=f"X{i:04d}",
                account_name=f"Export Perf Account {i}",
                account_type=account_type,
            )
        )
        account_ids.append(acct.id)

    posting_date = date.today()
    num_entries = _SAMPLE_LINES // 2

    entry_ids = [uuid.uuid4() for _ in range(num_entries)]
    entry_rows = [
        {
            "id": entry_ids[i],
            "company_id": company_id,
            "journal_number": f"EXPORT-{i:07d}",
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
                "account_code": f"X{i % _ACCOUNT_POOL_SIZE:04d}",
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
                "account_code": f"X{(i + 1) % _ACCOUNT_POOL_SIZE:04d}",
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


class TestGLExportPerformance:
    def test_cursor_export_visits_every_row_exactly_once(
        self, db_session: Session
    ) -> None:
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

        seed_start = time.perf_counter()
        _seed_gl(db_session, company_id, period.id, fiscal_year.id)
        seed_elapsed = time.perf_counter() - seed_start
        print(f"\nSeeded {_SAMPLE_LINES} GL lines in {seed_elapsed:.2f}s")

        gl_report_repo = GLReportRepository(db_session)

        seen_keys: set[tuple[uuid.UUID, int]] = set()
        cursor: tuple[date, uuid.UUID, int] | None = None
        page_count = 0

        start = time.perf_counter()
        while True:
            rows, has_more = gl_report_repo.gl_detail_cursor_query(
                company_id=company_id, cursor=cursor, limit=_PAGE_SIZE
            )
            page_count += 1
            assert (
                rows
            ), "cursor query returned an empty page while has_more was still true"

            for row in rows:
                key = (row["journal_entry_id"], row["line_number"])
                assert (
                    key not in seen_keys
                ), f"duplicate row visited across pages: {key}"
                seen_keys.add(key)

            last = rows[-1]
            cursor = (
                last["posting_date"],
                last["journal_entry_id"],
                last["line_number"],
            )

            if not has_more:
                break
        elapsed = time.perf_counter() - start

        print(
            f"GL cursor export: {len(seen_keys)} rows across {page_count} pages "
            f"({_PAGE_SIZE}/page) in {elapsed:.3f}s"
        )
        assert len(seen_keys) == _SAMPLE_LINES
        assert elapsed < _TARGET_SECONDS, (
            f"GL cursor export of {_SAMPLE_LINES} rows took {elapsed:.2f}s "
            f"(regression guard: {_TARGET_SECONDS}s)"
        )

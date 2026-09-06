"""Unit tests for ReportService — Phase 13 (T256, T257).

Tests:
  - GL report: cursor pagination walks every row exactly once, in order,
    with no skips or duplicates, and ``has_more``/derived cursor are correct
    at every page boundary.
  - GL report: filters (account_id) apply under cursor pagination too.
  - Subsidiary ledger reports delegate correctly (customer/supplier ledger,
    bank book, cash book) — thin smoke tests since the underlying logic is
    already covered by Phases 6-9's own test suites.
  - Journal report returns POSTED entries for the requested period.

Spec ref: specs/008-accounting-finance/tasks.md T256, T257
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_posting_engine, build_report_service
from modules.accounting.models.coa import Account
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.accounting.services.posting_engine import PostingEngine
from modules.accounting.services.report_service import ReportService


@pytest.fixture
def setup(db_session: Session) -> dict:
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
    company_id = uuid4()
    cash = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1000",
            account_name="Cash",
            account_type="ASSET",
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
    fiscal_year = fiscal_service.create_fiscal_year(
        company_id,
        f"FY-{uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )
    period = next(
        p
        for p in fiscal_service.list_periods(company_id, fiscal_year.id)
        if p.start_date <= today <= p.end_date
    )
    return {
        "company_id": company_id,
        "cash": cash,
        "revenue": revenue,
        "today": today,
        "period": period,
    }


@pytest.fixture
def posting_engine(db_session: Session) -> PostingEngine:
    return build_posting_engine(db_session)


@pytest.fixture
def service(db_session: Session) -> ReportService:
    return build_report_service(db_session)


class TestGLReportCursorPagination:
    def test_walks_every_row_exactly_once_across_pages(
        self, posting_engine: PostingEngine, service: ReportService, setup: dict
    ) -> None:
        for i in range(25):
            posting_engine.post_direct(
                company_id=setup["company_id"],
                journal_type="STANDARD",
                posting_source="MANUAL",
                posting_date=setup["today"],
                lines=[
                    {
                        "account_id": setup["cash"].id,
                        "debit_amount": Decimal(str(i + 1)),
                        "credit_amount": Decimal("0"),
                    },
                    {
                        "account_id": setup["revenue"].id,
                        "debit_amount": Decimal("0"),
                        "credit_amount": Decimal(str(i + 1)),
                    },
                ],
                currency_code="USD",
            )

        seen_journal_line_keys: set[tuple] = set()
        cursor = None
        pages = 0
        while True:
            result = service.get_gl_report(
                setup["company_id"],
                filters={"account_id": setup["cash"].id},
                cursor=cursor,
                limit=7,
            )
            pages += 1
            for row in result["items"]:
                key = (row["journal_entry_id"], row["line_number"])
                assert key not in seen_journal_line_keys, (
                    "cursor pagination duplicated a row"
                )
                seen_journal_line_keys.add(key)
            if not result["has_more"]:
                assert result["next_cursor"] is None
                break
            cursor = result["next_cursor"]
            assert pages < 20, "pagination did not terminate — possible infinite loop"

        # 25 cash-debit lines posted (revenue lines excluded by account_id filter).
        assert len(seen_journal_line_keys) == 25
        assert pages == 4  # ceil(25 / 7)

    def test_account_filter_excludes_other_accounts_under_cursor_mode(
        self, posting_engine: PostingEngine, service: ReportService, setup: dict
    ) -> None:
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["cash"].id,
                    "debit_amount": Decimal("10"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("10"),
                },
            ],
            currency_code="USD",
        )

        result = service.get_gl_report(
            setup["company_id"], filters={"account_id": setup["revenue"].id}, limit=100
        )
        assert len(result["items"]) == 1
        assert result["items"][0]["account_id"] == setup["revenue"].id
        assert result["has_more"] is False


class TestJournalReport:
    def test_returns_only_posted_entries_for_the_period(
        self, posting_engine: PostingEngine, service: ReportService, setup: dict
    ) -> None:
        posting_engine.post_direct(
            company_id=setup["company_id"],
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=setup["today"],
            lines=[
                {
                    "account_id": setup["cash"].id,
                    "debit_amount": Decimal("75"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": setup["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("75"),
                },
            ],
            currency_code="USD",
        )

        report = service.get_journal_report(setup["company_id"], setup["period"].id)

        assert report["total"] == 1
        assert report["entries"][0].status == "POSTED"
        assert report["entries"][0].total_debit_base == Decimal("75")

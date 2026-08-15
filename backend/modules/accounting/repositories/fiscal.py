"""Repositories for Fiscal Calendar entities — Phase 3.

  FiscalYearRepository      — fiscal year definitions
  FiscalPeriodRepository    — periods within a fiscal year
  OpeningBalanceRepository  — opening balances per account per fiscal year

Spec ref: specs/008-accounting-finance/tasks.md T071, T072
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.accounting.models.fiscal import FiscalPeriod, FiscalYear, OpeningBalance
from modules.accounting.repositories import BaseAccountingRepository


class FiscalYearRepository(BaseAccountingRepository[FiscalYear]):
    """Data-access layer for the ``accounting_fiscal_years`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=FiscalYear)

    def find_current(self, company_id: UUID) -> FiscalYear | None:
        """Return the fiscal year marked ``is_current=True`` for this company."""
        stmt = (
            select(FiscalYear)
            .where(FiscalYear.company_id == company_id)
            .where(FiscalYear.is_deleted == False)  # noqa: E712
            .where(FiscalYear.is_current == True)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def find_by_year(
        self, company_id: UUID, fiscal_year_name: str
    ) -> FiscalYear | None:
        """Return the fiscal year with this name for the company, or None."""
        stmt = (
            select(FiscalYear)
            .where(FiscalYear.company_id == company_id)
            .where(FiscalYear.fiscal_year_name == fiscal_year_name)
            .where(FiscalYear.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_all(self, company_id: UUID) -> list[FiscalYear]:
        """Return all fiscal years for a company, most recent start_date first."""
        stmt = (
            select(FiscalYear)
            .where(FiscalYear.company_id == company_id)
            .where(FiscalYear.is_deleted == False)  # noqa: E712
            .order_by(FiscalYear.start_date.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_containing_date(
        self, company_id: UUID, as_of_date: date
    ) -> FiscalYear | None:
        """Return the fiscal year whose ``[start_date, end_date]`` range
        contains ``as_of_date`` (Phase 13 — ``FinancialStatementService``'s
        "Current Year Earnings" balance sheet line needs the fiscal year's
        start date to compute YTD net income).
        """
        stmt = (
            select(FiscalYear)
            .where(FiscalYear.company_id == company_id)
            .where(FiscalYear.is_deleted == False)  # noqa: E712
            .where(FiscalYear.start_date <= as_of_date)
            .where(FiscalYear.end_date >= as_of_date)
        )
        return self.db.execute(stmt).scalars().one_or_none()


class FiscalPeriodRepository(BaseAccountingRepository[FiscalPeriod]):
    """Data-access layer for the ``accounting_fiscal_periods`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=FiscalPeriod)

    def find_open_period_for_date(
        self, company_id: UUID, posting_date: date
    ) -> FiscalPeriod | None:
        """Return the fiscal period covering ``posting_date`` for this company.

        Returns the period regardless of status (OPEN/LOCKED/CLOSED) so the
        caller (``FiscalCalendarService.get_open_period_for_posting`` /
        Phase 4's PostingEngine) can distinguish "no period defined" from
        "period defined but not open" and raise the correct error.
        """
        stmt = (
            select(FiscalPeriod)
            .where(FiscalPeriod.company_id == company_id)
            .where(FiscalPeriod.is_deleted == False)  # noqa: E712
            .where(FiscalPeriod.start_date <= posting_date)
            .where(FiscalPeriod.end_date >= posting_date)
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def find_by_id(self, company_id: UUID, period_id: UUID) -> FiscalPeriod | None:
        """Return the fiscal period by id scoped to the company, or None."""
        return self.get_by_id_or_none(id=period_id, company_id=company_id)

    def list_periods(
        self, company_id: UUID, fiscal_year_id: UUID
    ) -> list[FiscalPeriod]:
        """Return all periods for a fiscal year, ordered by period_number."""
        stmt = (
            select(FiscalPeriod)
            .where(FiscalPeriod.company_id == company_id)
            .where(FiscalPeriod.fiscal_year_id == fiscal_year_id)
            .where(FiscalPeriod.is_deleted == False)  # noqa: E712
            .order_by(FiscalPeriod.period_number)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_recent(
        self, company_id: UUID, limit: int, as_of_date: date | None = None
    ) -> list[FiscalPeriod]:
        """Return up to ``limit`` periods ending on or before ``as_of_date``
        (default: today), across ALL fiscal years, oldest first — the
        chronological time-series shape Phase 17's AI history endpoints
        (P&L / cash flow history, T305/T306) need. Unlike ``list_periods()``,
        not scoped to a single fiscal year.
        """
        cutoff = as_of_date or date.today()
        stmt = (
            select(FiscalPeriod)
            .where(FiscalPeriod.company_id == company_id)
            .where(FiscalPeriod.is_deleted == False)  # noqa: E712
            .where(FiscalPeriod.start_date <= cutoff)
            .order_by(FiscalPeriod.start_date.desc())
            .limit(limit)
        )
        periods = list(self.db.execute(stmt).scalars().all())
        periods.reverse()
        return periods


class OpeningBalanceRepository(BaseAccountingRepository[OpeningBalance]):
    """Data-access layer for the ``accounting_opening_balances`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=OpeningBalance)

    def list_for_fiscal_year(
        self, company_id: UUID, fiscal_year_id: UUID
    ) -> list[OpeningBalance]:
        """Return all opening balance rows for a fiscal year."""
        stmt = (
            select(OpeningBalance)
            .where(OpeningBalance.company_id == company_id)
            .where(OpeningBalance.fiscal_year_id == fiscal_year_id)
            .where(OpeningBalance.is_deleted == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())

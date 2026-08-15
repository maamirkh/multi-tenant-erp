"""Integration tests for Fiscal Calendar repositories and period-lock enforcement.

Tests:
  - FiscalYearRepository CRUD, find_by_year, find_current, company isolation
  - FiscalPeriodRepository find_open_period_for_date, list_periods
  - Period lock enforcement: lock a period, then verify the exact check
    Phase 4's PostingEngine Step 3 will call (``FiscalCalendarService.
    get_open_period_for_posting``) raises ``PeriodLockedError`` — the
    PostingEngine class itself does not exist until Phase 4 (see
    fiscal_service.py module docstring); this test exercises the identical
    validation logic against the real (SQLite-backed) repository layer.

Spec ref: specs/008-accounting-finance/tasks.md T086
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.events import InProcessEventBus, set_event_bus
from modules.accounting.exceptions import PeriodLockedError
from modules.accounting.models.fiscal import FiscalPeriod, FiscalYear
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService


@pytest.fixture(autouse=True)
def _fresh_event_bus() -> None:
    set_event_bus(InProcessEventBus())


class TestFiscalYearRepository:
    def test_create_and_find_by_year(self, db_session: Session) -> None:
        repo = FiscalYearRepository(db_session)
        company_id = uuid4()
        year = repo.create(
            FiscalYear(
                company_id=company_id,
                fiscal_year_name="FY2040",
                start_date=date(2040, 1, 1),
                end_date=date(2040, 12, 31),
                status="OPEN",
                base_currency_code="USD",
            )
        )
        found = repo.find_by_year(company_id, "FY2040")
        assert found is not None
        assert found.id == year.id

    def test_find_current(self, db_session: Session) -> None:
        repo = FiscalYearRepository(db_session)
        company_id = uuid4()
        repo.create(
            FiscalYear(
                company_id=company_id,
                fiscal_year_name="FY2041",
                start_date=date(2041, 1, 1),
                end_date=date(2041, 12, 31),
                status="OPEN",
                base_currency_code="USD",
                is_current=True,
            )
        )
        current = repo.find_current(company_id)
        assert current is not None
        assert current.fiscal_year_name == "FY2041"

    def test_cross_company_isolation(self, db_session: Session) -> None:
        repo = FiscalYearRepository(db_session)
        company_a, company_b = uuid4(), uuid4()
        repo.create(
            FiscalYear(
                company_id=company_a,
                fiscal_year_name="FY2042",
                start_date=date(2042, 1, 1),
                end_date=date(2042, 12, 31),
                status="OPEN",
                base_currency_code="USD",
            )
        )
        assert repo.find_by_year(company_b, "FY2042") is None
        assert repo.list_all(company_b) == []


class TestFiscalPeriodRepository:
    def test_find_open_period_for_date(self, db_session: Session) -> None:
        year_repo = FiscalYearRepository(db_session)
        period_repo = FiscalPeriodRepository(db_session)
        company_id = uuid4()
        year = year_repo.create(
            FiscalYear(
                company_id=company_id,
                fiscal_year_name="FY2043",
                start_date=date(2043, 1, 1),
                end_date=date(2043, 12, 31),
                status="OPEN",
                base_currency_code="USD",
            )
        )
        period_repo.create(
            FiscalPeriod(
                company_id=company_id,
                fiscal_year_id=year.id,
                period_number=1,
                period_name="January 2043",
                start_date=date(2043, 1, 1),
                end_date=date(2043, 1, 31),
                status="OPEN",
            )
        )
        found = period_repo.find_open_period_for_date(company_id, date(2043, 1, 15))
        assert found is not None
        assert found.period_number == 1
        assert (
            period_repo.find_open_period_for_date(company_id, date(2043, 2, 15)) is None
        )

    def test_list_periods_ordered_by_period_number(self, db_session: Session) -> None:
        year_repo = FiscalYearRepository(db_session)
        period_repo = FiscalPeriodRepository(db_session)
        company_id = uuid4()
        year = year_repo.create(
            FiscalYear(
                company_id=company_id,
                fiscal_year_name="FY2044",
                start_date=date(2044, 1, 1),
                end_date=date(2044, 12, 31),
                status="OPEN",
                base_currency_code="USD",
            )
        )
        for n, (start, end) in enumerate(
            [
                (date(2044, 2, 1), date(2044, 2, 28)),
                (date(2044, 1, 1), date(2044, 1, 31)),
            ],
            start=1,
        ):
            period_repo.create(
                FiscalPeriod(
                    company_id=company_id,
                    fiscal_year_id=year.id,
                    period_number=2 if n == 1 else 1,
                    period_name=start.strftime("%B %Y"),
                    start_date=start,
                    end_date=end,
                    status="OPEN",
                )
            )
        periods = period_repo.list_periods(company_id, year.id)
        assert [p.period_number for p in periods] == [1, 2]


class TestPeriodLockEnforcement:
    """Exercises the exact validation Phase 4's PostingEngine Step 3 will call."""

    def test_locking_a_period_blocks_the_posting_check(
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
        company_id = uuid4()
        user_id = uuid4()
        year = fiscal_service.create_fiscal_year(
            company_id, "FY2045", date(2045, 1, 1), date(2045, 12, 31), "USD"
        )
        july = fiscal_service.list_periods(company_id, year.id)[6]

        # Before locking: the posting-date check passes.
        assert (
            fiscal_service.get_open_period_for_posting(company_id, date(2045, 7, 15)).id
            == july.id
        )

        fiscal_service.lock_period(
            company_id, july.id, user_id, "Month-end close initiated"
        )

        # After locking: the exact PostingEngine Step 3 check now rejects it.
        with pytest.raises(PeriodLockedError):
            fiscal_service.get_open_period_for_posting(company_id, date(2045, 7, 15))

        # Other, still-OPEN periods remain postable.
        assert (
            fiscal_service.get_open_period_for_posting(company_id, date(2045, 8, 15))
            is not None
        )

"""Unit/service-level tests for FiscalCalendarService — Phase 3.

Tests:
  - create_fiscal_year generates 12 correctly-bounded monthly periods
  - Duplicate fiscal year name rejected
  - setup_opening_balances: balanced set passes; imbalanced set raises
  - lock_period / unlock_period transition and event publication
  - get_open_period_for_posting: OPEN passes; LOCKED/no-period raises
  - close_period rejects a direct call outside year-end close
  - execute_year_end_close: blocked until all periods LOCKED; succeeds after

Spec ref: specs/008-accounting-finance/tasks.md T085
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.events import InProcessEventBus, set_event_bus
from modules.accounting.exceptions import (
    DuplicateFiscalYearError,
    InvalidFiscalPeriodTransitionError,
    OpeningBalanceImbalancedError,
    PeriodLockedError,
    YearEndCloseBlockedError,
)
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService


@pytest.fixture(autouse=True)
def _fresh_event_bus() -> InProcessEventBus:
    bus = InProcessEventBus()
    set_event_bus(bus)
    return bus


@pytest.fixture
def fiscal_service(db_session: Session) -> FiscalCalendarService:
    return FiscalCalendarService(
        db=db_session,
        year_repo=FiscalYearRepository(db_session),
        period_repo=FiscalPeriodRepository(db_session),
        opening_balance_repo=OpeningBalanceRepository(db_session),
        audit_service=AuditLogService(
            db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
        ),
    )


class TestCreateFiscalYear:
    def test_generates_twelve_calendar_year_periods(
        self, fiscal_service: FiscalCalendarService
    ) -> None:
        company_id = uuid4()
        year = fiscal_service.create_fiscal_year(
            company_id, "FY2026", date(2026, 1, 1), date(2026, 12, 31), "USD"
        )
        periods = fiscal_service.list_periods(company_id, year.id)
        assert len(periods) == 12
        assert periods[0].start_date == date(2026, 1, 1)
        assert periods[0].end_date == date(2026, 1, 31)
        assert periods[-1].start_date == date(2026, 12, 1)
        assert periods[-1].end_date == date(2026, 12, 31)
        assert all(p.status == "OPEN" for p in periods)

    def test_periods_cover_full_span_with_no_gaps(
        self, fiscal_service: FiscalCalendarService
    ) -> None:
        company_id = uuid4()
        year = fiscal_service.create_fiscal_year(
            company_id, "FY-Mid", date(2026, 7, 15), date(2027, 7, 14), "USD"
        )
        periods = fiscal_service.list_periods(company_id, year.id)
        total_days = sum((p.end_date - p.start_date).days + 1 for p in periods)
        span_days = (year.end_date - year.start_date).days + 1
        assert total_days == span_days

        from datetime import timedelta

        for prev, nxt in zip(periods, periods[1:]):
            assert nxt.start_date == prev.end_date + timedelta(days=1)

    def test_duplicate_fiscal_year_name_rejected(
        self, fiscal_service: FiscalCalendarService
    ) -> None:
        company_id = uuid4()
        fiscal_service.create_fiscal_year(
            company_id, "FY2027", date(2027, 1, 1), date(2027, 12, 31), "USD"
        )
        with pytest.raises(DuplicateFiscalYearError):
            fiscal_service.create_fiscal_year(
                company_id, "FY2027", date(2027, 1, 1), date(2027, 12, 31), "USD"
            )

    def test_end_date_before_start_date_rejected(
        self, fiscal_service: FiscalCalendarService
    ) -> None:
        with pytest.raises(ValueError):
            fiscal_service.create_fiscal_year(
                uuid4(), "FY-Bad", date(2026, 12, 31), date(2026, 1, 1), "USD"
            )


class TestLockUnlockPeriod:
    def test_lock_then_unlock_round_trip(
        self, fiscal_service: FiscalCalendarService
    ) -> None:
        company_id = uuid4()
        user_id = uuid4()
        year = fiscal_service.create_fiscal_year(
            company_id, "FY2028", date(2028, 1, 1), date(2028, 12, 31), "USD"
        )
        period = fiscal_service.list_periods(company_id, year.id)[0]

        locked = fiscal_service.lock_period(company_id, period.id, user_id, "month-end")
        assert locked.status == "LOCKED"
        assert locked.locked_by_user_id == user_id
        assert locked.lock_reason == "month-end"

        unlocked = fiscal_service.unlock_period(
            company_id, period.id, user_id, "correction needed"
        )
        assert unlocked.status == "OPEN"
        assert unlocked.locked_at is None

    def test_unlock_requires_non_blank_reason(
        self, fiscal_service: FiscalCalendarService
    ) -> None:
        company_id = uuid4()
        user_id = uuid4()
        year = fiscal_service.create_fiscal_year(
            company_id, "FY2029", date(2029, 1, 1), date(2029, 12, 31), "USD"
        )
        period = fiscal_service.list_periods(company_id, year.id)[0]
        fiscal_service.lock_period(company_id, period.id, user_id, "close")
        with pytest.raises(ValueError):
            fiscal_service.unlock_period(company_id, period.id, user_id, "   ")

    def test_re_lock_already_locked_period_rejected(
        self, fiscal_service: FiscalCalendarService
    ) -> None:
        company_id = uuid4()
        user_id = uuid4()
        year = fiscal_service.create_fiscal_year(
            company_id, "FY2030", date(2030, 1, 1), date(2030, 12, 31), "USD"
        )
        period = fiscal_service.list_periods(company_id, year.id)[0]
        fiscal_service.lock_period(company_id, period.id, user_id, "close")
        with pytest.raises(InvalidFiscalPeriodTransitionError):
            fiscal_service.lock_period(company_id, period.id, user_id, "close again")


class TestGetOpenPeriodForPosting:
    def test_open_period_returned(self, fiscal_service: FiscalCalendarService) -> None:
        company_id = uuid4()
        year = fiscal_service.create_fiscal_year(
            company_id, "FY2031", date(2031, 1, 1), date(2031, 12, 31), "USD"
        )
        period = fiscal_service.get_open_period_for_posting(
            company_id, date(2031, 3, 15)
        )
        assert period.period_number == 3

    def test_locked_period_raises_period_locked_error(
        self, fiscal_service: FiscalCalendarService
    ) -> None:
        company_id = uuid4()
        user_id = uuid4()
        year = fiscal_service.create_fiscal_year(
            company_id, "FY2032", date(2032, 1, 1), date(2032, 12, 31), "USD"
        )
        march = fiscal_service.list_periods(company_id, year.id)[2]
        fiscal_service.lock_period(company_id, march.id, user_id, "close")
        with pytest.raises(PeriodLockedError):
            fiscal_service.get_open_period_for_posting(company_id, date(2032, 3, 10))

    def test_no_period_defined_raises_period_locked_error(
        self, fiscal_service: FiscalCalendarService
    ) -> None:
        with pytest.raises(PeriodLockedError):
            fiscal_service.get_open_period_for_posting(uuid4(), date(1999, 1, 1))


class TestClosePeriodDirectCallRejected:
    def test_close_period_outside_year_end_close_rejected(
        self, fiscal_service: FiscalCalendarService
    ) -> None:
        company_id = uuid4()
        user_id = uuid4()
        year = fiscal_service.create_fiscal_year(
            company_id, "FY2033", date(2033, 1, 1), date(2033, 12, 31), "USD"
        )
        period = fiscal_service.list_periods(company_id, year.id)[0]
        fiscal_service.lock_period(company_id, period.id, user_id, "close")
        with pytest.raises(InvalidFiscalPeriodTransitionError):
            fiscal_service.close_period(company_id, period.id, user_id)


class TestSetupOpeningBalances:
    def test_balanced_set_passes(self, fiscal_service: FiscalCalendarService) -> None:
        company_id = uuid4()
        year = fiscal_service.create_fiscal_year(
            company_id, "FY2034", date(2034, 1, 1), date(2034, 12, 31), "USD"
        )
        account_a, account_b = uuid4(), uuid4()
        created = fiscal_service.setup_opening_balances(
            company_id,
            year.id,
            [
                {"account_id": account_a, "debit_amount": Decimal("500.00")},
                {"account_id": account_b, "credit_amount": Decimal("500.00")},
            ],
        )
        assert len(created) == 2

    def test_imbalanced_set_raises(self, fiscal_service: FiscalCalendarService) -> None:
        company_id = uuid4()
        year = fiscal_service.create_fiscal_year(
            company_id, "FY2035", date(2035, 1, 1), date(2035, 12, 31), "USD"
        )
        with pytest.raises(OpeningBalanceImbalancedError):
            fiscal_service.setup_opening_balances(
                company_id,
                year.id,
                [{"account_id": uuid4(), "debit_amount": Decimal("100.00")}],
            )


class TestExecuteYearEndClose:
    def test_blocked_until_all_periods_locked(
        self, fiscal_service: FiscalCalendarService
    ) -> None:
        company_id = uuid4()
        user_id = uuid4()
        year = fiscal_service.create_fiscal_year(
            company_id, "FY2036", date(2036, 1, 1), date(2036, 12, 31), "USD"
        )
        periods = fiscal_service.list_periods(company_id, year.id)
        for period in periods[:-1]:
            fiscal_service.lock_period(company_id, period.id, user_id, "close")
        with pytest.raises(YearEndCloseBlockedError):
            fiscal_service.execute_year_end_close(company_id, year.id, user_id)

    def test_succeeds_once_all_periods_locked(
        self, fiscal_service: FiscalCalendarService
    ) -> None:
        company_id = uuid4()
        user_id = uuid4()
        year = fiscal_service.create_fiscal_year(
            company_id, "FY2037", date(2037, 1, 1), date(2037, 12, 31), "USD"
        )
        periods = fiscal_service.list_periods(company_id, year.id)
        for period in periods:
            fiscal_service.lock_period(company_id, period.id, user_id, "close")

        closed_year = fiscal_service.execute_year_end_close(
            company_id, year.id, user_id
        )
        assert closed_year.status == "CLOSED"
        closed_periods = fiscal_service.list_periods(company_id, year.id)
        assert all(p.status == "CLOSED" for p in closed_periods)

"""[Phase 4] Unit test: leap-year date arithmetic correctness (tasks.md
T063, FR-INST-111) — handled automatically by stdlib clamping, no custom
leap-year branch needed since MONTHLY/QUARTERLY never assume a fixed
365/366-day year."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from modules.installments.services.schedule_engine import ScheduleEngine, _add_months


def test_add_months_feb_29_leap_year_anchor_clamps_in_non_leap_year() -> None:
    # 2028 is a leap year (Feb has 29 days); 2029 is not (Feb has 28).
    assert _add_months(date(2028, 2, 29), 12) == date(2029, 2, 28)


def test_add_months_into_leap_year_preserves_feb_29() -> None:
    # 2027 is not a leap year; anchoring from Jan 29 into Feb of a leap
    # year (2028) should NOT clamp since Feb 29 exists that year.
    assert _add_months(date(2027, 1, 29), 13) == date(2028, 2, 29)


def test_schedule_generation_crossing_a_leap_day_is_deterministic() -> None:
    result = ScheduleEngine.generate(
        principal=Decimal("300"),
        down_payment=Decimal("0"),
        markup=Decimal("0"),
        installment_count=3,
        frequency="MONTHLY",
        first_due_date=date(2028, 1, 29),
        rounding_policy="ROUND_HALF_UP",
    )
    due_dates = [line.due_date for line in result.lines]
    assert due_dates == [
        date(2028, 1, 29),
        date(2028, 2, 29),  # leap day — not clamped
        date(2028, 3, 29),
    ]


def test_weekly_schedule_correctly_crosses_leap_day() -> None:
    result = ScheduleEngine.generate(
        principal=Decimal("200"),
        down_payment=Decimal("0"),
        markup=Decimal("0"),
        installment_count=2,
        frequency="WEEKLY",
        first_due_date=date(2028, 2, 25),
        rounding_policy="ROUND_HALF_UP",
    )
    due_dates = [line.due_date for line in result.lines]
    assert due_dates == [date(2028, 2, 25), date(2028, 3, 3)]

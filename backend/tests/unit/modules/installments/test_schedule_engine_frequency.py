"""[Phase 4] Unit test: monthly/weekly/quarterly frequency due-date
sequencing (tasks.md T061, plan.md §10.2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from modules.installments.services.schedule_engine import ScheduleEngine


def test_monthly_frequency_advances_one_month_per_line() -> None:
    result = ScheduleEngine.generate(
        principal=Decimal("1200"),
        down_payment=Decimal("0"),
        markup=Decimal("0"),
        installment_count=4,
        frequency="MONTHLY",
        first_due_date=date(2026, 1, 15),
        rounding_policy="ROUND_HALF_UP",
    )
    due_dates = [line.due_date for line in result.lines]
    assert due_dates == [
        date(2026, 1, 15),
        date(2026, 2, 15),
        date(2026, 3, 15),
        date(2026, 4, 15),
    ]


def test_weekly_frequency_advances_seven_days_per_line() -> None:
    result = ScheduleEngine.generate(
        principal=Decimal("400"),
        down_payment=Decimal("0"),
        markup=Decimal("0"),
        installment_count=4,
        frequency="WEEKLY",
        first_due_date=date(2026, 1, 5),
        rounding_policy="ROUND_HALF_UP",
    )
    due_dates = [line.due_date for line in result.lines]
    assert due_dates == [
        date(2026, 1, 5),
        date(2026, 1, 12),
        date(2026, 1, 19),
        date(2026, 1, 26),
    ]


def test_quarterly_frequency_advances_three_months_per_line() -> None:
    result = ScheduleEngine.generate(
        principal=Decimal("4000"),
        down_payment=Decimal("0"),
        markup=Decimal("0"),
        installment_count=4,
        frequency="QUARTERLY",
        first_due_date=date(2026, 1, 10),
        rounding_policy="ROUND_HALF_UP",
    )
    due_dates = [line.due_date for line in result.lines]
    assert due_dates == [
        date(2026, 1, 10),
        date(2026, 4, 10),
        date(2026, 7, 10),
        date(2026, 10, 10),
    ]


def test_sequence_numbers_are_1_based_and_contiguous() -> None:
    result = ScheduleEngine.generate(
        principal=Decimal("300"),
        down_payment=Decimal("0"),
        markup=Decimal("0"),
        installment_count=3,
        frequency="MONTHLY",
        first_due_date=date(2026, 1, 1),
        rounding_policy="ROUND_HALF_UP",
    )
    assert [line.sequence for line in result.lines] == [1, 2, 3]


def test_unsupported_frequency_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        ScheduleEngine.generate(
            principal=Decimal("100"),
            down_payment=Decimal("0"),
            markup=Decimal("0"),
            installment_count=2,
            frequency="DAILY",
            first_due_date=date(2026, 1, 1),
            rounding_policy="ROUND_HALF_UP",
        )

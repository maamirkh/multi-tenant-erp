"""[Phase 4] Unit test: month-end anchoring — a due date anchored to the
31st in a 30-day (or shorter) month resolves to that month's actual last
day (tasks.md T062, FR-INST-111)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from modules.installments.services.schedule_engine import ScheduleEngine, _add_months


def test_add_months_clamps_day_31_into_30_day_month() -> None:
    assert _add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)  # Feb, non-leap


def test_add_months_clamps_day_31_into_april() -> None:
    assert _add_months(date(2026, 1, 31), 3) == date(2026, 4, 30)


def test_add_months_does_not_clamp_when_target_month_has_enough_days() -> None:
    assert _add_months(date(2026, 1, 31), 2) == date(2026, 3, 31)


def test_schedule_generation_anchors_to_month_end_across_lines() -> None:
    result = ScheduleEngine.generate(
        principal=Decimal("500"),
        down_payment=Decimal("0"),
        markup=Decimal("0"),
        installment_count=5,
        frequency="MONTHLY",
        first_due_date=date(2026, 1, 31),
        rounding_policy="ROUND_HALF_UP",
    )
    due_dates = [line.due_date for line in result.lines]
    assert due_dates == [
        date(2026, 1, 31),
        date(2026, 2, 28),  # clamped
        date(2026, 3, 31),  # NOT re-clamped forward — computed from the
        # ORIGINAL anchor date each time (Jan 31), not from Feb 28.
        date(2026, 4, 30),  # clamped
        date(2026, 5, 31),
    ]

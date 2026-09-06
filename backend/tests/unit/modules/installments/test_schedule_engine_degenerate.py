"""[Phase 4] Unit test: a degenerate (zero/negative) final installment is
rejected with DegenerateScheduleError, never silently produced (tasks.md
T065, spec §28 edge case)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from modules.installments.exceptions import DegenerateScheduleError
from modules.installments.services.schedule_engine import ScheduleEngine


def test_zero_contractual_total_raises_degenerate_schedule_error() -> None:
    with pytest.raises(DegenerateScheduleError):
        ScheduleEngine.generate(
            principal=Decimal("100"),
            down_payment=Decimal("100"),  # financed_principal = 0
            markup=Decimal("0"),
            installment_count=3,
            frequency="MONTHLY",
            first_due_date=date(2026, 1, 1),
            rounding_policy="ROUND_HALF_UP",
        )


def test_negative_contractual_total_raises_degenerate_schedule_error() -> None:
    with pytest.raises(DegenerateScheduleError):
        ScheduleEngine.generate(
            principal=Decimal("100"),
            down_payment=Decimal("150"),  # financed_principal = -50
            markup=Decimal("0"),
            installment_count=2,
            frequency="MONTHLY",
            first_due_date=date(2026, 1, 1),
            rounding_policy="ROUND_HALF_UP",
        )


def test_degenerate_schedule_error_carries_documented_code() -> None:
    with pytest.raises(DegenerateScheduleError) as exc_info:
        ScheduleEngine.generate(
            principal=Decimal("100"),
            down_payment=Decimal("100"),
            markup=Decimal("0"),
            installment_count=1,
            frequency="MONTHLY",
            first_due_date=date(2026, 1, 1),
            rounding_policy="ROUND_HALF_UP",
        )
    assert exc_info.value.code == "DEGENERATE_SCHEDULE"


def test_error_raised_before_any_lines_are_returned() -> None:
    """No partial/inconsistent result is ever returned — the exception is
    raised in place of any ``ScheduleGenerationResult``."""
    with pytest.raises(DegenerateScheduleError):
        result = ScheduleEngine.generate(
            principal=Decimal("50"),
            down_payment=Decimal("50"),
            markup=Decimal("0"),
            installment_count=5,
            frequency="MONTHLY",
            first_due_date=date(2026, 1, 1),
            rounding_policy="ROUND_HALF_UP",
        )
        del result  # unreachable — generate() must raise first

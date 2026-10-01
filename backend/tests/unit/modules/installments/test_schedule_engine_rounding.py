"""[Phase 4] Unit test: ROUND_HALF_UP quantization to Decimal("0.000001")
and exact sum(lines) == contractual_total reconciliation (tasks.md T064,
BR-INST-005)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from modules.installments.services.schedule_engine import ScheduleEngine


def test_lines_sum_exactly_to_contractual_total_non_divisible_amount() -> None:
    # 1000 / 3 = 333.333333... — a genuinely non-divisible split.
    result = ScheduleEngine.generate(
        principal=Decimal("1000"),
        down_payment=Decimal("0"),
        markup=Decimal("0"),
        installment_count=3,
        frequency="MONTHLY",
        first_due_date=date(2026, 1, 1),
        rounding_policy="ROUND_HALF_UP",
    )
    assert (
        sum(line.scheduled_amount for line in result.lines) == result.contractual_total
    )
    assert result.contractual_total == Decimal("1000")


def test_base_lines_quantized_to_six_decimal_places() -> None:
    result = ScheduleEngine.generate(
        principal=Decimal("1000"),
        down_payment=Decimal("0"),
        markup=Decimal("0"),
        installment_count=3,
        frequency="MONTHLY",
        first_due_date=date(2026, 1, 1),
        rounding_policy="ROUND_HALF_UP",
    )
    # First two lines are the quantized base amount; ROUND_HALF_UP of
    # 333.333333333... to 6dp is 333.333333.
    assert result.lines[0].scheduled_amount == Decimal("333.333333")
    assert result.lines[1].scheduled_amount == Decimal("333.333333")
    # Residual absorbed entirely into the final line by subtraction.
    assert result.lines[2].scheduled_amount == Decimal("333.333334")


def test_round_half_up_vs_round_half_even_produce_different_base_amounts() -> None:
    # 5.000001 / 2 = 2.5000005 exactly — a genuine tie at the 6th decimal
    # place (base amount's 6th digit is 0, i.e. even), so HALF_UP and
    # HALF_EVEN provably diverge.
    kwargs: dict[str, Any] = dict(
        principal=Decimal("5.000001"),
        down_payment=Decimal("0"),
        markup=Decimal("0"),
        installment_count=2,
        frequency="MONTHLY",
        first_due_date=date(2026, 1, 1),
    )
    half_up = ScheduleEngine.generate(rounding_policy="ROUND_HALF_UP", **kwargs)
    half_even = ScheduleEngine.generate(rounding_policy="ROUND_HALF_EVEN", **kwargs)

    assert half_up.lines[0].scheduled_amount == Decimal("2.500001")
    assert half_up.lines[1].scheduled_amount == Decimal("2.500000")

    assert half_even.lines[0].scheduled_amount == Decimal("2.500000")
    assert half_even.lines[1].scheduled_amount == Decimal("2.500001")

    # Both policies still reconcile exactly regardless of which line
    # absorbs the residual.
    assert sum(line.scheduled_amount for line in half_up.lines) == Decimal("5.000001")
    assert sum(line.scheduled_amount for line in half_even.lines) == Decimal("5.000001")


def test_markup_included_in_contractual_total() -> None:
    result = ScheduleEngine.generate(
        principal=Decimal("900"),
        down_payment=Decimal("100"),
        markup=Decimal("50"),
        installment_count=4,
        frequency="MONTHLY",
        first_due_date=date(2026, 1, 1),
        rounding_policy="ROUND_HALF_UP",
    )
    # financed_principal = 900 - 100 = 800; contractual_total = 800 + 50 = 850
    assert result.contractual_total == Decimal("850")
    assert sum(line.scheduled_amount for line in result.lines) == Decimal("850")

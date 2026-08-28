"""[Epic 10, Phase 8, T146] Unit test — aging-bucket boundary values.

Exercises every boundary named in spec.md Assumption A7 (current, 1-30,
31-60, 61-90, 91-120, 120+) at the exact days-overdue values where the
bucket changes: 0, 1, 30, 31, 60, 61, 90, 91, 120, 121.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from modules.installments.services.aging_calculator import (
    InstallmentAgingCalculator,
    bucket_for,
)

_AS_OF = date(2026, 6, 30)


@pytest.mark.parametrize(
    "days_overdue,expected_bucket",
    [
        (-5, "current"),
        (0, "current"),
        (1, "days_1_30"),
        (30, "days_1_30"),
        (31, "days_31_60"),
        (60, "days_31_60"),
        (61, "days_61_90"),
        (90, "days_61_90"),
        (91, "days_91_120"),
        (120, "days_91_120"),
        (121, "days_120_plus"),
    ],
)
def test_bucket_for_boundary_values(days_overdue: int, expected_bucket: str) -> None:
    due_date = _AS_OF - timedelta(days=days_overdue)
    assert bucket_for(due_date, _AS_OF) == expected_bucket
    assert InstallmentAgingCalculator.bucket_for(due_date, _AS_OF) == expected_bucket


def test_none_due_date_like_input_is_never_passed_but_future_due_date_is_current() -> (
    None
):
    # A due date in the future (not yet due at all) must land in
    # "current", matching Accounting's own convention (days_overdue<=0).
    future_due_date = _AS_OF + timedelta(days=10)
    assert bucket_for(future_due_date, _AS_OF) == "current"


def test_aggregate_sums_outstanding_amounts_into_correct_buckets() -> None:
    from decimal import Decimal

    lines = [
        (_AS_OF, Decimal("100.00")),  # current
        (_AS_OF - timedelta(days=15), Decimal("50.00")),  # 1-30
        (_AS_OF - timedelta(days=45), Decimal("25.00")),  # 31-60
        (_AS_OF - timedelta(days=200), Decimal("10.00")),  # 120+
    ]
    row = InstallmentAgingCalculator.aggregate(lines, _AS_OF)
    assert row.current == Decimal("100.00")
    assert row.days_1_30 == Decimal("50.00")
    assert row.days_31_60 == Decimal("25.00")
    assert row.days_120_plus == Decimal("10.00")
    assert row.days_61_90 == Decimal("0")
    assert row.days_91_120 == Decimal("0")
    assert row.total == Decimal("185.00")


def test_aggregate_skips_zero_and_negative_outstanding_lines() -> None:
    from decimal import Decimal

    lines = [
        (_AS_OF - timedelta(days=200), Decimal("0")),
        (_AS_OF - timedelta(days=200), Decimal("-5.00")),
    ]
    row = InstallmentAgingCalculator.aggregate(lines, _AS_OF)
    assert row.total == Decimal("0")

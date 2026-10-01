"""[Phase 4] Unit test: identical inputs produce byte-identical output
across repeated calls (tasks.md T066, FR-INST-031/BR-INST-019) — no
randomness, no wall-clock dependency beyond the explicit
``first_due_date`` parameter."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from modules.installments.services.schedule_engine import ScheduleEngine


def _kwargs() -> dict[str, Any]:
    return dict(
        principal=Decimal("10000"),
        down_payment=Decimal("1000"),
        markup=Decimal("250.50"),
        installment_count=7,
        frequency="MONTHLY",
        first_due_date=date(2026, 3, 15),
        rounding_policy="ROUND_HALF_UP",
    )


def test_repeated_calls_with_identical_inputs_produce_identical_output() -> None:
    first = ScheduleEngine.generate(**_kwargs())
    second = ScheduleEngine.generate(**_kwargs())
    third = ScheduleEngine.generate(**_kwargs())

    assert first == second == third
    assert (
        first.contractual_total == second.contractual_total == third.contractual_total
    )
    assert first.lines == second.lines == third.lines


def test_determinism_holds_across_different_frequencies_and_policies() -> None:
    for frequency in ("WEEKLY", "MONTHLY", "QUARTERLY"):
        for policy in ("ROUND_HALF_UP", "ROUND_HALF_EVEN"):
            kwargs = _kwargs()
            kwargs["frequency"] = frequency
            kwargs["rounding_policy"] = policy
            first = ScheduleEngine.generate(**kwargs)
            second = ScheduleEngine.generate(**kwargs)
            assert first == second

"""[Epic 10, Phase 7, T130] Unit tests for
``InstallmentAllocationPolicy.allocate_oldest_first()`` — pure function,
no DB (FR-INST-140, BR-INST-007).

Covers exact/partial/multi-installment/advance payment allocation
scenarios (spec.md Scenarios B/C/D).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from modules.installments.services.allocation_policy import (
    InstallmentAllocationPolicy,
    OutstandingLine,
)


def _line(due_date: date, outstanding: str) -> OutstandingLine:
    return OutstandingLine(
        schedule_line_id=uuid.uuid4(),
        due_date=due_date,
        outstanding_amount=Decimal(outstanding),
    )


class TestAllocateOldestFirst:
    def test_exact_single_installment_payment(self) -> None:
        line = _line(date(2026, 1, 1), "300.00")
        instructions = InstallmentAllocationPolicy.allocate_oldest_first(
            Decimal("300.00"), [line]
        )
        assert len(instructions) == 1
        assert instructions[0].schedule_line_id == line.schedule_line_id
        assert instructions[0].amount == Decimal("300.00")
        assert instructions[0].allocation_order == 1

    def test_partial_installment_payment(self) -> None:
        line = _line(date(2026, 1, 1), "300.00")
        instructions = InstallmentAllocationPolicy.allocate_oldest_first(
            Decimal("100.00"), [line]
        )
        assert len(instructions) == 1
        assert instructions[0].amount == Decimal("100.00")

    def test_multi_installment_payment_satisfies_oldest_first(self) -> None:
        older = _line(date(2026, 1, 1), "200.00")
        newer = _line(date(2026, 2, 1), "200.00")
        # Deliberately pass newer before older to prove sorting happens
        # internally, not relying on input order.
        instructions = InstallmentAllocationPolicy.allocate_oldest_first(
            Decimal("300.00"), [newer, older]
        )
        assert len(instructions) == 2
        assert instructions[0].schedule_line_id == older.schedule_line_id
        assert instructions[0].amount == Decimal("200.00")
        assert instructions[0].allocation_order == 1
        assert instructions[1].schedule_line_id == newer.schedule_line_id
        assert instructions[1].amount == Decimal("100.00")
        assert instructions[1].allocation_order == 2

    def test_advance_payment_against_not_yet_due_line(self) -> None:
        """Scenario D: a future-dated line is exactly as eligible as an
        overdue one — no special branch, same oldest-first ordering."""
        future_line = _line(date(2099, 1, 1), "150.00")
        instructions = InstallmentAllocationPolicy.allocate_oldest_first(
            Decimal("150.00"), [future_line]
        )
        assert len(instructions) == 1
        assert instructions[0].amount == Decimal("150.00")

    def test_zero_outstanding_lines_are_skipped(self) -> None:
        paid_line = _line(date(2026, 1, 1), "0")
        due_line = _line(date(2026, 2, 1), "100.00")
        instructions = InstallmentAllocationPolicy.allocate_oldest_first(
            Decimal("100.00"), [paid_line, due_line]
        )
        assert len(instructions) == 1
        assert instructions[0].schedule_line_id == due_line.schedule_line_id

    def test_payment_exceeding_total_outstanding_raises_value_error(self) -> None:
        line = _line(date(2026, 1, 1), "100.00")
        with pytest.raises(ValueError):
            InstallmentAllocationPolicy.allocate_oldest_first(Decimal("200.00"), [line])

    def test_non_positive_payment_amount_raises_value_error(self) -> None:
        line = _line(date(2026, 1, 1), "100.00")
        with pytest.raises(ValueError):
            InstallmentAllocationPolicy.allocate_oldest_first(Decimal("0"), [line])
        with pytest.raises(ValueError):
            InstallmentAllocationPolicy.allocate_oldest_first(Decimal("-10"), [line])

    def test_three_lines_partial_third_line(self) -> None:
        l1 = _line(date(2026, 1, 1), "100.00")
        l2 = _line(date(2026, 2, 1), "100.00")
        l3 = _line(date(2026, 3, 1), "100.00")
        instructions = InstallmentAllocationPolicy.allocate_oldest_first(
            Decimal("250.00"), [l1, l2, l3]
        )
        assert len(instructions) == 3
        assert instructions[0].amount == Decimal("100.00")
        assert instructions[1].amount == Decimal("100.00")
        assert instructions[2].amount == Decimal("50.00")

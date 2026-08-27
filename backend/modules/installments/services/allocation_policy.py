"""InstallmentAllocationPolicy — pure, deterministic oldest-due-first
payment allocation (FR-INST-140, BR-INST-007, spec.md §13.2).

Zero DB/HTTP imports (mirrors ``ScheduleEngine``'s pure-engine
convention exactly) — a stateless function taking only primitive/value-
object inputs, independently unit-testable, called by
``InstallmentCollectionService.record_collection()`` (Phase 7) after it
has already computed each schedule line's live outstanding amount from
``InstallmentAllocationReferenceRepository``.

"Advance payment" (spec.md Scenario D) requires no special branch here:
a not-yet-due line is exactly as eligible for allocation as an overdue
one — oldest-due-first orders ALL outstanding lines by ``due_date``
ascending, regardless of whether that date is in the past, today, or the
future.

Spec ref: specs/010-installments/plan.md §13; specs/010-installments/
data-model.md "InstallmentAllocationReference".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class OutstandingLine:
    """One schedule line's live outstanding amount — the input shape
    ``allocate_oldest_first()`` consumes. The caller (``record_collection()``)
    computes ``outstanding_amount`` from
    ``scheduled_amount - net_allocated_amount`` before calling this
    function; this module has no knowledge of how that figure was
    derived."""

    schedule_line_id: UUID
    due_date: date
    outstanding_amount: Decimal


@dataclass(frozen=True)
class AllocationInstruction:
    """One line of the computed allocation plan — consumed by
    ``InstallmentCollectionService`` to build both the Accounting
    allocation-line request and the resulting
    ``InstallmentAllocationReference`` row."""

    schedule_line_id: UUID
    amount: Decimal
    allocation_order: int


class InstallmentAllocationPolicy:
    """Stateless oldest-due-first allocation policy."""

    @staticmethod
    def allocate_oldest_first(
        payment_amount: Decimal,
        schedule_lines_outstanding: list[OutstandingLine],
    ) -> list[AllocationInstruction]:
        """Greedily consume ``payment_amount`` against
        ``schedule_lines_outstanding``, sorted by ``due_date`` ascending
        (FR-INST-140), oldest first.

        Raises:
            ValueError: ``payment_amount`` is not positive, or exceeds
                the sum of every line's outstanding amount — a pure-
                function input-contract violation (mirrors
                ``ScheduleEngine.generate()``'s convention); the caller
                (``record_collection()``) validates this against the
                over-collection guard (BR-INST-011) *before* invoking
                this function, so this exception should never surface to
                an end user from this function alone.
        """
        if payment_amount <= 0:
            raise ValueError("payment_amount must be positive.")

        total_outstanding = sum(
            (line.outstanding_amount for line in schedule_lines_outstanding),
            Decimal("0"),
        )
        if payment_amount > total_outstanding:
            raise ValueError(
                f"payment_amount ({payment_amount}) exceeds total outstanding "
                f"({total_outstanding})."
            )

        ordered_lines = sorted(
            (
                line
                for line in schedule_lines_outstanding
                if line.outstanding_amount > 0
            ),
            key=lambda line: line.due_date,
        )

        instructions: list[AllocationInstruction] = []
        remaining = payment_amount
        order = 1
        for line in ordered_lines:
            if remaining <= 0:
                break
            amount = min(remaining, line.outstanding_amount)
            instructions.append(
                AllocationInstruction(
                    schedule_line_id=line.schedule_line_id,
                    amount=amount,
                    allocation_order=order,
                )
            )
            remaining -= amount
            order += 1

        return instructions

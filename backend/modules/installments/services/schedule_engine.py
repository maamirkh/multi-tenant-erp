"""ScheduleEngine — pure, deterministic installment schedule generation.

Zero DB/HTTP imports (plan.md §10.1) — a stateless engine taking only
primitive/value-object inputs, independently unit-testable and callable
identically from quote preview (no persistence, Phase 4) and contract
activation (persisted, Phase 7). No randomness, no wall-clock dependency
beyond the explicit ``first_due_date`` parameter (FR-INST-031/BR-INST-019).

Spec ref: specs/010-installments/plan.md §10 (Schedule Engine);
specs/010-installments/data-model.md "InstallmentScheduleLine".
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

from modules.installments.exceptions import DegenerateScheduleError

#: ``InstallmentConfiguration.rounding_policy`` string values map directly
#: onto Python's ``decimal`` rounding-mode constant names (research.md
#: §17/§8) — a local mapping only, never importing Accounting's
#: conceptually-similar ``RoundingRule`` enum across the module boundary.
_ROUNDING_MODES: dict[str, str] = {
    "ROUND_HALF_UP": ROUND_HALF_UP,
    "ROUND_HALF_EVEN": ROUND_HALF_EVEN,
}

#: Frequencies supported by this phase (FR-INST-110: "monthly at minimum,
#: weekly/quarterly/custom where tenant-enabled"). Tenant-defined custom
#: interval-in-days frequencies are explicitly out of scope here.
SUPPORTED_FREQUENCIES: frozenset[str] = frozenset({"WEEKLY", "MONTHLY", "QUARTERLY"})

_AMOUNT_QUANT = Decimal("0.000001")


@dataclass(frozen=True)
class ScheduleLineDraft:
    """One computed, not-yet-persisted schedule line."""

    sequence: int
    due_date: date
    scheduled_amount: Decimal


@dataclass(frozen=True)
class ScheduleGenerationResult:
    """The full deterministic output of ``ScheduleEngine.generate()``."""

    lines: tuple[ScheduleLineDraft, ...]
    contractual_total: Decimal


def _add_months(d: date, n: int) -> date:
    """Add ``n`` calendar months to ``d``, clamping the day-of-month to
    the target month's actual last day (FR-INST-111) — a due date
    anchored to the 31st in a 30-day month resolves to that month's last
    day. Uses stdlib ``calendar.monthrange()``; no external date library
    needed. Leap years are handled automatically by this same clamping
    (e.g. Feb 29 anchor in a non-leap year resolves to Feb 28)."""
    month_index = d.month - 1 + n
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    last_day_of_month = calendar.monthrange(year, month)[1]
    day = min(d.day, last_day_of_month)
    return date(year, month, day)


def _due_date_for_index(first_due_date: date, frequency: str, index: int) -> date:
    """Due date for the ``index``-th line (0-based), always computed as an
    offset from the original ``first_due_date`` anchor — never
    incrementally from the previous (possibly month-end-clamped) line.
    Anchoring every line to the original day-of-month, rather than
    chaining ``_add_months`` calls off a clamped result, is what prevents
    day-drift (e.g. Jan 31 -> Feb 28 -> Mar 28 would silently lose the
    31st anchor forever; anchoring from ``first_due_date`` each time
    instead correctly yields Mar 31)."""
    if frequency == "WEEKLY":
        return first_due_date + timedelta(weeks=index)
    if frequency == "MONTHLY":
        return _add_months(first_due_date, index)
    if frequency == "QUARTERLY":
        return _add_months(first_due_date, index * 3)
    raise ValueError(f"Unsupported frequency: {frequency!r}")


class ScheduleEngine:
    """Stateless schedule-generation engine — no DB session, no HTTP
    context, no repository calls (plan.md §10.1)."""

    @staticmethod
    def generate(
        *,
        principal: Decimal,
        down_payment: Decimal,
        markup: Decimal,
        installment_count: int,
        frequency: str,
        first_due_date: date,
        rounding_policy: str,
    ) -> ScheduleGenerationResult:
        """Deterministic: identical inputs always produce an identical
        ``ScheduleGenerationResult`` (FR-INST-031, BR-INST-019).

        Raises:
            ValueError: unsupported ``frequency``/``rounding_policy`` —
                a pure-function input-contract violation, not a
                user-facing business error (callers validate against
                tenant configuration before invoking this engine).
            DegenerateScheduleError: the computed final installment would
                be zero or negative (spec §28 edge case) — rejected
                before any persistence, never silently produced.
        """
        if frequency not in SUPPORTED_FREQUENCIES:
            raise ValueError(f"Unsupported frequency: {frequency!r}")
        rounding_mode = _ROUNDING_MODES.get(rounding_policy)
        if rounding_mode is None:
            raise ValueError(f"Unsupported rounding policy: {rounding_policy!r}")

        financed_principal = principal - down_payment
        contractual_total = financed_principal + markup

        # Amount splitting/residual (BR-INST-005, FR-INST-112, §10.3):
        # the residual is absorbed entirely into the final line, computed
        # by subtraction — never independently rounded — guaranteeing
        # sum(lines) == contractual_total exactly, every time.
        base_line_amount = (contractual_total / installment_count).quantize(
            _AMOUNT_QUANT, rounding=rounding_mode
        )
        amounts = [base_line_amount] * (installment_count - 1)
        last_line_amount = contractual_total - sum(amounts)
        if last_line_amount <= 0:
            raise DegenerateScheduleError(
                message=(
                    "The generated schedule's final installment would be "
                    f"{last_line_amount} (zero or negative)."
                )
            )
        amounts.append(last_line_amount)

        lines = [
            ScheduleLineDraft(
                sequence=sequence,
                due_date=_due_date_for_index(first_due_date, frequency, sequence - 1),
                scheduled_amount=amount,
            )
            for sequence, amount in enumerate(amounts, start=1)
        ]

        return ScheduleGenerationResult(
            lines=tuple(lines), contractual_total=contractual_total
        )

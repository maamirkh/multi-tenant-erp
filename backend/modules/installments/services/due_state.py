"""DueStateCalculator — pure, deterministic due-state derivation (T138).

Derives a schedule line's business state from authoritative dates and
payment allocations at *read time* — never from a background job having
already run (BR-INST-019, FR-INST-122). ``grace_period_days`` MUST be the
value frozen in the owning contract's ``terms_snapshot`` at activation
(FR-INST-172, BR-INST-009), never a live ``InstallmentConfiguration``
read — a later tenant policy change must never retroactively alter an
already-active contract's overdue determination.

State precedence (highest to lowest — matches FR-INST-120's enumeration
order and Scenario E's "past grace *without payment*" phrasing, which
implies a partial payment takes priority over an overdue/upcoming
classification, not the reverse):

    VOIDED > WAIVED > PAID > PARTIALLY_PAID > OVERDUE > DUE > UPCOMING

``VOIDED``/``WAIVED`` are the two controlled-workflow exceptions
(FR-INST-120) — reachable only via ``schedule_line.voided_at``/
``waived_at``, never derived from dates/amounts.

Spec ref: specs/010-installments/spec.md FR-INST-120/121/122/160/161;
specs/010-installments/plan.md §14.1, ADR-INST-05.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class DueStateResult:
    """The derived state plus the figures it was computed from —
    returned together so a caller never has to re-derive ``days_overdue``
    or ``outstanding_amount`` separately and risk disagreement."""

    state: str
    outstanding_amount: Decimal
    days_overdue: int


class DueStateCalculator:
    """Pure — no I/O, no side effects, no dependency on wall-clock time
    (the caller supplies ``business_date`` via
    ``modules.installments.services.business_date.get_business_date()``,
    FR-INST-115)."""

    @staticmethod
    def calculate(
        *,
        scheduled_amount: Decimal,
        paid_amount: Decimal,
        due_date: date,
        business_date: date,
        grace_period_days: int,
        waived_at: datetime | None = None,
        voided_at: datetime | None = None,
    ) -> DueStateResult:
        outstanding = scheduled_amount - paid_amount
        days_overdue = max((business_date - due_date).days, 0)

        if voided_at is not None:
            return DueStateResult("VOIDED", outstanding, days_overdue)
        if waived_at is not None:
            return DueStateResult("WAIVED", outstanding, days_overdue)
        if outstanding <= Decimal("0"):
            return DueStateResult("PAID", outstanding, 0)
        if paid_amount > Decimal("0"):
            return DueStateResult("PARTIALLY_PAID", outstanding, days_overdue)

        grace_end = due_date + timedelta(days=grace_period_days)
        if business_date > grace_end:
            return DueStateResult("OVERDUE", outstanding, days_overdue)
        if business_date >= due_date:
            return DueStateResult("DUE", outstanding, days_overdue)
        return DueStateResult("UPCOMING", outstanding, 0)

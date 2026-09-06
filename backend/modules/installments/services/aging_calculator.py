"""InstallmentAgingCalculator — module-local free function replicating
Accounting's exact aging-bucket boundaries (T139, spec.md Assumption A7).

Bucket boundary logic is a deliberate line-for-line replication of
``modules.accounting.services.aging_calculator._bucket_for`` — Installments
does not import Accounting's aging module (Accounting's buckets are keyed
by ``CustomerLedger``/``ARTransaction``, an unrelated aggregate shape;
importing it would create a coupling the two-line boundary function
doesn't warrant). Divergence between the two implementations would violate
spec.md Assumption A7 ("Aging buckets reuse Accounting's existing
convention exactly") — kept identical by inspection, not by shared code.

Spec ref: specs/010-installments/spec.md FR-INST-180/181, Assumption A7.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

_BUCKET_FIELDS = (
    "current",
    "days_1_30",
    "days_31_60",
    "days_61_90",
    "days_91_120",
    "days_120_plus",
)


def bucket_for(due_date: date, as_of_date: date) -> str:
    """Current | 1-30 | 31-60 | 61-90 | 91-120 | 120+ days overdue,
    identical boundary logic to Accounting's ``AgingCalculator``."""
    days_overdue = (as_of_date - due_date).days
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "days_1_30"
    if days_overdue <= 60:
        return "days_31_60"
    if days_overdue <= 90:
        return "days_61_90"
    if days_overdue <= 120:
        return "days_91_120"
    return "days_120_plus"


@dataclass
class InstallmentAgingRow:
    current: Decimal = Decimal("0")
    days_1_30: Decimal = Decimal("0")
    days_31_60: Decimal = Decimal("0")
    days_61_90: Decimal = Decimal("0")
    days_91_120: Decimal = Decimal("0")
    days_120_plus: Decimal = Decimal("0")

    @property
    def total(self) -> Decimal:
        return sum((getattr(self, f) for f in _BUCKET_FIELDS), Decimal("0"))


class InstallmentAgingCalculator:
    """Pure aggregation over caller-supplied ``(due_date, outstanding_amount)``
    pairs — no I/O, no dependency on which service derived the outstanding
    figures (schedule lines today; late-charge AR is aggregated
    separately by whichever Phase-12 reporting caller needs it)."""

    @staticmethod
    def bucket_for(due_date: date, as_of_date: date) -> str:
        return bucket_for(due_date, as_of_date)

    @staticmethod
    def aggregate(
        outstanding_lines: list[tuple[date, Decimal]], as_of_date: date
    ) -> InstallmentAgingRow:
        row = InstallmentAgingRow()
        for due_date, outstanding_amount in outstanding_lines:
            if outstanding_amount <= Decimal("0"):
                continue
            bucket = bucket_for(due_date, as_of_date)
            setattr(row, bucket, getattr(row, bucket) + outstanding_amount)
        return row

"""Single business-date source (FR-INST-115).

Schedule generation and all due-date evaluation must use one consistent
"as of" date — never an ad hoc ``datetime.now()`` read inside a service.
Server UTC date; conversion to tenant-local happens only at presentation,
mirroring the business-date convention Accounting already uses.

Spec ref: specs/010-installments/plan.md §10.2.
"""

from __future__ import annotations

from datetime import date

from core.utils.datetime import utcnow


def get_business_date() -> date:
    """The current business date (server UTC, presentation-agnostic)."""
    return utcnow().date()

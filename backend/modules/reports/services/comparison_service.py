"""Comparison computation (spec §23, plan.md §20).

Given two already-fetched numeric values (the caller is responsible for
calling the *same* adapter method a second time for the comparison
period — this service never re-derives a number differently, FR-RPT-140),
computes absolute/percentage change in ``Decimal``.

Zero-denominator and incomplete-period rules follow spec §23 exactly:
- prior == 0 and current != 0 -> NOT_COMPARABLE (no infinite/undefined %).
- prior == 0 and current == 0 -> 0% (comparable, not "not comparable").
- the current period is itself partial (FR-RPT-142) -> PARTIAL_CURRENT_PERIOD,
  reported alongside whatever change value was still computed.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from modules.reports.schemas.common import Comparability, ComparisonResult

_PERCENTAGE_QUANTIZE = Decimal("0.01")


def compute_comparison(
    current: Decimal,
    prior: Decimal,
    *,
    is_current_period_partial: bool = False,
) -> ComparisonResult:
    """Compute the comparison between *current* and *prior* period values."""
    absolute_change = current - prior

    if prior == 0:
        if current == 0:
            percentage_change: Decimal | None = Decimal("0")
            comparability = Comparability.FULL
        else:
            percentage_change = None
            comparability = Comparability.NOT_COMPARABLE
    else:
        percentage_change = ((absolute_change / prior) * Decimal("100")).quantize(
            _PERCENTAGE_QUANTIZE, rounding=ROUND_HALF_UP
        )
        comparability = Comparability.FULL

    if is_current_period_partial and comparability is not Comparability.NOT_COMPARABLE:
        comparability = Comparability.PARTIAL_CURRENT_PERIOD

    return ComparisonResult(
        absolute_change=str(absolute_change),
        percentage_change=(
            str(percentage_change) if percentage_change is not None else None
        ),
        comparability=comparability,
    )

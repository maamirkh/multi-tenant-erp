"""Money normalization (spec §24, plan.md §20).

Cross-precision combination — Sales/Purchase (`NUMERIC(15,2)`) figures
combined with Accounting/Installments (`NUMERIC(20,6)`) figures — is
performed at `NUMERIC(20,6)` precision, rounding only at final display
(Assumption A4, FR-RPT-150/151/154). Mirrors Installments'
``Decimal("0.000001")``/``ROUND_HALF_UP`` precedent exactly — no new
rounding convention invented.

``Decimal`` exclusively — no ``float`` anywhere in this module or its call
chain (Constitution §17, FR-RPT-150).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_INTERNAL_QUANTIZE = Decimal("0.000001")  # NUMERIC(20,6)


def normalize_amount(amount: Decimal) -> Decimal:
    """Promote *amount* to the shared ``NUMERIC(20,6)`` internal precision
    used for any arithmetic combining Sales/Purchase and Accounting/
    Installments figures."""
    return amount.quantize(_INTERNAL_QUANTIZE, rounding=ROUND_HALF_UP)


def round_for_display(amount: Decimal, decimal_places: int) -> Decimal:
    """Round *amount* to *decimal_places* (the tenant's configured currency
    decimal places) using ``ROUND_HALF_UP`` — applied only at final
    display, never mid-calculation."""
    display_quantize = Decimal(1).scaleb(-decimal_places)
    return amount.quantize(display_quantize, rounding=ROUND_HALF_UP)

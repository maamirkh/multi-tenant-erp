"""T027 — ``money_normalization`` uses ``Decimal`` exclusively, never
``float`` (FR-RPT-150)."""

from __future__ import annotations

import inspect
from decimal import Decimal

from modules.reports.services import money_normalization
from modules.reports.services.money_normalization import (
    normalize_amount,
    round_for_display,
)


def test_normalize_amount_promotes_to_numeric_20_6() -> None:
    result = normalize_amount(Decimal("12.5"))
    assert result == Decimal("12.500000")
    assert isinstance(result, Decimal)


def test_normalize_amount_rounds_half_up_at_sixth_decimal() -> None:
    result = normalize_amount(Decimal("1.0000005"))
    assert result == Decimal("1.000001")


def test_round_for_display_uses_configured_decimal_places() -> None:
    amount = normalize_amount(Decimal("12.3456789"))
    assert round_for_display(amount, 2) == Decimal("12.35")
    assert round_for_display(amount, 0) == Decimal("12")


def test_no_float_anywhere_in_module_source() -> None:
    """Static guard: no ``float`` literal/cast appears in the module's
    own source (Constitution §17) — the call chain never introduces
    floating-point arithmetic."""
    source = inspect.getsource(money_normalization)
    assert "float(" not in source
    assert ": float" not in source

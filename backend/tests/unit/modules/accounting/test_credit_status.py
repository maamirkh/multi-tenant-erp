"""Unit tests for credit status auto-calculation — Phase 6.

Tests (tasks.md T152):
  0% = GOOD, 79% = GOOD, 80% = WARNING, 100% = EXCEEDED, 101% = EXCEEDED.
  Also covers: zero credit limit (unlimited -> always GOOD) and a custom
  warning threshold override.

Spec ref: specs/008-accounting-finance/tasks.md T152, T139
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from modules.accounting.services.ar_service import AccountsReceivableService


class TestComputeCreditStatus:
    @pytest.mark.parametrize(
        "outstanding,limit,expected",
        [
            ("0", "10000", "GOOD"),
            ("7900", "10000", "GOOD"),
            ("8000", "10000", "WARNING"),
            ("9999", "10000", "WARNING"),
            ("10000", "10000", "EXCEEDED"),
            ("10100", "10000", "EXCEEDED"),
        ],
    )
    def test_boundaries(self, outstanding: str, limit: str, expected: str) -> None:
        result = AccountsReceivableService.compute_credit_status(
            Decimal(outstanding), Decimal(limit)
        )
        assert result == expected

    def test_zero_credit_limit_is_always_good(self) -> None:
        assert (
            AccountsReceivableService.compute_credit_status(
                Decimal("500000"), Decimal("0")
            )
            == "GOOD"
        )

    def test_never_returns_hold(self) -> None:
        result = AccountsReceivableService.compute_credit_status(
            Decimal("999999"), Decimal("1")
        )
        assert result != "HOLD"

    def test_custom_warning_threshold(self) -> None:
        result = AccountsReceivableService.compute_credit_status(
            Decimal("6000"), Decimal("10000"), warning_threshold_pct=Decimal("50")
        )
        assert result == "WARNING"

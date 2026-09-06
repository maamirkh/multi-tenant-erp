"""Unit tests for MarginGuardService — Phase 2.

Tests:
  - OK when margin >= threshold
  - WARN when margin < threshold and block_on_low_margin=False
  - BLOCK when margin < threshold and block_on_low_margin=True
  - WARN when unit_price = 0 (cannot compute margin)
  - WARN when cost_price = 0
  - OK when min_margin_pct is None (guard disabled)
  - Margin percentage computed correctly

Task: T079
Spec ref: specs/007-sales-management/plan.md §Phase 2 MarginGuardService
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from modules.sales.services.pricing_service import MarginGuardService


@pytest.fixture()
def service() -> MarginGuardService:
    return MarginGuardService()


# ---------------------------------------------------------------------------
# Guard Disabled
# ---------------------------------------------------------------------------


class TestGuardDisabled:
    def test_none_threshold_returns_ok(self, service: MarginGuardService) -> None:
        result = service.check_margin(
            unit_price=Decimal("100"),
            cost_price=Decimal("90"),
            min_margin_pct=None,
        )
        assert result.action == "OK"
        assert result.passes is True

    def test_none_threshold_zero_prices_still_ok(
        self, service: MarginGuardService
    ) -> None:
        result = service.check_margin(
            unit_price=Decimal("0"),
            cost_price=Decimal("0"),
            min_margin_pct=None,
        )
        assert result.action == "OK"
        assert result.passes is True


# ---------------------------------------------------------------------------
# Normal Margin Calculation
# ---------------------------------------------------------------------------


class TestMarginCalculation:
    def test_margin_above_threshold_returns_ok(
        self, service: MarginGuardService
    ) -> None:
        # margin = (100 - 70) / 100 * 100 = 30%
        result = service.check_margin(
            unit_price=Decimal("100"),
            cost_price=Decimal("70"),
            min_margin_pct=Decimal("20"),
        )
        assert result.action == "OK"
        assert result.passes is True
        assert result.margin_percentage == Decimal("30.00")

    def test_margin_exactly_at_threshold_returns_ok(
        self, service: MarginGuardService
    ) -> None:
        # margin = (100 - 80) / 100 * 100 = 20%
        result = service.check_margin(
            unit_price=Decimal("100"),
            cost_price=Decimal("80"),
            min_margin_pct=Decimal("20"),
        )
        assert result.action == "OK"
        assert result.passes is True
        assert result.margin_percentage == Decimal("20.00")

    def test_margin_below_threshold_returns_warn(
        self, service: MarginGuardService
    ) -> None:
        # margin = (100 - 90) / 100 * 100 = 10%
        result = service.check_margin(
            unit_price=Decimal("100"),
            cost_price=Decimal("90"),
            min_margin_pct=Decimal("20"),
        )
        assert result.action == "WARN"
        assert result.passes is False

    def test_margin_below_threshold_with_block_returns_block(
        self, service: MarginGuardService
    ) -> None:
        result = service.check_margin(
            unit_price=Decimal("100"),
            cost_price=Decimal("90"),
            min_margin_pct=Decimal("20"),
            block_on_low_margin=True,
        )
        assert result.action == "BLOCK"
        assert result.passes is False

    def test_margin_percentage_computed_correctly(
        self, service: MarginGuardService
    ) -> None:
        # margin = (150 - 100) / 150 * 100 = 33.33%
        result = service.check_margin(
            unit_price=Decimal("150"),
            cost_price=Decimal("100"),
            min_margin_pct=Decimal("10"),
        )
        assert result.action == "OK"
        assert result.margin_percentage == Decimal("33.33")


# ---------------------------------------------------------------------------
# Edge Cases — Zero / Negative Prices
# ---------------------------------------------------------------------------


class TestZeroPriceEdgeCases:
    def test_zero_unit_price_returns_warn(self, service: MarginGuardService) -> None:
        result = service.check_margin(
            unit_price=Decimal("0"),
            cost_price=Decimal("50"),
            min_margin_pct=Decimal("20"),
        )
        assert result.action == "WARN"
        assert result.passes is False
        assert result.margin_percentage == Decimal("0")

    def test_zero_cost_price_returns_warn(self, service: MarginGuardService) -> None:
        result = service.check_margin(
            unit_price=Decimal("100"),
            cost_price=Decimal("0"),
            min_margin_pct=Decimal("20"),
        )
        assert result.action == "WARN"
        assert result.passes is False

    def test_negative_unit_price_returns_warn(
        self, service: MarginGuardService
    ) -> None:
        result = service.check_margin(
            unit_price=Decimal("-10"),
            cost_price=Decimal("5"),
            min_margin_pct=Decimal("20"),
        )
        assert result.action == "WARN"
        assert result.passes is False

    def test_negative_cost_price_returns_warn(
        self, service: MarginGuardService
    ) -> None:
        result = service.check_margin(
            unit_price=Decimal("100"),
            cost_price=Decimal("-10"),
            min_margin_pct=Decimal("20"),
        )
        assert result.action == "WARN"
        assert result.passes is False


# ---------------------------------------------------------------------------
# Threshold in Result
# ---------------------------------------------------------------------------


class TestThresholdInResult:
    def test_threshold_reflected_in_result(self, service: MarginGuardService) -> None:
        result = service.check_margin(
            unit_price=Decimal("100"),
            cost_price=Decimal("80"),
            min_margin_pct=Decimal("25"),
        )
        assert result.threshold_pct == Decimal("25")

    def test_zero_threshold_allows_any_positive_margin(
        self, service: MarginGuardService
    ) -> None:
        result = service.check_margin(
            unit_price=Decimal("100"),
            cost_price=Decimal("99"),
            min_margin_pct=Decimal("0"),
        )
        assert result.action == "OK"
        assert result.passes is True

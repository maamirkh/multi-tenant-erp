"""Unit tests for KPI formula helpers — Phase 8.

Tests:
  - _pct  : percentage calculation
  - _div  : safe division
  - _trend: trend direction and change computation
  - _period_label: human-readable period label
  - _prev_period: previous-period calculation

Task: T218
Spec ref: specs/007-sales-management/spec.md §36
"""

from __future__ import annotations

from decimal import Decimal

from modules.sales.services.kpi_service import (
    _div,
    _pct,
    _period_label,
    _prev_period,
    _trend,
)

# ---------------------------------------------------------------------------
# _pct — percentage
# ---------------------------------------------------------------------------


class TestPct:
    def test_basic_percentage(self) -> None:
        result = _pct(Decimal("25"), Decimal("100"))
        assert result == Decimal("25.00")

    def test_decimal_percentage(self) -> None:
        result = _pct(Decimal("1"), Decimal("3"))
        assert result is not None
        assert abs(result - Decimal("33.33")) < Decimal("0.01")

    def test_zero_denominator_returns_none(self) -> None:
        assert _pct(Decimal("10"), Decimal("0")) is None

    def test_none_numerator_returns_none(self) -> None:
        assert _pct(None, Decimal("100")) is None

    def test_none_denominator_returns_none(self) -> None:
        assert _pct(Decimal("50"), None) is None

    def test_both_none_returns_none(self) -> None:
        assert _pct(None, None) is None

    def test_zero_numerator(self) -> None:
        result = _pct(Decimal("0"), Decimal("100"))
        assert result == Decimal("0.00")

    def test_greater_than_100(self) -> None:
        result = _pct(Decimal("200"), Decimal("100"))
        assert result == Decimal("200.00")


# ---------------------------------------------------------------------------
# _div — safe division
# ---------------------------------------------------------------------------


class TestDiv:
    def test_basic_division(self) -> None:
        result = _div(Decimal("10"), Decimal("4"))
        assert result == Decimal("2.50")

    def test_zero_denominator(self) -> None:
        assert _div(Decimal("10"), Decimal("0")) is None

    def test_none_inputs(self) -> None:
        assert _div(None, Decimal("4")) is None
        assert _div(Decimal("10"), None) is None

    def test_rounding(self) -> None:
        result = _div(Decimal("1"), Decimal("3"))
        assert result is not None
        assert abs(result - Decimal("0.33")) < Decimal("0.01")


# ---------------------------------------------------------------------------
# _trend — trend direction
# ---------------------------------------------------------------------------


class TestTrend:
    def test_up_trend(self) -> None:
        t, chg = _trend(Decimal("110"), Decimal("100"))
        assert t == "UP"
        assert chg == Decimal("10.00")

    def test_down_trend(self) -> None:
        t, chg = _trend(Decimal("90"), Decimal("100"))
        assert t == "DOWN"

    def test_stable_trend(self) -> None:
        t, chg = _trend(Decimal("101"), Decimal("100"))
        assert t == "STABLE"

    def test_none_current(self) -> None:
        t, chg = _trend(None, Decimal("100"))
        assert t is None
        assert chg is None

    def test_none_previous(self) -> None:
        t, chg = _trend(Decimal("100"), None)
        assert t is None

    def test_zero_previous_positive_current(self) -> None:
        t, chg = _trend(Decimal("50"), Decimal("0"))
        assert t == "UP"

    def test_zero_previous_zero_current(self) -> None:
        t, chg = _trend(Decimal("0"), Decimal("0"))
        assert t == "STABLE"


# ---------------------------------------------------------------------------
# _period_label
# ---------------------------------------------------------------------------


class TestPeriodLabel:
    def test_with_explicit_dates(self) -> None:
        label = _period_label("2026-01-01", "2026-01-31")
        assert "2026-01-01" in label
        assert "2026-01-31" in label

    def test_without_dates_returns_month(self) -> None:
        label = _period_label(None, None)
        # Should return something like "2026-08"
        assert len(label) == 7
        assert label[4] == "-"


# ---------------------------------------------------------------------------
# _prev_period
# ---------------------------------------------------------------------------


class TestPrevPeriod:
    def test_simple_month_range(self) -> None:
        # Equal-length window: 2026-02-01 to 2026-02-28 = 28 days
        # prev_to = 2026-01-31, prev_from = 2026-01-31 - 27 = 2026-01-04
        prev_from, prev_to = _prev_period("2026-02-01", "2026-02-28")
        assert prev_to == "2026-01-31"
        assert prev_from == "2026-01-04"

    def test_none_returns_last_calendar_month(self) -> None:
        prev_from, prev_to = _prev_period(None, None)
        # Both should be valid ISO date strings
        from datetime import date as dt_date

        dt_date.fromisoformat(prev_from)
        dt_date.fromisoformat(prev_to)
        assert prev_from <= prev_to

    def test_symmetric_range(self) -> None:
        # 2026-08-01 to 2026-08-31 = 31 days; prev window of 31 days ending 2026-07-31
        prev_from, prev_to = _prev_period("2026-08-01", "2026-08-31")
        assert prev_to == "2026-07-31"
        assert prev_from == "2026-07-01"

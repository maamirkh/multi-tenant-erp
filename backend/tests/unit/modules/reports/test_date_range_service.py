"""T023 — ``date_range_service.resolve_period()`` correctness.

Covers all 11 presets (FR-RPT-130), a year-boundary custom range
(FR-RPT-134), and mid-month "This Month" partial-period flagging
(FR-RPT-142).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from modules.reports.schemas.common import PeriodPreset
from modules.reports.services.date_range_service import resolve_period

_UTC = ZoneInfo("UTC")

# Fixed "now": 2026-03-15 (a Sunday), mid-month, mid-quarter (Q1), mid-year.
_NOW = datetime(2026, 3, 15, 12, 0, 0, tzinfo=_UTC)


def test_today() -> None:
    r = resolve_period(PeriodPreset.TODAY, "UTC", now=_NOW)
    assert r.start == "2026-03-15T00:00:00+00:00"
    assert r.end == "2026-03-16T00:00:00+00:00"
    assert r.is_partial_current_period is True


def test_yesterday() -> None:
    r = resolve_period(PeriodPreset.YESTERDAY, "UTC", now=_NOW)
    assert r.start == "2026-03-14T00:00:00+00:00"
    assert r.end == "2026-03-15T00:00:00+00:00"
    assert r.is_partial_current_period is False


def test_this_week() -> None:
    # 2026-03-15 is a Sunday -> ISO week starts Monday 2026-03-09.
    r = resolve_period(PeriodPreset.THIS_WEEK, "UTC", now=_NOW)
    assert r.start == "2026-03-09T00:00:00+00:00"
    assert r.end == "2026-03-16T00:00:00+00:00"
    assert r.is_partial_current_period is True


def test_last_week() -> None:
    r = resolve_period(PeriodPreset.LAST_WEEK, "UTC", now=_NOW)
    assert r.start == "2026-03-02T00:00:00+00:00"
    assert r.end == "2026-03-09T00:00:00+00:00"
    assert r.is_partial_current_period is False


def test_this_month_is_partial() -> None:
    r = resolve_period(PeriodPreset.THIS_MONTH, "UTC", now=_NOW)
    assert r.start == "2026-03-01T00:00:00+00:00"
    assert r.end == "2026-04-01T00:00:00+00:00"
    assert r.is_partial_current_period is True


def test_last_month() -> None:
    r = resolve_period(PeriodPreset.LAST_MONTH, "UTC", now=_NOW)
    assert r.start == "2026-02-01T00:00:00+00:00"
    assert r.end == "2026-03-01T00:00:00+00:00"
    assert r.is_partial_current_period is False


def test_this_quarter() -> None:
    r = resolve_period(PeriodPreset.THIS_QUARTER, "UTC", now=_NOW)
    assert r.start == "2026-01-01T00:00:00+00:00"
    assert r.end == "2026-04-01T00:00:00+00:00"
    assert r.is_partial_current_period is True


def test_last_quarter() -> None:
    r = resolve_period(PeriodPreset.LAST_QUARTER, "UTC", now=_NOW)
    assert r.start == "2025-10-01T00:00:00+00:00"
    assert r.end == "2026-01-01T00:00:00+00:00"
    assert r.is_partial_current_period is False


def test_this_year() -> None:
    r = resolve_period(PeriodPreset.THIS_YEAR, "UTC", now=_NOW)
    assert r.start == "2026-01-01T00:00:00+00:00"
    assert r.end == "2027-01-01T00:00:00+00:00"
    assert r.is_partial_current_period is True


def test_last_year() -> None:
    r = resolve_period(PeriodPreset.LAST_YEAR, "UTC", now=_NOW)
    assert r.start == "2025-01-01T00:00:00+00:00"
    assert r.end == "2026-01-01T00:00:00+00:00"
    assert r.is_partial_current_period is False


def test_custom_range_crossing_year_boundary() -> None:
    r = resolve_period(
        PeriodPreset.CUSTOM,
        "UTC",
        custom_start="2025-12-20",
        custom_end="2026-01-10",
        now=_NOW,
    )
    assert r.start == "2025-12-20T00:00:00+00:00"
    # end is exclusive: custom_end's day + 1
    assert r.end == "2026-01-11T00:00:00+00:00"
    assert r.is_partial_current_period is False


def test_company_timezone_shifts_utc_boundaries() -> None:
    # America/New_York is already in EDT (UTC-4) by 2026-03-15 (DST began
    # 2026-03-08) -> both boundaries share the -04:00 offset.
    r = resolve_period(PeriodPreset.TODAY, "America/New_York", now=_NOW)
    assert r.start == "2026-03-15T04:00:00+00:00"
    assert r.end == "2026-03-16T04:00:00+00:00"

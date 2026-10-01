"""Resolves the 11 standard period presets (spec §22, FR-RPT-130..134)
into half-open ``[start, end)`` UTC intervals, computed against the
requesting company's own local timezone — never the server's local
timezone or a blanket UTC assumption for a company that has configured
one.

No new timezone library: ``zoneinfo`` (stdlib) + the platform's existing
``core/utils/datetime.py::ensure_utc()``/``utcnow()`` convention.

Spec ref: specs/011-reports-analytics/plan.md §20.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from core.utils.datetime import ensure_utc, utcnow
from modules.reports.exceptions import FilterValidationError
from modules.reports.schemas.common import (
    ComparisonType,
    PeriodPreset,
    PeriodResolution,
)

_DEFAULT_TIMEZONE = "UTC"

# Presets whose end boundary is "now" from the company's own local
# perspective — always (or virtually always) incomplete when queried
# (FR-RPT-142).
_CURRENT_PERIOD_PRESETS = frozenset(
    {
        PeriodPreset.TODAY,
        PeriodPreset.THIS_WEEK,
        PeriodPreset.THIS_MONTH,
        PeriodPreset.THIS_QUARTER,
        PeriodPreset.THIS_YEAR,
    }
)


def _start_of_day(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _quarter_start(d: date) -> date:
    quarter_start_month = ((d.month - 1) // 3) * 3 + 1
    return date(d.year, quarter_start_month, 1)


def resolve_period(
    preset: PeriodPreset,
    timezone: str | None,
    *,
    custom_start: str | None = None,
    custom_end: str | None = None,
    now: datetime | None = None,
) -> PeriodResolution:
    """Resolve *preset* into a ``PeriodResolution`` in the company's local
    timezone, converted to UTC boundaries.

    Args:
        preset: One of the 11 standard presets.
        timezone: The company's ``default_timezone`` (IANA identifier),
            or ``None`` — treated as ``"UTC"`` per spec's documented
            default.
        custom_start/custom_end: Required (ISO-8601 dates) iff
            ``preset == PeriodPreset.CUSTOM``.
        now: Injectable "current instant" for deterministic tests;
            defaults to ``utcnow()``.
    """
    tz_name = timezone or _DEFAULT_TIMEZONE
    tz = ZoneInfo(tz_name)
    now_utc = ensure_utc(now or utcnow())
    now_local = now_utc.astimezone(tz)
    today = now_local.date()

    start_date: date
    end_date: date  # exclusive

    if preset is PeriodPreset.TODAY:
        start_date, end_date = today, today + timedelta(days=1)
    elif preset is PeriodPreset.YESTERDAY:
        start_date, end_date = today - timedelta(days=1), today
    elif preset is PeriodPreset.THIS_WEEK:
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=7)
    elif preset is PeriodPreset.LAST_WEEK:
        this_week_start = today - timedelta(days=today.weekday())
        start_date = this_week_start - timedelta(days=7)
        end_date = this_week_start
    elif preset is PeriodPreset.THIS_MONTH:
        start_date = date(today.year, today.month, 1)
        end_date = _add_months(start_date, 1)
    elif preset is PeriodPreset.LAST_MONTH:
        this_month_start = date(today.year, today.month, 1)
        start_date = _add_months(this_month_start, -1)
        end_date = this_month_start
    elif preset is PeriodPreset.THIS_QUARTER:
        start_date = _quarter_start(today)
        end_date = _add_months(start_date, 3)
    elif preset is PeriodPreset.LAST_QUARTER:
        this_quarter_start = _quarter_start(today)
        start_date = _add_months(this_quarter_start, -3)
        end_date = this_quarter_start
    elif preset is PeriodPreset.THIS_YEAR:
        start_date = date(today.year, 1, 1)
        end_date = date(today.year + 1, 1, 1)
    elif preset is PeriodPreset.LAST_YEAR:
        start_date = date(today.year - 1, 1, 1)
        end_date = date(today.year, 1, 1)
    elif preset is PeriodPreset.CUSTOM:
        if not custom_start or not custom_end:
            raise FilterValidationError(
                "period",
                "custom_start and custom_end are required when period=custom",
            )
        start_date = date.fromisoformat(custom_start)
        end_date = date.fromisoformat(custom_end) + timedelta(days=1)
    else:  # pragma: no cover — exhaustive over PeriodPreset
        raise FilterValidationError("period", f"Unsupported period preset '{preset}'")

    start_local = _start_of_day(start_date).replace(tzinfo=tz)
    end_local = _start_of_day(end_date).replace(tzinfo=tz)

    is_partial = preset in _CURRENT_PERIOD_PRESETS and now_local < end_local

    return PeriodResolution(
        start=ensure_utc(start_local).isoformat(),
        end=ensure_utc(end_local).isoformat(),
        timezone=tz_name,
        is_partial_current_period=is_partial,
    )


def resolve_comparison_period(
    period: PeriodResolution, comparison_type: ComparisonType
) -> PeriodResolution:
    """Shift *period*'s ``[start, end)`` boundaries per *comparison_type*
    (spec §23, FR-RPT-140) — used by the Executive Dashboard (T148) to call
    the same adapter method a second time for the comparison period,
    exactly like ``comparison_service.py``'s own docstring requires (the
    caller supplies two already-fetched values; this function only
    resolves *which* second period to fetch, never a value itself).

    - ``PREVIOUS_PERIOD``: the immediately preceding interval of the same
      length.
    - ``PREVIOUS_MONTH``/``PREVIOUS_QUARTER``: shift both boundaries by
      1/3 calendar months (day-of-month preserved where possible).
    - ``PREVIOUS_YEAR``/``SAME_PERIOD_LAST_YEAR``: shift both boundaries by
      exactly one calendar year (both resolve identically here — the
      distinction only matters when the *current* period itself spans
      more than a year, which no standard preset does).
    """
    tz = ZoneInfo(period.timezone)
    start = datetime.fromisoformat(period.start).astimezone(tz)
    end = datetime.fromisoformat(period.end).astimezone(tz)

    if comparison_type is ComparisonType.PREVIOUS_PERIOD:
        length = end - start
        new_start, new_end = start - length, start
    elif comparison_type is ComparisonType.PREVIOUS_MONTH:
        new_start, new_end = _shift_months(start, -1), _shift_months(end, -1)
    elif comparison_type is ComparisonType.PREVIOUS_QUARTER:
        new_start, new_end = _shift_months(start, -3), _shift_months(end, -3)
    else:
        assert comparison_type in (
            ComparisonType.PREVIOUS_YEAR,
            ComparisonType.SAME_PERIOD_LAST_YEAR,
        )
        new_start = start.replace(year=start.year - 1)
        new_end = end.replace(year=end.year - 1)

    return PeriodResolution(
        start=ensure_utc(new_start).isoformat(),
        end=ensure_utc(new_end).isoformat(),
        timezone=period.timezone,
        is_partial_current_period=False,
    )


def _shift_months(moment: datetime, months: int) -> datetime:
    month_index = moment.month - 1 + months
    year = moment.year + month_index // 12
    month = month_index % 12 + 1
    return moment.replace(year=year, month=month)

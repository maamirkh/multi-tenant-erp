"""Shared Reports contracts (plan.md §7/§18/§19/§20/§25/§26).

Declared in dependency order so nothing in this module forward-references
a type defined later in the same file: ``JsonValue`` → ``PeriodPreset`` →
``PeriodResolution`` → ``FreshnessClassification`` → ``ComparisonRequest``/
``ComparisonResult`` → ``DrillDownRef`` → ``ReportEnvelopeMeta``.

Spec ref: specs/011-reports-analytics/{spec.md §22/§23/§27, plan.md
§7/§18/§20/§25/§26}.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# JsonValue — recursive JSON alias for raw JSONB persistence columns only
# (e.g. SavedReportView.filter_config, Phase 1). NOT a Reports-contract
# `Any` exception: this alias never appears in an execution/service/
# adapter signature, only on a persistence model's JSONB column type.
# ---------------------------------------------------------------------------

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)


# ---------------------------------------------------------------------------
# Period presets & resolution (spec §22)
# ---------------------------------------------------------------------------


class PeriodPreset(StrEnum):
    """The 11 standard period presets (FR-RPT-130)."""

    TODAY = "today"
    YESTERDAY = "yesterday"
    THIS_WEEK = "this_week"
    LAST_WEEK = "last_week"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    THIS_QUARTER = "this_quarter"
    LAST_QUARTER = "last_quarter"
    THIS_YEAR = "this_year"
    LAST_YEAR = "last_year"
    CUSTOM = "custom"


class PeriodResolution(BaseModel):
    """A resolved, half-open ``[start, end)`` UTC interval (FR-RPT-131/132),
    computed from a ``PeriodPreset`` + the company's own
    ``default_timezone``."""

    model_config = ConfigDict(frozen=True)

    start: str  # ISO-8601 UTC instant
    end: str  # ISO-8601 UTC instant, exclusive
    timezone: str  # IANA identifier the boundaries were computed against
    is_partial_current_period: bool = False


# ---------------------------------------------------------------------------
# Freshness (plan.md §26)
# ---------------------------------------------------------------------------


class FreshnessClassification(StrEnum):
    """Always ``TRANSACTIONAL_LIVE`` for every Epic 11 report (FR-RPT-230).
    ``CACHED_N_MINUTES`` is reserved, unused — it exists only so a future
    caching layer has a place to add a value without a breaking response-
    shape change (FR-RPT-231/232)."""

    TRANSACTIONAL_LIVE = "transactional_live"
    CACHED_N_MINUTES = "cached_n_minutes"


# ---------------------------------------------------------------------------
# Comparison (spec §23, plan.md §20)
# ---------------------------------------------------------------------------


class ComparisonType(StrEnum):
    PREVIOUS_PERIOD = "previous_period"
    PREVIOUS_MONTH = "previous_month"
    PREVIOUS_QUARTER = "previous_quarter"
    PREVIOUS_YEAR = "previous_year"
    SAME_PERIOD_LAST_YEAR = "same_period_last_year"


class Comparability(StrEnum):
    FULL = "full"
    NOT_COMPARABLE = "not_comparable"
    PARTIAL_CURRENT_PERIOD = "partial_current_period"


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    comparison_type: ComparisonType


class ComparisonResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    absolute_change: str  # Decimal serialized as string — never a float (FR-RPT-150)
    percentage_change: str | None  # None when comparability is NOT_COMPARABLE
    comparability: Comparability


# ---------------------------------------------------------------------------
# Drill-down (runtime payload — distinct from the registry-time
# ``DrillDownTarget`` dataclass, T019/registry/definitions.py)
# ---------------------------------------------------------------------------


class CurrencyAmount(BaseModel):
    """One currency's own figure (FR-RPT-152). Aggregates that span several
    currencies are reported as a list of these — never summed together.
    ``currency_code`` is ``None`` only where the source record has none."""

    currency_code: str | None
    amount: Decimal
    comparison: ComparisonResult | None = None


def single_currency_amount(amounts: list[CurrencyAmount]) -> CurrencyAmount | None:
    """The one entry when exactly one currency is present, else ``None`` —
    the rule for every legacy single-value field (FR-RPT-152)."""
    return amounts[0] if len(amounts) == 1 else None


class DrillDownRef(BaseModel):
    """A resolved drill-down link embedded in a response's
    ``ReportEnvelopeMeta`` — the registry-time ``DrillDownTarget`` with its
    ``target_route`` template filled in and originating filters preserved
    (FR-RPT-180/182)."""

    model_config = ConfigDict(frozen=True)

    label: str
    target_route: str
    required_permission: str


# ---------------------------------------------------------------------------
# Response envelope metadata (plan.md §18, FR-RPT-311)
# ---------------------------------------------------------------------------


class ReportEnvelopeMeta(BaseModel):
    """Embedded in every Epic 11 typed response's top level — never a
    change to ``StandardResponse[T]``/``PaginatedResponse[T]`` themselves
    (FR-RPT-310/Assumption A10)."""

    report_key: str
    applied_filters: dict[str, JsonValue]
    period: PeriodResolution
    freshness: FreshnessClassification
    drill_down: list[DrillDownRef] = []
    comparison: ComparisonResult | None = None
    read_only_servicing_continuity: bool = False
    """True only for an Installments report served under Case B
    (disabled entitlement, but existing obligations being serviced —
    Phase 2's ``InstallmentsServicingContinuityGate``). Set by
    ``ReportExecutionService`` after the adapter returns, never by the
    (entitlement-unaware) adapter itself. ``False`` for every other
    report (Phase 3, T126/T142)."""


# ---------------------------------------------------------------------------
# Date-range filter mixin (T015)
# ---------------------------------------------------------------------------


class DateRangeFilter(BaseModel):
    """Base mixin for any report filter schema needing a period (FR-RPT-133).
    Concrete filter schemas compose this with ``extra="forbid"`` and their
    own report-specific fields."""

    model_config = ConfigDict(extra="forbid")

    period: PeriodPreset
    custom_start: str | None = None  # ISO-8601 date; required iff period == CUSTOM
    custom_end: str | None = None

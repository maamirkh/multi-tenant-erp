"""Installments report filter/response schemas (spec §18, plan.md Phase 2
§2.6). None of the 7 "Now" reports exposes a ``branch_id`` filter field
(FR-RPT-160/162 correction pass): although ``InstallmentContract`` itself
carries a ``branch_id`` column, none of ``InstallmentReportingService``'s
public methods (the module's own approved source contract) accepts a
``branch_id`` parameter, and Installments is not one of the 3 sanctioned
T047/T075/T087 source-domain bounded-read seams — so no seam exists to
wire it through. FR-RPT-160 permits a branch filter only "where a
report's underlying entity carries a branch_id column" *and the system
can actually apply it as a plain WHERE-clause filter*; FR-RPT-162
requires that a filter that cannot genuinely be honored MUST NOT be
exposed at all, rather than silently accepted and ignored. Every filter
schema below is ``extra="forbid"``, so passing ``branch_id`` from the API
now fails validation (422) instead of being silently dropped. ``status``
is a real, repo-confirmed ``Literal`` (``InstallmentContract``'s own
CHECK constraint) — no ``REJECTED`` value exists anywhere in this model
(FR-RPT-101).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

ContractStatus = Literal[
    "DRAFT",
    "PENDING_APPROVAL",
    "APPROVED",
    "ACTIVE",
    "DEFAULTED",
    "COMPLETED",
    "CANCELLED",
    "WRITTEN_OFF",
]


class ContractRegisterFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ContractStatus | None = None


class CollectionsFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    since: date | None = None
    until: date | None = None


class DueOverdueFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InstallmentAgingFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of_date: date | None = None


class SettlementWriteoffFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanPerformanceFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InstallmentDashboardFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of_date: date | None = None


# ---------------------------------------------------------------------------
# Response row/aggregate shapes.
# ---------------------------------------------------------------------------


class InstallmentReportRow(BaseModel):
    """Generic row shape shared by the 5 list-shaped Installments reports
    — ``InstallmentReportingService``'s per-report dicts already each
    carry a distinct, well-established field set (see its own module
    docstring); this wrapper passes every such field through as-is."""

    model_config = ConfigDict(extra="allow")


class PlanPerformanceResponse(BaseModel):
    rows: list[InstallmentReportRow]
    total: int


class InstallmentDashboardResponse(BaseModel):
    """Mirrors ``InstallmentDashboardData`` (a plain dataclass, not a
    Pydantic model) field-for-field — the 13 metrics are read verbatim,
    never recomputed (FR-INST-080/081)."""

    active_contract_count: int
    outstanding_amount: Decimal
    due_today_amount: Decimal
    due_this_month_amount: Decimal
    collected_today_amount: Decimal
    collected_this_month_amount: Decimal
    overdue_amount: Decimal
    overdue_count: int
    collection_rate: Decimal
    aging_distribution: dict[str, Decimal]
    defaulted_balance: Decimal
    written_off_balance: Decimal
    upcoming_receivables_amount: Decimal

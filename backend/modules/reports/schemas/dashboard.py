"""Executive Dashboard response schemas (spec §13, plan.md §33 Phase 4,
tasks.md T145).

``WidgetState`` is defined exactly once, here, with exactly three values
(§0.2 item 8 of tasks.md's correction pass) — never mutated later:

- ``PRESENT``    — the widget's gates passed and a real (possibly zero)
  value was computed.
- ``OMITTED``    — an entitlement/permission gate failed; the widget key
  simply never appears with an error/reason (FR-RPT-041) — Installments'
  documented exception (FR-RPT-041) still renders under
  ``SERVICING_CONTINUITY``, so ``OMITTED`` there means Case A only.
- ``UNAVAILABLE`` — the wrapped domain service raised the specific, typed
  ``UnavailablePrerequisiteError`` (e.g. Accounting not yet configured) —
  the *only* condition that produces this state (``dashboard_service.py``
  T148).

Exactly **10** widgets, recounted directly from FR-RPT-040's
comma-separated list (§0.2 item 9): Net Sales (+trend), Gross Sales,
Purchase Spend, AR balance + Overdue Receivables, AP balance, Cash
Position, Operational Inventory Value (WAC), CRM Pipeline Value + Win
Rate, Outstanding Installment Principal + Overdue Installments, Recognized
Gross Profit Margin. AR and AP are separate widgets, not combined.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from modules.reports.schemas.common import (
    ComparisonResult,
    DrillDownRef,
    PeriodResolution,
)


class DashboardFilter(BaseModel):
    """Registry-shape placeholder (T032 requires ``supported_filters`` be a
    ``BaseModel`` subclass for every entry, ``COMPOSITE`` included) —
    ``GET /reports/dashboard`` (T150) never routes through the generic
    ``_authorize_and_validate()`` this would otherwise feed; its real
    ``period``/``compare`` query params are parsed directly by the
    dedicated dashboard route."""

    model_config = ConfigDict(extra="forbid")


class WidgetState(StrEnum):
    PRESENT = "present"
    OMITTED = "omitted"
    UNAVAILABLE = "unavailable"


class NetSalesWidget(BaseModel):
    state: WidgetState
    value: Decimal | None = None
    comparison: ComparisonResult | None = None
    drill_down: DrillDownRef | None = None


class GrossSalesWidget(BaseModel):
    state: WidgetState
    value: Decimal | None = None
    comparison: ComparisonResult | None = None
    drill_down: DrillDownRef | None = None


class PurchaseSpendWidget(BaseModel):
    state: WidgetState
    value: Decimal | None = None
    comparison: ComparisonResult | None = None
    drill_down: DrillDownRef | None = None


class ArWidget(BaseModel):
    """Accounts Receivable balance + Overdue Receivables (FR-RPT-040 bundles
    these into one widget — never combined with AP, §0.2 item 9)."""

    state: WidgetState
    balance: Decimal | None = None
    overdue: Decimal | None = None
    comparison: ComparisonResult | None = None
    drill_down: DrillDownRef | None = None


class ApWidget(BaseModel):
    state: WidgetState
    value: Decimal | None = None
    comparison: ComparisonResult | None = None
    drill_down: DrillDownRef | None = None


class CashPositionWidget(BaseModel):
    state: WidgetState
    value: Decimal | None = None
    comparison: ComparisonResult | None = None
    drill_down: DrillDownRef | None = None


class OperationalInventoryValueWidget(BaseModel):
    """FR-RPT-071: always carries an explicit ``valuation_basis`` disclaimer
    — never presented as a reconciled accounting balance (Assumption A11)."""

    state: WidgetState
    value: Decimal | None = None
    valuation_basis: Literal["operational_wac"] | None = None
    comparison: ComparisonResult | None = None
    drill_down: DrillDownRef | None = None


class CrmPipelineWidget(BaseModel):
    """Pipeline Value + Win Rate together, one widget per spec's comma
    grouping (§0.2 item 9)."""

    state: WidgetState
    pipeline_value: Decimal | None = None
    win_rate: Decimal | None = None
    comparison: ComparisonResult | None = None
    drill_down: DrillDownRef | None = None


class InstallmentExposureWidget(BaseModel):
    """Outstanding Principal + Overdue Installments together, one widget.

    The **only** widget with FR-RPT-041's documented three-way branch: a
    disabled Installments module with existing serviceable obligations
    (Case B) still renders here, with ``read_only_servicing_continuity``
    set, sourced only from the allow-listed ``installments.aging``/
    ``installments.due_overdue``-shaped data (plan.md §13 correction) —
    never from the non-allow-listed ``installments.dashboard`` key."""

    state: WidgetState
    outstanding_principal: Decimal | None = None
    overdue: Decimal | None = None
    read_only_servicing_continuity: bool = False
    comparison: ComparisonResult | None = None
    drill_down: DrillDownRef | None = None


class GrossProfitMarginWidget(BaseModel):
    state: WidgetState
    value: Decimal | None = None
    comparison: ComparisonResult | None = None
    drill_down: DrillDownRef | None = None


class ExecutiveDashboardResponse(BaseModel):
    period: PeriodResolution
    net_sales: NetSalesWidget
    gross_sales: GrossSalesWidget
    purchase_spend: PurchaseSpendWidget
    ar: ArWidget
    ap: ApWidget
    cash_position: CashPositionWidget
    operational_inventory_value: OperationalInventoryValueWidget
    crm_pipeline: CrmPipelineWidget
    installment_exposure: InstallmentExposureWidget
    gross_profit_margin: GrossProfitMarginWidget

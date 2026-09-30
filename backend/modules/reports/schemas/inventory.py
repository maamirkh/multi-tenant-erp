"""Inventory report filter/response schemas (spec §16, plan.md Phase 2
§2.4). ``InventoryValuationResponse.valuation_basis`` is a **mandatory**
field (FR-RPT-071) fixed to ``"operational_wac"`` — Inventory's own
weighted-average-cost valuation, injected by ``InventoryAdapter`` (not
Inventory's own service) to make explicit that this is *not* the same
figure as Accounting's GL-derived inventory asset number (spec §16.2 —
see ``test_inventory_valuation_disclaimer.py`` for the exact wording this
module must never contain).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from modules.reports.schemas.common import CurrencyAmount


class InventorySummaryFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warehouse_id: UUID | None = None
    category_id: UUID | None = None


class InventoryValuationFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warehouse_id: UUID | None = None


class StockPositionFilter(BaseModel):
    """Backed by ``ReportQueryService.stock_ledger`` (already a genuine
    Category A bounded-count query, unlike ``stock_position_report``'s
    unbounded full-fetch) — filter surface mirrors ``stock_ledger``'s own
    params, not the never-called ``stock_position_report`` method's."""

    model_config = ConfigDict(extra="forbid")

    product_id: UUID | None = None
    warehouse_id: UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class DeadStockFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold_days: int = 90


class MovementVelocityFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: datetime | None = None
    date_to: datetime | None = None


class StockAgingFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warehouse_id: UUID | None = None


class LowStockFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    alert_type: str | None = None
    product_id: UUID | None = None
    warehouse_id: UUID | None = None


class InventoryKpiFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_days: int = 90


# ---------------------------------------------------------------------------
# Response row/aggregate shapes.
# ---------------------------------------------------------------------------


class InventoryReportRow(BaseModel):
    """Generic row shape shared by the 5 list-shaped Inventory reports
    (``stock_position``, ``dead_stock``, ``movement_velocity``,
    ``stock_aging``, ``low_stock``) — each of ``ReportQueryService``'s
    per-report dicts (and ``LowStockAlertRepository``'s ORM rows) already
    carries a distinct, well-established field set of its own; this
    wrapper passes every such field through as-is rather than declaring
    five near-duplicate row schemas for data this module never recomputes."""

    model_config = ConfigDict(extra="allow")


class InventorySummaryResponse(BaseModel):
    rows: list[InventoryReportRow]
    grand_total_value: Decimal
    as_of: datetime


class InventoryValuationResponse(BaseModel):
    rows: list[InventoryReportRow]
    grand_totals_by_currency: list[CurrencyAmount]
    """Each currency's own total (FR-RPT-152) — never one sum across them."""
    grand_total_value: Decimal | None = None
    """Set only when every position is in one currency; else ``None``."""
    currency_code: str | None = None
    as_of: datetime
    valuation_basis: Literal["operational_wac"]


class InventoryKpiSet(BaseModel):
    """10 existing Inventory KPIs (``KPIService.compute()``) — a
    loosely-typed pass-through wrapper, matching the Purchase/Sales
    catalog's ``*KpiSet`` precedent for heterogeneous KPI dicts."""

    model_config = ConfigDict(extra="allow")

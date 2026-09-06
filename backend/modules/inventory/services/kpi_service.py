"""KPIService — inventory KPI dashboard calculations.

Computes all 10 KPIs defined in the spec:
  1. Inventory Turnover
  2. Average Inventory Value
  3. Inventory Accuracy
  4. Dead Stock %
  5. Stock Accuracy %
  6. Warehouse Efficiency
  7. Total Inventory Value
  8. Reorder Frequency
  9. Stockout Rate
  10. Overstock Rate

Spec ref: specs/005-inventory-management/spec.md §33 (KPI Requirements)
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.inventory.models.alerts import ReorderSuggestion
from modules.inventory.models.stock import StockMovement, StockPosition
from modules.inventory.models.warehouse import Warehouse


def _dec(v: object) -> Decimal:
    if v is None:
        return Decimal("0")
    return Decimal(str(v))


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Return percentage (0–100) rounded to 2dp, safe for zero denominator."""
    if denominator == 0:
        return Decimal("0.00")
    return (numerator / denominator * 100).quantize(Decimal("0.01"))


class KPIService:
    """Computes all 10 inventory KPIs for a given company and lookback period."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def compute(self, *, company_id: UUID, period_days: int = 90) -> dict[str, object]:
        """Return all 10 KPIs as a dict compatible with KPIDashboard schema."""
        now = utcnow()
        period_start = now - timedelta(days=period_days)

        # --- Positions (snapshot of current stock) ---
        positions = (
            self.db.query(StockPosition)
            .filter(
                StockPosition.company_id == company_id,
                StockPosition.deleted_at.is_(None),
            )
            .all()
        )

        total_positions = len(positions)
        total_inventory_value = sum(
            (_dec(p.qty_on_hand) * _dec(p.unit_cost) for p in positions),
            Decimal("0"),
        )

        # KPI 7 — Total Inventory Value
        kpi_total_inventory_value = total_inventory_value

        # KPI 2 — Average Inventory Value (average of start and end period values)
        # Approximation: use the current snapshot as the end value and compute
        # a start value using net movement cost during the period.
        # Simplified: (total_inventory_value) / 1 (single-point estimate)
        kpi_average_inventory = total_inventory_value

        # KPI 1 — Inventory Turnover = COGS / Average Inventory
        # COGS proxy: sum of OUT movement costs during the period
        cogs_q = (
            self.db.query(
                func.sum(
                    StockMovement.quantity * func.coalesce(StockMovement.unit_cost, 0)
                )
            )
            .filter(
                StockMovement.company_id == company_id,
                StockMovement.direction == "OUT",
                StockMovement.movement_type.in_(
                    [
                        "SALES_ISSUE",
                        "ADJUSTMENT_OUT",
                        "TRANSFER_OUT",
                        "DAMAGE",
                        "WRITE_OFF",
                    ]
                ),
                StockMovement.performed_at >= period_start,
            )
            .scalar()
        )
        cogs = _dec(cogs_q)
        kpi_inventory_turnover = (
            (cogs / kpi_average_inventory).quantize(Decimal("0.01"))
            if kpi_average_inventory > 0
            else Decimal("0.00")
        )

        # KPI 3 — Inventory Accuracy (proxy: % positions that have a non-null unit_cost)
        positions_with_cost = sum(1 for p in positions if p.unit_cost is not None)
        kpi_inventory_accuracy = _pct(
            Decimal(str(positions_with_cost)), Decimal(str(total_positions))
        )

        # KPI 4 — Dead Stock % (positions with no movement in period, by value / total value)
        active_products = set(
            row[0]
            for row in self.db.query(StockMovement.product_id)
            .filter(
                StockMovement.company_id == company_id,
                StockMovement.performed_at >= period_start,
            )
            .distinct()
            .all()
        )
        dead_value = sum(
            (
                _dec(p.qty_on_hand) * _dec(p.unit_cost)
                for p in positions
                if p.product_id not in active_products and _dec(p.qty_on_hand) > 0
            ),
            Decimal("0"),
        )
        kpi_dead_stock_pct = _pct(dead_value, total_inventory_value)

        # KPI 5 — Stock Accuracy % (% of positions with qty_on_hand > 0)
        positions_with_stock = sum(1 for p in positions if _dec(p.qty_on_hand) > 0)
        kpi_stock_accuracy_pct = _pct(
            Decimal(str(positions_with_stock)), Decimal(str(total_positions))
        )

        # KPI 6 — Warehouse Efficiency (% of warehouses that are ACTIVE)
        warehouses = (
            self.db.query(Warehouse)
            .filter(
                Warehouse.company_id == company_id,
                Warehouse.deleted_at.is_(None),
            )
            .all()
        )
        total_warehouses = len(warehouses)
        active_warehouses = sum(
            1 for w in warehouses if getattr(w, "status", "ACTIVE") == "ACTIVE"
        )
        kpi_warehouse_efficiency = _pct(
            Decimal(str(active_warehouses)), Decimal(str(total_warehouses))
        )

        # KPI 8 — Reorder Frequency (# reorder suggestions in period)
        kpi_reorder_frequency = Decimal(
            str(
                self.db.query(func.count(ReorderSuggestion.id))
                .filter(
                    ReorderSuggestion.company_id == company_id,
                    ReorderSuggestion.created_at >= period_start,
                )
                .scalar()
                or 0
            )
        )

        # KPI 9 — Stockout Rate (% of products with any position at qty_on_hand == 0)
        zero_stock = sum(1 for p in positions if _dec(p.qty_on_hand) == 0)
        kpi_stockout_rate = _pct(
            Decimal(str(zero_stock)), Decimal(str(total_positions))
        )

        # KPI 10 — Overstock Rate (% of positions exceeding maximum_stock)
        positions_with_max = [p for p in positions if p.maximum_stock is not None]
        overstock = sum(
            1 for p in positions_with_max if _dec(p.qty_on_hand) > _dec(p.maximum_stock)
        )
        kpi_overstock_rate = _pct(
            Decimal(str(overstock)),
            (
                Decimal(str(len(positions_with_max)))
                if positions_with_max
                else Decimal("0")
            ),
        )

        return {
            "inventory_turnover": kpi_inventory_turnover,
            "average_inventory_value": kpi_average_inventory.quantize(Decimal("0.01")),
            "inventory_accuracy": kpi_inventory_accuracy,
            "dead_stock_percentage": kpi_dead_stock_pct,
            "stock_accuracy_percentage": kpi_stock_accuracy_pct,
            "warehouse_efficiency": kpi_warehouse_efficiency,
            "total_inventory_value": kpi_total_inventory_value.quantize(
                Decimal("0.01")
            ),
            "reorder_frequency": kpi_reorder_frequency,
            "stockout_rate": kpi_stockout_rate,
            "overstock_rate": kpi_overstock_rate,
            "as_of": now,
            "period_days": period_days,
        }

"""ReportQueryService — read-only inventory report queries.

Implements all 14 inventory reports defined in the spec.

Design constraints:
  - All methods are read-only: no domain mutations.
  - Every query is scoped by company_id for tenant isolation.
  - SQLAlchemy ORM queries use text() / func to stay compatible with
    SQLite (tests) and PostgreSQL (production).
  - Returns plain dataclass/dict rows; conversion to Pydantic schemas
    happens in the router layer.

Spec ref: specs/005-inventory-management/spec.md §32 (Reporting Requirements)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.utils.datetime import ensure_utc, utcnow
from modules.inventory.models.adjustment import InventoryAdjustment
from modules.inventory.models.brand import Brand
from modules.inventory.models.category import Category
from modules.inventory.models.product import Product
from modules.inventory.models.stock import StockMovement, StockPosition
from modules.inventory.models.transfer import StockTransfer, StockTransferLine
from modules.inventory.models.warehouse import Warehouse

logger = logging.getLogger(__name__)


def _dec(value: Any) -> Decimal:
    """Coerce to Decimal, defaulting to 0 for None."""
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


class ReportQueryService:
    """Read-only query service for all 14 inventory reports.

    All methods:
      1. Accept ``company_id`` as the first filter (tenant isolation).
      2. Return plain Python dicts or lists of dicts (caller converts).
      3. Never write to the database.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # =========================================================================
    # Report 1 — Inventory Summary
    # =========================================================================

    def inventory_summary(
        self,
        *,
        company_id: UUID,
        warehouse_id: UUID | None = None,
        category_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Total stock value by warehouse, category, brand with WAC valuation."""
        q = (
            self.db.query(
                StockPosition,
                Product,
                Warehouse,
                Category,
                Brand,
            )
            .join(Product, Product.id == StockPosition.product_id)
            .join(Warehouse, Warehouse.id == StockPosition.warehouse_id)
            .outerjoin(Category, Category.id == Product.category_id)
            .outerjoin(Brand, Brand.id == Product.brand_id)
            .filter(
                StockPosition.company_id == company_id,
                StockPosition.deleted_at.is_(None),
            )
        )
        if warehouse_id:
            q = q.filter(StockPosition.warehouse_id == str(warehouse_id))
        if category_id:
            q = q.filter(Product.category_id == str(category_id))

        rows = []
        grand_total = Decimal("0")
        for pos, prod, wh, cat, brand in q.all():
            qty = _dec(pos.qty_on_hand)
            cost = _dec(pos.unit_cost)
            total_value = qty * cost
            grand_total += total_value
            rows.append(
                {
                    "product_id": str(prod.id),
                    "product_code": prod.product_code,
                    "product_name": prod.name,
                    "category_name": cat.name if cat else None,
                    "brand_name": brand.name if brand else None,
                    "warehouse_id": str(wh.id),
                    "warehouse_name": wh.name,
                    "qty_on_hand": qty,
                    "unit_cost": cost if pos.unit_cost else None,
                    "total_value": total_value,
                    "currency_code": pos.currency_code,
                }
            )
        return {"rows": rows, "grand_total_value": grand_total, "as_of": utcnow()}

    # =========================================================================
    # Report 2 — Stock Ledger
    # =========================================================================

    def stock_ledger(
        self,
        *,
        company_id: UUID,
        product_id: UUID | None = None,
        warehouse_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> dict[str, Any]:
        """All movements for product × warehouse × date range."""
        q = (
            self.db.query(StockMovement, Product, Warehouse)
            .join(Product, Product.id == StockMovement.product_id)
            .join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
            .filter(StockMovement.company_id == company_id)
        )
        if product_id:
            q = q.filter(StockMovement.product_id == str(product_id))
        if warehouse_id:
            q = q.filter(StockMovement.warehouse_id == str(warehouse_id))
        if date_from:
            q = q.filter(StockMovement.performed_at >= date_from)
        if date_to:
            q = q.filter(StockMovement.performed_at <= date_to)

        total_rows = q.count()
        rows_raw = (
            q.order_by(StockMovement.performed_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        rows = []
        for mov, prod, wh in rows_raw:
            qty = _dec(mov.quantity)
            cost = _dec(mov.unit_cost)
            rows.append(
                {
                    "movement_id": str(mov.id),
                    "product_id": str(prod.id),
                    "product_code": prod.product_code,
                    "product_name": prod.name,
                    "warehouse_id": str(wh.id),
                    "warehouse_name": wh.name,
                    "movement_type": mov.movement_type,
                    "direction": mov.direction,
                    "quantity": qty,
                    "unit_cost": _dec(mov.unit_cost) if mov.unit_cost else None,
                    "total_value": qty * cost if mov.unit_cost else None,
                    "reference_type": mov.reference_type,
                    "reference_id": mov.reference_id,
                    "performed_at": mov.performed_at,
                    "notes": getattr(mov, "notes", None),
                }
            )
        return {"rows": rows, "total_rows": total_rows}

    # =========================================================================
    # Report 3 — Inventory Valuation
    # =========================================================================

    def inventory_valuation(
        self,
        *,
        company_id: UUID,
        warehouse_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Per-product WAC value, total portfolio value."""
        q = (
            self.db.query(
                StockPosition.product_id,
                Product.product_code,
                Product.name.label("product_name"),
                func.sum(StockPosition.qty_on_hand).label("total_qty"),
                func.avg(StockPosition.unit_cost).label("unit_cost"),
                func.sum(
                    StockPosition.qty_on_hand
                    * func.coalesce(StockPosition.unit_cost, 0)
                ).label("total_value"),
                StockPosition.currency_code,
            )
            .join(Product, Product.id == StockPosition.product_id)
            .filter(
                StockPosition.company_id == company_id,
                StockPosition.deleted_at.is_(None),
            )
            .group_by(
                StockPosition.product_id,
                Product.product_code,
                Product.name,
                StockPosition.currency_code,
            )
        )
        if warehouse_id:
            q = q.filter(StockPosition.warehouse_id == str(warehouse_id))

        rows = []
        grand_total = Decimal("0")
        currency = None
        for row in q.all():
            total_value = _dec(row.total_value)
            grand_total += total_value
            if row.currency_code:
                currency = row.currency_code
            rows.append(
                {
                    "product_id": row.product_id,
                    "product_code": row.product_code,
                    "product_name": row.product_name,
                    "total_qty": _dec(row.total_qty),
                    "unit_cost": _dec(row.unit_cost) if row.unit_cost else None,
                    "total_value": total_value,
                    "currency_code": row.currency_code,
                    "valuation_method": "WAC",
                }
            )
        return {
            "rows": rows,
            "grand_total_value": grand_total,
            "currency_code": currency,
            "as_of": utcnow(),
        }

    # =========================================================================
    # Report 4 — Stock Position
    # =========================================================================

    def stock_position_report(
        self,
        *,
        company_id: UUID,
        warehouse_id: UUID | None = None,
        below_reorder_only: bool = False,
    ) -> dict[str, Any]:
        """Current/reserved/damaged/available per product × warehouse."""
        q = (
            self.db.query(StockPosition, Product, Warehouse)
            .join(Product, Product.id == StockPosition.product_id)
            .join(Warehouse, Warehouse.id == StockPosition.warehouse_id)
            .filter(
                StockPosition.company_id == company_id,
                StockPosition.deleted_at.is_(None),
            )
        )
        if warehouse_id:
            q = q.filter(StockPosition.warehouse_id == str(warehouse_id))

        rows = []
        for pos, prod, wh in q.all():
            qty_on_hand = _dec(pos.qty_on_hand)
            qty_reserved = _dec(pos.qty_reserved)
            qty_damaged = _dec(pos.qty_damaged)
            qty_available = qty_on_hand - qty_reserved - qty_damaged
            reorder_level = _dec(pos.reorder_level)
            safety_stock = _dec(pos.safety_stock)

            is_below_reorder = qty_on_hand <= reorder_level and reorder_level > 0
            is_below_safety = qty_on_hand < safety_stock and safety_stock > 0
            is_out_of_stock = qty_on_hand == 0

            if below_reorder_only and not is_below_reorder:
                continue

            rows.append(
                {
                    "product_id": str(prod.id),
                    "product_code": prod.product_code,
                    "product_name": prod.name,
                    "warehouse_id": str(wh.id),
                    "warehouse_name": wh.name,
                    "qty_on_hand": qty_on_hand,
                    "qty_reserved": qty_reserved,
                    "qty_damaged": qty_damaged,
                    "qty_available": max(qty_available, Decimal("0")),
                    "reorder_level": reorder_level,
                    "safety_stock": safety_stock,
                    "is_below_reorder": is_below_reorder,
                    "is_below_safety": is_below_safety,
                    "is_out_of_stock": is_out_of_stock,
                }
            )
        return {"rows": rows, "total_rows": len(rows)}

    # =========================================================================
    # Report 5 — Warehouse Utilisation
    # =========================================================================

    def warehouse_utilisation(self, *, company_id: UUID) -> dict[str, Any]:
        """Stock count and value by warehouse."""
        warehouses = (
            self.db.query(Warehouse)
            .filter(
                Warehouse.company_id == company_id,
                Warehouse.deleted_at.is_(None),
            )
            .all()
        )

        rows = []
        for wh in warehouses:
            positions = (
                self.db.query(StockPosition)
                .filter(
                    StockPosition.company_id == company_id,
                    StockPosition.warehouse_id == str(wh.id),
                    StockPosition.deleted_at.is_(None),
                )
                .all()
            )
            total_qty = sum(_dec(p.qty_on_hand) for p in positions)
            total_value = sum(
                _dec(p.qty_on_hand) * _dec(p.unit_cost) for p in positions
            )
            # Location counts from warehouse locations
            from modules.inventory.models.warehouse import WarehouseLocation

            locs = (
                self.db.query(WarehouseLocation)
                .filter(
                    WarehouseLocation.warehouse_id == str(wh.id),
                    WarehouseLocation.deleted_at.is_(None),
                )
                .all()
            )
            active_locs = len(
                [loc for loc in locs if getattr(loc, "status", "ACTIVE") == "ACTIVE"]
            )
            used_locs = len(
                set(
                    getattr(p, "location_id", None)
                    for p in positions
                    if getattr(p, "location_id", None)
                )
            )
            rows.append(
                {
                    "warehouse_id": str(wh.id),
                    "warehouse_name": wh.name,
                    "warehouse_code": wh.code,
                    "total_products": len(positions),
                    "total_qty_on_hand": total_qty,
                    "total_value": total_value,
                    "active_locations": active_locs,
                    "used_locations": used_locs,
                }
            )
        return {"rows": rows}

    # =========================================================================
    # Reports 6 & 7 — Category & Brand Performance
    # =========================================================================

    def category_brand_report(
        self,
        *,
        company_id: UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        """Stock value and movement count by category and brand."""
        # Category aggregation
        cat_q = (
            self.db.query(
                Category.id.label("category_id"),
                Category.name.label("category_name"),
                func.count(func.distinct(Product.id)).label("total_products"),
                func.sum(StockPosition.qty_on_hand).label("total_qty"),
                func.sum(
                    StockPosition.qty_on_hand
                    * func.coalesce(StockPosition.unit_cost, 0)
                ).label("total_value"),
            )
            .join(Product, Product.category_id == Category.id)
            .outerjoin(
                StockPosition,
                (StockPosition.product_id == Product.id)
                & (StockPosition.company_id == company_id)
                & (StockPosition.deleted_at.is_(None)),
            )
            .filter(Category.company_id == company_id, Category.deleted_at.is_(None))
            .group_by(Category.id, Category.name)
        )

        # Movement count per category for the period
        mov_cat: dict[str, int] = {}
        mv_q = (
            self.db.query(
                Product.category_id.label("category_id"),
                func.count(StockMovement.id).label("cnt"),
            )
            .join(StockMovement, StockMovement.product_id == Product.id)
            .filter(StockMovement.company_id == company_id)
        )
        if date_from:
            mv_q = mv_q.filter(StockMovement.performed_at >= date_from)
        if date_to:
            mv_q = mv_q.filter(StockMovement.performed_at <= date_to)
        mv_q = mv_q.group_by(Product.category_id)
        for mv_row in mv_q.all():
            if mv_row.category_id:
                mov_cat[mv_row.category_id] = int(mv_row.cnt)

        categories = []
        for row in cat_q.all():
            categories.append(
                {
                    "category_id": str(row.category_id),
                    "category_name": row.category_name,
                    "total_products": int(row.total_products or 0),
                    "total_qty_on_hand": _dec(row.total_qty),
                    "total_value": _dec(row.total_value),
                    "total_movements": mov_cat.get(str(row.category_id), 0),
                }
            )

        # Brand aggregation
        brand_q = (
            self.db.query(
                Brand.id.label("brand_id"),
                Brand.name.label("brand_name"),
                func.count(func.distinct(Product.id)).label("total_products"),
                func.sum(StockPosition.qty_on_hand).label("total_qty"),
                func.sum(
                    StockPosition.qty_on_hand
                    * func.coalesce(StockPosition.unit_cost, 0)
                ).label("total_value"),
            )
            .join(Product, Product.brand_id == Brand.id)
            .outerjoin(
                StockPosition,
                (StockPosition.product_id == Product.id)
                & (StockPosition.company_id == company_id)
                & (StockPosition.deleted_at.is_(None)),
            )
            .filter(Brand.company_id == company_id, Brand.deleted_at.is_(None))
            .group_by(Brand.id, Brand.name)
        )

        mov_brand: dict[str, int] = {}
        mv_bq = (
            self.db.query(
                Product.brand_id.label("brand_id"),
                func.count(StockMovement.id).label("cnt"),
            )
            .join(StockMovement, StockMovement.product_id == Product.id)
            .filter(StockMovement.company_id == company_id)
        )
        if date_from:
            mv_bq = mv_bq.filter(StockMovement.performed_at >= date_from)
        if date_to:
            mv_bq = mv_bq.filter(StockMovement.performed_at <= date_to)
        mv_bq = mv_bq.group_by(Product.brand_id)
        for mv_row in mv_bq.all():
            if mv_row.brand_id:
                mov_brand[mv_row.brand_id] = int(mv_row.cnt)

        brands = []
        for row in brand_q.all():
            brands.append(
                {
                    "brand_id": str(row.brand_id),
                    "brand_name": row.brand_name,
                    "total_products": int(row.total_products or 0),
                    "total_qty_on_hand": _dec(row.total_qty),
                    "total_value": _dec(row.total_value),
                    "total_movements": mov_brand.get(str(row.brand_id), 0),
                }
            )

        return {"categories": categories, "brands": brands}

    # =========================================================================
    # Report 8 — Dead Stock
    # =========================================================================

    def dead_stock(
        self,
        *,
        company_id: UUID,
        threshold_days: int = 90,
    ) -> dict[str, Any]:
        """Products with zero movement in last N days."""
        cutoff = utcnow() - timedelta(days=threshold_days)

        # Products that have had a movement after the cutoff
        active_products = set(
            row[0]
            for row in self.db.query(StockMovement.product_id)
            .filter(
                StockMovement.company_id == company_id,
                StockMovement.performed_at >= cutoff,
            )
            .distinct()
            .all()
        )

        # Last movement per product (for display)
        last_mov: dict[str, datetime | None] = {}
        for row in (
            self.db.query(
                StockMovement.product_id,
                func.max(StockMovement.performed_at).label("last_at"),
            )
            .filter(StockMovement.company_id == company_id)
            .group_by(StockMovement.product_id)
            .all()
        ):
            last_mov[row.product_id] = row.last_at

        positions = (
            self.db.query(StockPosition, Product, Warehouse)
            .join(Product, Product.id == StockPosition.product_id)
            .join(Warehouse, Warehouse.id == StockPosition.warehouse_id)
            .filter(
                StockPosition.company_id == company_id,
                StockPosition.qty_on_hand > 0,
                StockPosition.deleted_at.is_(None),
            )
            .all()
        )

        rows = []
        total_dead_value = Decimal("0")
        now = utcnow()
        for pos, prod, wh in positions:
            if pos.product_id in active_products:
                continue
            last_at = last_mov.get(pos.product_id)
            days = (now - ensure_utc(last_at)).days if last_at else threshold_days
            qty = _dec(pos.qty_on_hand)
            value = qty * _dec(pos.unit_cost)
            total_dead_value += value
            rows.append(
                {
                    "product_id": str(prod.id),
                    "product_code": prod.product_code,
                    "product_name": prod.name,
                    "warehouse_id": str(wh.id),
                    "warehouse_name": wh.name,
                    "qty_on_hand": qty,
                    "total_value": value,
                    "last_movement_at": last_at,
                    "days_without_movement": days,
                }
            )

        rows.sort(key=lambda r: r["days_without_movement"], reverse=True)
        return {
            "rows": rows,
            "threshold_days": threshold_days,
            "total_dead_stock_value": total_dead_value,
        }

    # =========================================================================
    # Reports 9 & 10 — Movement Velocity
    # =========================================================================

    def movement_velocity(
        self,
        *,
        company_id: UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        top_n: int = 20,
    ) -> dict[str, Any]:
        """Fast and slow moving products by movement count over period."""
        if date_from is None:
            date_from = utcnow() - timedelta(days=90)
        if date_to is None:
            date_to = utcnow()

        period_days = max((date_to - date_from).days, 1)

        q = (
            self.db.query(
                StockMovement.product_id,
                Product.product_code,
                Product.name.label("product_name"),
                func.count(StockMovement.id).label("total_movements"),
                func.sum(StockMovement.quantity).label("total_qty"),
                func.min(StockMovement.performed_at).label("first_at"),
                func.max(StockMovement.performed_at).label("last_at"),
            )
            .join(Product, Product.id == StockMovement.product_id)
            .filter(
                StockMovement.company_id == company_id,
                StockMovement.performed_at >= date_from,
                StockMovement.performed_at <= date_to,
                StockMovement.movement_type != "SNAPSHOT",
            )
            .group_by(StockMovement.product_id, Product.product_code, Product.name)
        )

        all_rows = []
        for row in q.all():
            total_qty = _dec(row.total_qty)
            total_mov = int(row.total_movements or 0)
            all_rows.append(
                {
                    "product_id": row.product_id,
                    "product_code": row.product_code,
                    "product_name": row.product_name,
                    "total_movements": total_mov,
                    "total_quantity_moved": total_qty,
                    "avg_daily_movement": (
                        total_qty / Decimal(str(period_days))
                        if period_days
                        else Decimal("0")
                    ),
                    "first_movement_at": row.first_at,
                    "last_movement_at": row.last_at,
                }
            )

        all_rows.sort(key=lambda r: r["total_movements"], reverse=True)
        fast = all_rows[:top_n]
        slow = all_rows[-top_n:] if len(all_rows) > top_n else []
        slow = list(reversed(slow))

        return {"fast_moving": fast, "slow_moving": slow, "period_days": period_days}

    # =========================================================================
    # Report 11 — Stock Aging
    # =========================================================================

    def stock_aging(
        self,
        *,
        company_id: UUID,
        warehouse_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Age of current stock by first-receipt date."""
        # First receipt date per product × warehouse
        first_receipt: dict[tuple[str, str], datetime | None] = {}
        q = (
            self.db.query(
                StockMovement.product_id,
                StockMovement.warehouse_id,
                func.min(StockMovement.performed_at).label("first_at"),
            )
            .filter(
                StockMovement.company_id == company_id,
                StockMovement.direction == "IN",
                StockMovement.movement_type != "SNAPSHOT",
            )
            .group_by(StockMovement.product_id, StockMovement.warehouse_id)
        )
        if warehouse_id:
            q = q.filter(StockMovement.warehouse_id == str(warehouse_id))
        for row in q.all():
            first_receipt[(row.product_id, row.warehouse_id)] = row.first_at

        pos_q = (
            self.db.query(StockPosition, Product, Warehouse)
            .join(Product, Product.id == StockPosition.product_id)
            .join(Warehouse, Warehouse.id == StockPosition.warehouse_id)
            .filter(
                StockPosition.company_id == company_id,
                StockPosition.qty_on_hand > 0,
                StockPosition.deleted_at.is_(None),
            )
        )
        if warehouse_id:
            pos_q = pos_q.filter(StockPosition.warehouse_id == str(warehouse_id))

        now = utcnow()
        rows = []
        for pos, prod, wh in pos_q.all():
            first_at = first_receipt.get((pos.product_id, pos.warehouse_id))
            age_days: int | None = None
            bucket = "Unknown"
            if first_at:
                age_days = (now - ensure_utc(first_at)).days
                if age_days <= 30:
                    bucket = "0-30"
                elif age_days <= 60:
                    bucket = "31-60"
                elif age_days <= 90:
                    bucket = "61-90"
                else:
                    bucket = "90+"

            rows.append(
                {
                    "product_id": str(prod.id),
                    "product_code": prod.product_code,
                    "product_name": prod.name,
                    "warehouse_id": str(wh.id),
                    "warehouse_name": wh.name,
                    "qty_on_hand": _dec(pos.qty_on_hand),
                    "first_receipt_at": first_at,
                    "age_days": age_days,
                    "bucket": bucket,
                }
            )

        rows.sort(key=lambda r: r["age_days"] or 0, reverse=True)
        return {"rows": rows, "as_of": now}

    # =========================================================================
    # Reports 12 & 13 — Operational (Adjustment + Transfer)
    # =========================================================================

    def operational_report(
        self,
        *,
        company_id: UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        warehouse_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Audit history of adjustments and transfers."""
        # Adjustments
        adj_q = (
            self.db.query(InventoryAdjustment, Product, Warehouse)
            .join(Product, Product.id == InventoryAdjustment.product_id)
            .join(Warehouse, Warehouse.id == InventoryAdjustment.warehouse_id)
            .filter(InventoryAdjustment.company_id == company_id)
        )
        if date_from:
            adj_q = adj_q.filter(InventoryAdjustment.created_at >= date_from)
        if date_to:
            adj_q = adj_q.filter(InventoryAdjustment.created_at <= date_to)
        if warehouse_id:
            adj_q = adj_q.filter(InventoryAdjustment.warehouse_id == str(warehouse_id))

        adjustments = []
        for adj, prod, wh in adj_q.order_by(
            InventoryAdjustment.created_at.desc()
        ).all():
            adjustments.append(
                {
                    "adjustment_id": str(adj.id),
                    "product_id": str(prod.id),
                    "product_code": prod.product_code,
                    "product_name": prod.name,
                    "warehouse_id": str(wh.id),
                    "warehouse_name": wh.name,
                    "movement_type": adj.movement_type,
                    "quantity": _dec(adj.quantity),
                    "unit_cost": _dec(adj.unit_cost) if adj.unit_cost else None,
                    "status": adj.status,
                    "created_at": adj.created_at,
                    "notes": adj.notes,
                }
            )

        # Transfers
        tr_q = self.db.query(StockTransfer).filter(
            StockTransfer.company_id == company_id
        )
        if date_from:
            tr_q = tr_q.filter(StockTransfer.created_at >= date_from)
        if date_to:
            tr_q = tr_q.filter(StockTransfer.created_at <= date_to)
        if warehouse_id:
            tr_q = tr_q.filter(
                (StockTransfer.source_warehouse_id == str(warehouse_id))
                | (StockTransfer.destination_warehouse_id == str(warehouse_id))
            )

        wh_cache: dict[str, Warehouse] = {}

        def _get_wh(wid: str) -> Warehouse | None:
            if wid not in wh_cache:
                wh = self.db.query(Warehouse).filter(Warehouse.id == wid).first()
                wh_cache[wid] = wh  # type: ignore[assignment]
            return wh_cache[wid]

        transfers = []
        for tr in tr_q.order_by(StockTransfer.created_at.desc()).all():
            src_wh = _get_wh(tr.source_warehouse_id)
            dst_wh = _get_wh(tr.destination_warehouse_id)
            line_count = (
                self.db.query(func.count(StockTransferLine.id))
                .filter(StockTransferLine.transfer_id == tr.id)
                .scalar()
                or 0
            )
            transfers.append(
                {
                    "transfer_id": str(tr.id),
                    "reference_no": tr.reference_no,
                    "source_warehouse_id": tr.source_warehouse_id,
                    "source_warehouse_name": src_wh.name if src_wh else "Unknown",
                    "destination_warehouse_id": tr.destination_warehouse_id,
                    "destination_warehouse_name": dst_wh.name if dst_wh else "Unknown",
                    "status": tr.status,
                    "total_lines": int(line_count),
                    "created_at": tr.created_at,
                    "dispatched_at": tr.dispatched_at,
                    "received_at": tr.received_at,
                }
            )

        return {"adjustments": adjustments, "transfers": transfers}

    # =========================================================================
    # Report 14 — Inventory Trend Analysis
    # =========================================================================

    def trend_analysis(
        self,
        *,
        company_id: UUID,
        product_id: UUID,
        warehouse_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        """Stock level over time for selected product × warehouse."""
        if date_from is None:
            date_from = utcnow() - timedelta(days=90)
        if date_to is None:
            date_to = utcnow()

        prod = (
            self.db.query(Product)
            .filter(Product.id == product_id, Product.company_id == company_id)
            .first()
        )
        wh: Warehouse | None = None
        if warehouse_id:
            wh = self.db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()

        mov_q = (
            self.db.query(
                StockMovement.performed_at,
                StockMovement.direction,
                StockMovement.quantity,
            )
            .filter(
                StockMovement.company_id == company_id,
                StockMovement.product_id == str(product_id),
                StockMovement.performed_at >= date_from,
                StockMovement.performed_at <= date_to,
                StockMovement.movement_type != "SNAPSHOT",
            )
            .order_by(StockMovement.performed_at)
        )
        if warehouse_id:
            mov_q = mov_q.filter(StockMovement.warehouse_id == str(warehouse_id))

        # Bucket by date (daily)
        daily: dict[str, dict[str, Decimal]] = {}
        for performed_at, direction, quantity in mov_q.all():
            if performed_at is None:
                continue
            date_key = performed_at.strftime("%Y-%m-%d")
            if date_key not in daily:
                daily[date_key] = {"in": Decimal("0"), "out": Decimal("0")}
            qty = _dec(quantity)
            if direction == "IN":
                daily[date_key]["in"] += qty
            else:
                daily[date_key]["out"] += qty

        # Build running total from the first receipt date
        data_points = []
        running_qty = Decimal("0")
        for date_key in sorted(daily.keys()):
            d_in = daily[date_key]["in"]
            d_out = daily[date_key]["out"]
            running_qty += d_in - d_out
            data_points.append(
                {
                    "date": datetime.fromisoformat(date_key),
                    "qty_on_hand": running_qty,
                    "total_in": d_in,
                    "total_out": d_out,
                    "net_change": d_in - d_out,
                }
            )

        return {
            "product_id": str(product_id),
            "product_code": prod.product_code if prod else "",
            "product_name": prod.name if prod else "",
            "warehouse_id": str(warehouse_id) if warehouse_id else None,
            "warehouse_name": wh.name if wh else None,
            "data_points": data_points,
            "period_start": date_from,
            "period_end": date_to,
        }

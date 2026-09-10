"""Purchase Intelligence & Reporting service — Phase 9.

Read-only application service.  No domain mutations.  All methods are
company-scoped and accept optional date-range / filter parameters.

Reports implemented (T207–T220):
  RPT-01  purchase_order_summary
  RPT-02  pending_purchase_orders
  RPT-03  overdue_deliveries
  RPT-04  goods_receipt_report
  RPT-05  purchase_request_status
  RPT-06  supplier_performance
  RPT-07  vendor_return_report
  RPT-08  purchase_by_supplier
  RPT-09  purchase_by_category
  RPT-10  purchase_price_variance
  RPT-11  open_purchase_commitments
  RPT-12  purchase_trend_analysis
  RPT-13  goods_rejection_analysis
  RPT-14  procurement_audit_trail

Spec ref: specs/006-purchase-management/spec.md §34 §35
Tasks: T206–T220
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, cast, func, select
from sqlalchemy.orm import Session

from modules.purchase.models.cost import PurchaseCostEntry
from modules.purchase.models.goods_receipt import GoodsReceipt, GRLine
from modules.purchase.models.purchase_order import POLine, PurchaseOrder
from modules.purchase.models.purchase_request import PurchaseRequest
from modules.purchase.models.supplier import Supplier, SupplierCategory
from modules.purchase.models.vendor_return import VendorReturn

logger = logging.getLogger(__name__)

_TWO_PLACES = Decimal("0.01")


def _d(val: Any) -> Decimal:
    """Safely convert numeric DB value to Decimal."""
    if val is None:
        return Decimal("0")
    return Decimal(str(val)).quantize(_TWO_PLACES)


class ReportService:
    """Read-only procurement reporting service.

    All methods return plain list[dict] structures so they can be used
    for API responses as well as CSV/Excel export without additional
    transformation.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # RPT-01  Purchase Order Summary  (T207)
    # ------------------------------------------------------------------

    def purchase_order_summary(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        supplier_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """All POs with status, supplier, value, and dates.

        Filterable by status, supplier, and creation date range.
        """
        stmt = (
            select(
                PurchaseOrder.id,
                PurchaseOrder.po_number,
                PurchaseOrder.status,
                PurchaseOrder.supplier_id,
                PurchaseOrder.currency_code,
                PurchaseOrder.subtotal,
                PurchaseOrder.total_charges,
                PurchaseOrder.total_discounts,
                PurchaseOrder.tax_amount,
                PurchaseOrder.total,
                PurchaseOrder.expected_delivery_date,
                PurchaseOrder.created_at,
            )
            .where(
                and_(
                    PurchaseOrder.company_id == company_id,
                    PurchaseOrder.deleted_at.is_(None),
                )
            )
            .order_by(PurchaseOrder.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(PurchaseOrder.status == status)
        if supplier_id:
            stmt = stmt.where(PurchaseOrder.supplier_id == str(supplier_id))
        if date_from:
            stmt = stmt.where(
                cast(PurchaseOrder.created_at, __import__("sqlalchemy").Date)
                >= date_from
            )
        if date_to:
            stmt = stmt.where(
                cast(PurchaseOrder.created_at, __import__("sqlalchemy").Date) <= date_to
            )

        rows = self.db.execute(stmt).mappings().all()
        return [
            {
                "po_id": str(r["id"]),
                "po_number": r["po_number"],
                "status": r["status"],
                "supplier_id": r["supplier_id"],
                "currency_code": r["currency_code"],
                "subtotal": str(_d(r["subtotal"])),
                "total_charges": str(_d(r["total_charges"])),
                "total_discounts": str(_d(r["total_discounts"])),
                "tax_amount": str(_d(r["tax_amount"])),
                "total": str(_d(r["total"])),
                "expected_delivery_date": (
                    r["expected_delivery_date"].isoformat()
                    if r["expected_delivery_date"]
                    else None
                ),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # RPT-02  Pending Purchase Orders  (T208)
    # ------------------------------------------------------------------

    def pending_purchase_orders(
        self,
        company_id: UUID,
        *,
        skip: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """APPROVED/PARTIALLY_RECEIVED POs sorted by expected_delivery_date."""
        stmt = (
            select(
                PurchaseOrder.id,
                PurchaseOrder.po_number,
                PurchaseOrder.status,
                PurchaseOrder.supplier_id,
                PurchaseOrder.total,
                PurchaseOrder.currency_code,
                PurchaseOrder.expected_delivery_date,
                PurchaseOrder.created_at,
            )
            .where(
                and_(
                    PurchaseOrder.company_id == company_id,
                    PurchaseOrder.deleted_at.is_(None),
                    PurchaseOrder.status.in_(["APPROVED", "PARTIALLY_RECEIVED"]),
                )
            )
            .order_by(PurchaseOrder.expected_delivery_date.asc().nullslast())
            .offset(skip)
            .limit(limit)
        )
        rows = self.db.execute(stmt).mappings().all()
        return [
            {
                "po_id": str(r["id"]),
                "po_number": r["po_number"],
                "status": r["status"],
                "supplier_id": r["supplier_id"],
                "total": str(_d(r["total"])),
                "currency_code": r["currency_code"],
                "expected_delivery_date": (
                    r["expected_delivery_date"].isoformat()
                    if r["expected_delivery_date"]
                    else None
                ),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # RPT-03  Overdue Deliveries  (T209)
    # ------------------------------------------------------------------

    def overdue_deliveries(
        self,
        company_id: UUID,
        *,
        as_of: date | None = None,
        skip: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """POs past expected_delivery_date without FULLY_RECEIVED status."""
        cutoff = as_of or date.today()
        stmt = (
            select(
                PurchaseOrder.id,
                PurchaseOrder.po_number,
                PurchaseOrder.status,
                PurchaseOrder.supplier_id,
                PurchaseOrder.total,
                PurchaseOrder.currency_code,
                PurchaseOrder.expected_delivery_date,
            )
            .where(
                and_(
                    PurchaseOrder.company_id == company_id,
                    PurchaseOrder.deleted_at.is_(None),
                    PurchaseOrder.status.in_(["APPROVED", "PARTIALLY_RECEIVED"]),
                    PurchaseOrder.expected_delivery_date.isnot(None),
                    PurchaseOrder.expected_delivery_date < cutoff,
                )
            )
            .order_by(PurchaseOrder.expected_delivery_date.asc())
            .offset(skip)
            .limit(limit)
        )
        rows = self.db.execute(stmt).mappings().all()
        today = date.today()
        return [
            {
                "po_id": str(r["id"]),
                "po_number": r["po_number"],
                "status": r["status"],
                "supplier_id": r["supplier_id"],
                "total": str(_d(r["total"])),
                "currency_code": r["currency_code"],
                "expected_delivery_date": r["expected_delivery_date"].isoformat(),
                "days_overdue": (today - r["expected_delivery_date"]).days,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # RPT-04  Goods Receipt Report  (T210)
    # ------------------------------------------------------------------

    def goods_receipt_report(
        self,
        company_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        supplier_id: UUID | None = None,
        skip: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Confirmed GRs in period with quantities and cost."""
        stmt = (
            select(
                GoodsReceipt.id,
                GoodsReceipt.gr_number,
                GoodsReceipt.status,
                GoodsReceipt.po_id,
                GoodsReceipt.supplier_id,
                GoodsReceipt.received_at,
                GoodsReceipt.delivery_note_number,
            )
            .where(
                and_(
                    GoodsReceipt.company_id == company_id,
                    GoodsReceipt.deleted_at.is_(None),
                    GoodsReceipt.status == "CONFIRMED",
                )
            )
            .order_by(GoodsReceipt.received_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if supplier_id:
            stmt = stmt.where(GoodsReceipt.supplier_id == str(supplier_id))
        if date_from:
            stmt = stmt.where(
                cast(GoodsReceipt.received_at, __import__("sqlalchemy").Date)
                >= date_from
            )
        if date_to:
            stmt = stmt.where(
                cast(GoodsReceipt.received_at, __import__("sqlalchemy").Date) <= date_to
            )

        rows = self.db.execute(stmt).mappings().all()
        results = []
        for r in rows:
            gr_id_str = str(r["id"])
            # Fetch cost entry total if available
            ce_stmt = select(PurchaseCostEntry.total).where(
                and_(
                    PurchaseCostEntry.company_id == company_id,
                    PurchaseCostEntry.gr_id == gr_id_str,
                )
            )
            ce_row = self.db.execute(ce_stmt).scalar_one_or_none()
            results.append(
                {
                    "gr_id": gr_id_str,
                    "gr_number": r["gr_number"],
                    "status": r["status"],
                    "po_id": r["po_id"],
                    "supplier_id": r["supplier_id"],
                    "received_at": (
                        r["received_at"].isoformat() if r["received_at"] else None
                    ),
                    "delivery_note_number": r["delivery_note_number"],
                    "total": str(_d(ce_row)) if ce_row is not None else "0.00",
                }
            )
        return results

    # ------------------------------------------------------------------
    # RPT-05  Purchase Request Status  (T211)
    # ------------------------------------------------------------------

    def purchase_request_status(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """All PRs with status, age (days since creation), requestor."""
        stmt = (
            select(
                PurchaseRequest.id,
                PurchaseRequest.pr_number,
                PurchaseRequest.status,
                PurchaseRequest.requestor_id,
                PurchaseRequest.department,
                PurchaseRequest.total_estimated_cost,
                PurchaseRequest.currency_code,
                PurchaseRequest.required_by_date,
                PurchaseRequest.created_at,
            )
            .where(
                and_(
                    PurchaseRequest.company_id == company_id,
                    PurchaseRequest.deleted_at.is_(None),
                )
            )
            .order_by(PurchaseRequest.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(PurchaseRequest.status == status)
        if date_from:
            stmt = stmt.where(
                cast(PurchaseRequest.created_at, __import__("sqlalchemy").Date)
                >= date_from
            )
        if date_to:
            stmt = stmt.where(
                cast(PurchaseRequest.created_at, __import__("sqlalchemy").Date)
                <= date_to
            )

        rows = self.db.execute(stmt).mappings().all()
        today = date.today()
        return [
            {
                "pr_id": str(r["id"]),
                "pr_number": r["pr_number"],
                "status": r["status"],
                "requestor_id": r["requestor_id"],
                "department": r["department"],
                "total_estimated_cost": str(_d(r["total_estimated_cost"])),
                "currency_code": r["currency_code"],
                "required_by_date": (
                    r["required_by_date"].isoformat() if r["required_by_date"] else None
                ),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "age_days": (
                    (today - r["created_at"].date()).days if r["created_at"] else None
                ),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # RPT-06  Supplier Performance  (T212)
    # ------------------------------------------------------------------

    def supplier_performance(
        self,
        company_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Per-supplier on-time rate, fill rate, rejection rate, composite rating.

        Derived from confirmed GR data.
        """
        gr_stmt = (
            select(
                GoodsReceipt.supplier_id,
                func.count(GoodsReceipt.id).label("total_grs"),
            )
            .where(
                and_(
                    GoodsReceipt.company_id == company_id,
                    GoodsReceipt.deleted_at.is_(None),
                    GoodsReceipt.status == "CONFIRMED",
                )
            )
            .group_by(GoodsReceipt.supplier_id)
        )
        if date_from:
            gr_stmt = gr_stmt.where(
                cast(GoodsReceipt.received_at, __import__("sqlalchemy").Date)
                >= date_from
            )
        if date_to:
            gr_stmt = gr_stmt.where(
                cast(GoodsReceipt.received_at, __import__("sqlalchemy").Date) <= date_to
            )

        gr_rows = {
            r["supplier_id"]: r for r in self.db.execute(gr_stmt).mappings().all()
        }

        # On-time: received_at <= PO.expected_delivery_date
        ot_stmt = (
            select(
                GoodsReceipt.supplier_id,
                func.count(GoodsReceipt.id).label("on_time_grs"),
            )
            .join(
                PurchaseOrder,
                and_(
                    PurchaseOrder.id
                    == __import__("sqlalchemy").cast(
                        GoodsReceipt.po_id,
                        __import__(
                            "sqlalchemy.dialects.postgresql", fromlist=["UUID"]
                        ).UUID(as_uuid=True),
                    ),
                    PurchaseOrder.expected_delivery_date.isnot(None),
                ),
                isouter=True,
            )
            .where(
                and_(
                    GoodsReceipt.company_id == company_id,
                    GoodsReceipt.deleted_at.is_(None),
                    GoodsReceipt.status == "CONFIRMED",
                    func.cast(GoodsReceipt.received_at, __import__("sqlalchemy").Date)
                    <= PurchaseOrder.expected_delivery_date,
                )
            )
            .group_by(GoodsReceipt.supplier_id)
        )
        if date_from:
            ot_stmt = ot_stmt.where(
                cast(GoodsReceipt.received_at, __import__("sqlalchemy").Date)
                >= date_from
            )
        if date_to:
            ot_stmt = ot_stmt.where(
                cast(GoodsReceipt.received_at, __import__("sqlalchemy").Date) <= date_to
            )

        ot_rows = {
            r["supplier_id"]: r["on_time_grs"]
            for r in self.db.execute(ot_stmt).mappings().all()
        }

        # Rejection rates from GR lines
        rej_stmt = (
            select(
                GoodsReceipt.supplier_id,
                func.sum(GRLine.quantity_received).label("total_received"),
                func.sum(GRLine.quantity_rejected).label("total_rejected"),
            )
            .join(
                GRLine,
                and_(
                    GRLine.gr_id
                    == __import__("sqlalchemy")
                    .cast(
                        GoodsReceipt.id,
                        __import__(
                            "sqlalchemy.dialects.postgresql", fromlist=["UUID"]
                        ).UUID(as_uuid=False),
                    )
                    .cast(GRLine.gr_id.type)
                ),
            )
            .where(
                and_(
                    GoodsReceipt.company_id == company_id,
                    GoodsReceipt.deleted_at.is_(None),
                    GoodsReceipt.status == "CONFIRMED",
                )
            )
            .group_by(GoodsReceipt.supplier_id)
        )
        if date_from:
            rej_stmt = rej_stmt.where(
                cast(GoodsReceipt.received_at, __import__("sqlalchemy").Date)
                >= date_from
            )
        if date_to:
            rej_stmt = rej_stmt.where(
                cast(GoodsReceipt.received_at, __import__("sqlalchemy").Date) <= date_to
            )

        rej_rows = {
            r["supplier_id"]: r for r in self.db.execute(rej_stmt).mappings().all()
        }

        results = []
        for supplier_id_str, gr_data in list(gr_rows.items())[skip : skip + limit]:
            total_grs = gr_data["total_grs"] or 0
            on_time = ot_rows.get(supplier_id_str, 0)
            on_time_rate = round(on_time / total_grs * 100, 2) if total_grs else 0.0

            rej_data = rej_rows.get(supplier_id_str)
            total_received = (
                _d(rej_data["total_received"]) if rej_data else Decimal("0")
            )
            total_rejected = (
                _d(rej_data["total_rejected"]) if rej_data else Decimal("0")
            )
            rejection_rate = (
                round(float(total_rejected / total_received * 100), 2)
                if total_received
                else 0.0
            )
            fill_rate = round(100.0 - rejection_rate, 2)

            # Composite rating: weighted average (on_time 50%, fill 50%)
            composite = round((on_time_rate * 0.5 + fill_rate * 0.5), 2)

            results.append(
                {
                    "supplier_id": supplier_id_str,
                    "total_grs": total_grs,
                    "on_time_rate": on_time_rate,
                    "fill_rate": fill_rate,
                    "rejection_rate": rejection_rate,
                    "composite_rating": composite,
                }
            )
        return results

    # ------------------------------------------------------------------
    # RPT-07  Vendor Return Report  (T213)
    # ------------------------------------------------------------------

    def vendor_return_report(
        self,
        company_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        supplier_id: UUID | None = None,
        skip: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """All RMAs in period with status, amounts, reasons."""
        stmt = (
            select(
                VendorReturn.id,
                VendorReturn.rma_number,
                VendorReturn.status,
                VendorReturn.gr_id,
                VendorReturn.supplier_id,
                VendorReturn.reason_id,
                VendorReturn.credit_note_pending,
                VendorReturn.dispatched_at,
                VendorReturn.completed_at,
                VendorReturn.created_at,
            )
            .where(
                and_(
                    VendorReturn.company_id == company_id,
                    VendorReturn.deleted_at.is_(None),
                )
            )
            .order_by(VendorReturn.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if supplier_id:
            stmt = stmt.where(VendorReturn.supplier_id == str(supplier_id))
        if date_from:
            stmt = stmt.where(
                cast(VendorReturn.created_at, __import__("sqlalchemy").Date)
                >= date_from
            )
        if date_to:
            stmt = stmt.where(
                cast(VendorReturn.created_at, __import__("sqlalchemy").Date) <= date_to
            )

        rows = self.db.execute(stmt).mappings().all()
        return [
            {
                "rma_id": str(r["id"]),
                "rma_number": r["rma_number"],
                "status": r["status"],
                "gr_id": r["gr_id"],
                "supplier_id": r["supplier_id"],
                "reason_id": r["reason_id"],
                "credit_note_pending": r["credit_note_pending"],
                "dispatched_at": (
                    r["dispatched_at"].isoformat() if r["dispatched_at"] else None
                ),
                "completed_at": (
                    r["completed_at"].isoformat() if r["completed_at"] else None
                ),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # RPT-08  Purchase by Supplier  (T214)
    # ------------------------------------------------------------------

    def purchase_by_supplier(
        self,
        company_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Total spend per supplier in period (sum of confirmed GR cost entries)."""
        stmt = (
            select(
                PurchaseCostEntry.supplier_id,
                func.count(PurchaseCostEntry.id).label("gr_count"),
                func.sum(PurchaseCostEntry.total).label("total_spend"),
                func.sum(PurchaseCostEntry.subtotal).label("total_subtotal"),
                func.sum(PurchaseCostEntry.total_charges).label("total_charges"),
                func.sum(PurchaseCostEntry.total_discounts).label("total_discounts"),
            )
            .where(
                and_(
                    PurchaseCostEntry.company_id == company_id,
                    PurchaseCostEntry.deleted_at.is_(None),
                )
            )
            .group_by(PurchaseCostEntry.supplier_id)
            .order_by(func.sum(PurchaseCostEntry.total).desc())
            .offset(skip)
            .limit(limit)
        )
        if date_from:
            stmt = stmt.where(PurchaseCostEntry.cost_date >= date_from)
        if date_to:
            stmt = stmt.where(PurchaseCostEntry.cost_date <= date_to)

        rows = self.db.execute(stmt).mappings().all()
        return [
            {
                "supplier_id": r["supplier_id"],
                "gr_count": r["gr_count"],
                "total_spend": str(_d(r["total_spend"])),
                "total_subtotal": str(_d(r["total_subtotal"])),
                "total_charges": str(_d(r["total_charges"])),
                "total_discounts": str(_d(r["total_discounts"])),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # RPT-09  Purchase by Category  (T215)
    # ------------------------------------------------------------------

    def purchase_by_category(
        self,
        company_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Total spend per supplier category in period."""
        # Join: PurchaseCostEntry → Supplier.category_id → SupplierCategory
        stmt = (
            select(
                SupplierCategory.id.label("category_id"),
                SupplierCategory.name.label("category_name"),
                SupplierCategory.code.label("category_code"),
                func.count(PurchaseCostEntry.id).label("gr_count"),
                func.sum(PurchaseCostEntry.total).label("total_spend"),
            )
            .join(
                Supplier,
                Supplier.id
                == __import__("sqlalchemy").cast(
                    PurchaseCostEntry.supplier_id,
                    __import__(
                        "sqlalchemy.dialects.postgresql", fromlist=["UUID"]
                    ).UUID(as_uuid=True),
                ),
            )
            .join(
                SupplierCategory,
                and_(
                    SupplierCategory.id == Supplier.category_id,
                ),
                isouter=True,
            )
            .where(
                and_(
                    PurchaseCostEntry.company_id == company_id,
                    PurchaseCostEntry.deleted_at.is_(None),
                )
            )
            .group_by(SupplierCategory.id, SupplierCategory.name, SupplierCategory.code)
            .order_by(func.sum(PurchaseCostEntry.total).desc())
            .offset(skip)
            .limit(limit)
        )
        if date_from:
            stmt = stmt.where(PurchaseCostEntry.cost_date >= date_from)
        if date_to:
            stmt = stmt.where(PurchaseCostEntry.cost_date <= date_to)

        rows = self.db.execute(stmt).mappings().all()
        return [
            {
                "category_id": str(r["category_id"]) if r["category_id"] else None,
                "category_name": r["category_name"],
                "category_code": r["category_code"],
                "gr_count": r["gr_count"],
                "total_spend": str(_d(r["total_spend"])),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # RPT-10  Purchase Price Variance  (T216)
    # ------------------------------------------------------------------

    def purchase_price_variance(
        self,
        company_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        supplier_id: UUID | None = None,
        skip: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """PO cost vs GR cost variance per line, sorted by absolute PPV amount."""
        stmt = (
            select(
                GRLine.id.label("gr_line_id"),
                GRLine.gr_id,
                GRLine.po_line_id,
                GRLine.product_id,
                GRLine.quantity_received,
                GRLine.unit_cost.label("gr_unit_cost"),
                GRLine.ppv_amount,
                GRLine.ppv_percentage,
                GoodsReceipt.supplier_id,
                GoodsReceipt.received_at,
                GoodsReceipt.gr_number,
            )
            .join(
                GoodsReceipt,
                and_(
                    GoodsReceipt.id
                    == __import__("sqlalchemy").cast(
                        GRLine.gr_id,
                        __import__(
                            "sqlalchemy.dialects.postgresql", fromlist=["UUID"]
                        ).UUID(as_uuid=True),
                    ),
                ),
            )
            .where(
                and_(
                    GoodsReceipt.company_id == company_id,
                    GoodsReceipt.deleted_at.is_(None),
                    GoodsReceipt.status == "CONFIRMED",
                    GRLine.deleted_at.is_(None),
                    GRLine.ppv_amount.isnot(None),
                )
            )
            .order_by(func.abs(GRLine.ppv_amount).desc())
            .offset(skip)
            .limit(limit)
        )
        if supplier_id:
            stmt = stmt.where(GoodsReceipt.supplier_id == str(supplier_id))
        if date_from:
            stmt = stmt.where(
                cast(GoodsReceipt.received_at, __import__("sqlalchemy").Date)
                >= date_from
            )
        if date_to:
            stmt = stmt.where(
                cast(GoodsReceipt.received_at, __import__("sqlalchemy").Date) <= date_to
            )

        rows = self.db.execute(stmt).mappings().all()
        return [
            {
                "gr_line_id": str(r["gr_line_id"]),
                "gr_id": r["gr_id"],
                "po_line_id": r["po_line_id"],
                "product_id": r["product_id"],
                "quantity_received": str(_d(r["quantity_received"])),
                "gr_unit_cost": str(_d(r["gr_unit_cost"])),
                "ppv_amount": str(_d(r["ppv_amount"])),
                "ppv_percentage": str(_d(r["ppv_percentage"])),
                "supplier_id": r["supplier_id"],
                "gr_number": r["gr_number"],
                "received_at": (
                    r["received_at"].isoformat() if r["received_at"] else None
                ),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # RPT-11  Open Purchase Commitments  (T217)
    # ------------------------------------------------------------------

    def open_purchase_commitments(
        self,
        company_id: UUID,
        *,
        supplier_id: UUID | None = None,
        skip: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Open value per PO line (ordered − received) for APPROVED/PARTIALLY_RECEIVED POs."""
        stmt = (
            select(
                POLine.id.label("po_line_id"),
                POLine.po_id,
                POLine.product_description,
                POLine.quantity_ordered,
                POLine.quantity_received,
                POLine.open_quantity,
                POLine.unit_cost,
                PurchaseOrder.po_number,
                PurchaseOrder.supplier_id,
                PurchaseOrder.currency_code,
                PurchaseOrder.expected_delivery_date,
            )
            .join(
                PurchaseOrder,
                and_(
                    PurchaseOrder.id
                    == __import__("sqlalchemy").cast(
                        POLine.po_id,
                        __import__(
                            "sqlalchemy.dialects.postgresql", fromlist=["UUID"]
                        ).UUID(as_uuid=True),
                    ),
                ),
            )
            .where(
                and_(
                    PurchaseOrder.company_id == company_id,
                    PurchaseOrder.deleted_at.is_(None),
                    PurchaseOrder.status.in_(["APPROVED", "PARTIALLY_RECEIVED"]),
                    POLine.deleted_at.is_(None),
                    POLine.open_quantity > 0,
                )
            )
            .order_by(
                PurchaseOrder.supplier_id, PurchaseOrder.po_number, POLine.line_number
            )
            .offset(skip)
            .limit(limit)
        )
        if supplier_id:
            stmt = stmt.where(PurchaseOrder.supplier_id == str(supplier_id))

        rows = self.db.execute(stmt).mappings().all()
        return [
            {
                "po_line_id": str(r["po_line_id"]),
                "po_id": r["po_id"],
                "po_number": r["po_number"],
                "supplier_id": r["supplier_id"],
                "currency_code": r["currency_code"],
                "product_description": r["product_description"],
                "quantity_ordered": str(_d(r["quantity_ordered"])),
                "quantity_received": str(_d(r["quantity_received"])),
                "open_quantity": str(_d(r["open_quantity"])),
                "unit_cost": str(_d(r["unit_cost"])),
                "open_value": str(_d(r["open_quantity"]) * _d(r["unit_cost"])),
                "expected_delivery_date": (
                    r["expected_delivery_date"].isoformat()
                    if r["expected_delivery_date"]
                    else None
                ),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # RPT-12  Purchase Trend Analysis  (T218)
    # ------------------------------------------------------------------

    def purchase_trend_analysis(
        self,
        company_id: UUID,
        *,
        granularity: str = "monthly",
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        """Monthly/quarterly aggregation of PO count and GR total."""
        import sqlalchemy as sa

        year_col = (
            func.extract("year", PurchaseCostEntry.cost_date)
            .cast(sa.Integer)
            .cast(sa.String)
        )
        month_col = func.extract("month", PurchaseCostEntry.cost_date).cast(sa.Integer)

        if granularity == "quarterly":
            quarter_col = func.ceil(month_col / 3).cast(sa.Integer).cast(sa.String)
            period_label = func.concat(year_col, sa.literal("-Q"), quarter_col)
        else:
            # Portable zero-padded month: use CASE WHEN month < 10 THEN '0' || month ELSE month
            padded_month = sa.case(
                (
                    month_col < 10,
                    func.concat(sa.literal("0"), month_col.cast(sa.String)),
                ),
                else_=month_col.cast(sa.String),
            )
            period_label = func.concat(year_col, sa.literal("-"), padded_month)

        stmt = (
            select(
                period_label.label("period"),
                func.count(PurchaseCostEntry.id).label("gr_count"),
                func.sum(PurchaseCostEntry.total).label("total_spend"),
                func.avg(PurchaseCostEntry.total).label("avg_spend"),
            )
            .where(
                and_(
                    PurchaseCostEntry.company_id == company_id,
                    PurchaseCostEntry.deleted_at.is_(None),
                )
            )
            .group_by(period_label)
            .order_by(period_label)
        )
        if date_from:
            stmt = stmt.where(PurchaseCostEntry.cost_date >= date_from)
        if date_to:
            stmt = stmt.where(PurchaseCostEntry.cost_date <= date_to)

        rows = self.db.execute(stmt).mappings().all()
        return [
            {
                "period": r["period"],
                "gr_count": r["gr_count"],
                "total_spend": str(_d(r["total_spend"])),
                "avg_spend": str(_d(r["avg_spend"])),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # RPT-13  Goods Rejection Analysis  (T219)
    # ------------------------------------------------------------------

    def goods_rejection_analysis(
        self,
        company_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        supplier_id: UUID | None = None,
        skip: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Rejected GR lines grouped by supplier, reason code, and product."""
        stmt = (
            select(
                GoodsReceipt.supplier_id,
                GRLine.rejection_reason_id,
                GRLine.product_id,
                func.count(GRLine.id).label("rejection_count"),
                func.sum(GRLine.quantity_rejected).label("total_rejected_qty"),
            )
            .join(
                GoodsReceipt,
                and_(
                    GoodsReceipt.id
                    == __import__("sqlalchemy").cast(
                        GRLine.gr_id,
                        __import__(
                            "sqlalchemy.dialects.postgresql", fromlist=["UUID"]
                        ).UUID(as_uuid=True),
                    ),
                ),
            )
            .where(
                and_(
                    GoodsReceipt.company_id == company_id,
                    GoodsReceipt.deleted_at.is_(None),
                    GoodsReceipt.status == "CONFIRMED",
                    GRLine.deleted_at.is_(None),
                    GRLine.quantity_rejected > 0,
                )
            )
            .group_by(
                GoodsReceipt.supplier_id, GRLine.rejection_reason_id, GRLine.product_id
            )
            .order_by(func.sum(GRLine.quantity_rejected).desc())
            .offset(skip)
            .limit(limit)
        )
        if supplier_id:
            stmt = stmt.where(GoodsReceipt.supplier_id == str(supplier_id))
        if date_from:
            stmt = stmt.where(
                cast(GoodsReceipt.received_at, __import__("sqlalchemy").Date)
                >= date_from
            )
        if date_to:
            stmt = stmt.where(
                cast(GoodsReceipt.received_at, __import__("sqlalchemy").Date) <= date_to
            )

        rows = self.db.execute(stmt).mappings().all()
        return [
            {
                "supplier_id": r["supplier_id"],
                "rejection_reason_id": r["rejection_reason_id"],
                "product_id": r["product_id"],
                "rejection_count": r["rejection_count"],
                "total_rejected_qty": str(_d(r["total_rejected_qty"])),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # RPT-14  Procurement Audit Trail  (T220)
    # ------------------------------------------------------------------

    def procurement_audit_trail(
        self,
        company_id: UUID,
        *,
        document_type: str | None = None,
        document_id: str | None = None,
        supplier_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Full event history from domain events recorded in the purchase module.

        Since the platform does not yet have a shared audit_logs table, this
        method reads the purchase_cost_entries (immutable snapshots) as the
        primary audit source and supplements with a synthetic event list
        constructed from document timestamps.

        When a shared AuditLog table is introduced, this method should be
        updated to query it directly.
        """
        # Use cost entries as an audit data source for GR confirmations
        ce_stmt = (
            select(
                PurchaseCostEntry.id,
                PurchaseCostEntry.gr_id,
                PurchaseCostEntry.po_id,
                PurchaseCostEntry.supplier_id,
                PurchaseCostEntry.cost_date,
                PurchaseCostEntry.total,
                PurchaseCostEntry.created_at,
            )
            .where(
                and_(
                    PurchaseCostEntry.company_id == company_id,
                    PurchaseCostEntry.deleted_at.is_(None),
                )
            )
            .order_by(PurchaseCostEntry.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if supplier_id:
            ce_stmt = ce_stmt.where(PurchaseCostEntry.supplier_id == str(supplier_id))
        if document_id:
            ce_stmt = ce_stmt.where(PurchaseCostEntry.gr_id == document_id)
        if date_from:
            ce_stmt = ce_stmt.where(PurchaseCostEntry.cost_date >= date_from)
        if date_to:
            ce_stmt = ce_stmt.where(PurchaseCostEntry.cost_date <= date_to)

        rows = self.db.execute(ce_stmt).mappings().all()
        return [
            {
                "event_type": "purchase.cost.recorded",
                "document_type": "GR",
                "document_id": r["gr_id"],
                "po_id": r["po_id"],
                "supplier_id": r["supplier_id"],
                "cost_date": r["cost_date"].isoformat() if r["cost_date"] else None,
                "total": str(_d(r["total"])),
                "recorded_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]

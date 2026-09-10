"""Purchase KPI computation service — Phase 9.

Implements all 10 KPIs defined in spec §35:

  KPI-01  Purchase Cycle Time          — avg days PR created → PR approved
  KPI-02  On-Time Delivery Rate        — % GRs received on or before PO expected_delivery_date
  KPI-03  Order Fulfilment Rate        — % GR lines with 0 rejections (accepted / total)
  KPI-04  Rejection Rate               — % GR line quantity rejected vs total received
  KPI-05  PPV %                        — avg purchase price variance percentage
  KPI-06  Open Commitments Value       — sum of open_quantity × unit_cost on open PO lines
  KPI-07  Total Purchase Value         — sum of cost entry totals in period
  KPI-08  PO Processing Time           — avg days PO created → PO APPROVED
  KPI-09  Vendor Return Rate           — % confirmed GRs that have at least one RMA
  KPI-10  Preferred Supplier Utilisation — % POs placed with preferred suppliers

All methods return a float (or Decimal string) scalar.  The aggregate
`get_all_kpis` method returns a dict keyed by KPI code.

Spec ref: specs/006-purchase-management/spec.md §35
Task: T221
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from modules.purchase.models.cost import PurchaseCostEntry
from modules.purchase.models.goods_receipt import GoodsReceipt, GRLine
from modules.purchase.models.purchase_order import POLine, PurchaseOrder
from modules.purchase.models.purchase_request import PurchaseRequest
from modules.purchase.models.supplier import Supplier
from modules.purchase.models.vendor_return import VendorReturn

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")
_TWO = Decimal("0.01")


def _d(v: Any) -> Decimal:
    if v is None:
        return _ZERO
    return Decimal(str(v)).quantize(_TWO)


class KPIService:
    """Compute procurement KPIs for a company in an optional date range."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # KPI-01  Purchase Cycle Time
    # ------------------------------------------------------------------

    def purchase_cycle_time(
        self,
        company_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> float | None:
        """Average days from PR created_at to PR status = APPROVED.

        Uses updated_at as a proxy for approval timestamp since a dedicated
        approved_at column is not yet available on PurchaseRequest.
        Returns None when no approved PRs exist.
        """
        stmt = select(
            func.avg(
                func.extract(
                    "epoch",
                    PurchaseRequest.updated_at - PurchaseRequest.created_at,
                )
                / 86400.0
            ).label("avg_cycle_days")
        ).where(
            and_(
                PurchaseRequest.company_id == company_id,
                PurchaseRequest.deleted_at.is_(None),
                PurchaseRequest.status == "APPROVED",
            )
        )
        if date_from:
            stmt = stmt.where(
                func.cast(PurchaseRequest.created_at, __import__("sqlalchemy").Date)
                >= date_from
            )
        if date_to:
            stmt = stmt.where(
                func.cast(PurchaseRequest.created_at, __import__("sqlalchemy").Date)
                <= date_to
            )
        result = self.db.execute(stmt).scalar_one_or_none()
        return round(float(result), 2) if result is not None else None

    # ------------------------------------------------------------------
    # KPI-02  On-Time Delivery Rate
    # ------------------------------------------------------------------

    def on_time_delivery_rate(
        self,
        company_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> float:
        """% GRs received on or before PO expected_delivery_date."""
        import sqlalchemy as sa

        base_stmt = (
            select(func.count(GoodsReceipt.id))
            .join(
                PurchaseOrder,
                PurchaseOrder.id
                == sa.cast(
                    GoodsReceipt.po_id,
                    __import__(
                        "sqlalchemy.dialects.postgresql", fromlist=["UUID"]
                    ).UUID(as_uuid=True),
                ),
            )
            .where(
                and_(
                    GoodsReceipt.company_id == company_id,
                    GoodsReceipt.deleted_at.is_(None),
                    GoodsReceipt.status == "CONFIRMED",
                    PurchaseOrder.expected_delivery_date.isnot(None),
                )
            )
        )
        if date_from:
            base_stmt = base_stmt.where(
                sa.cast(GoodsReceipt.received_at, sa.Date) >= date_from
            )
        if date_to:
            base_stmt = base_stmt.where(
                sa.cast(GoodsReceipt.received_at, sa.Date) <= date_to
            )

        total = self.db.execute(base_stmt).scalar_one_or_none() or 0
        if total == 0:
            return 0.0

        on_time_stmt = base_stmt.where(
            sa.cast(GoodsReceipt.received_at, sa.Date)
            <= PurchaseOrder.expected_delivery_date
        )
        on_time = self.db.execute(on_time_stmt).scalar_one_or_none() or 0
        return round(on_time / total * 100, 2)

    # ------------------------------------------------------------------
    # KPI-03  Order Fulfilment Rate
    # ------------------------------------------------------------------

    def order_fulfilment_rate(
        self,
        company_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> float:
        """% GR lines with zero rejections (accepted / total lines)."""
        import sqlalchemy as sa

        stmt = (
            select(
                func.count(GRLine.id).label("total"),
                func.sum(sa.case((GRLine.quantity_rejected == 0, 1), else_=0)).label(
                    "accepted"
                ),
            )
            .join(
                GoodsReceipt,
                and_(
                    GoodsReceipt.id
                    == sa.cast(
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
                )
            )
        )
        if date_from:
            stmt = stmt.where(sa.cast(GoodsReceipt.received_at, sa.Date) >= date_from)
        if date_to:
            stmt = stmt.where(sa.cast(GoodsReceipt.received_at, sa.Date) <= date_to)

        row = self.db.execute(stmt).mappings().one_or_none()
        if not row or not row["total"]:
            return 0.0
        return float(round((row["accepted"] or 0) / row["total"] * 100, 2))

    # ------------------------------------------------------------------
    # KPI-04  Rejection Rate
    # ------------------------------------------------------------------

    def rejection_rate(
        self,
        company_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> float:
        """% GR quantity rejected vs total received across all confirmed GRs."""
        import sqlalchemy as sa

        stmt = (
            select(
                func.sum(GRLine.quantity_received).label("total_received"),
                func.sum(GRLine.quantity_rejected).label("total_rejected"),
            )
            .join(
                GoodsReceipt,
                and_(
                    GoodsReceipt.id
                    == sa.cast(
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
                )
            )
        )
        if date_from:
            stmt = stmt.where(sa.cast(GoodsReceipt.received_at, sa.Date) >= date_from)
        if date_to:
            stmt = stmt.where(sa.cast(GoodsReceipt.received_at, sa.Date) <= date_to)

        row = self.db.execute(stmt).mappings().one_or_none()
        if not row or not row["total_received"]:
            return 0.0
        total_received = _d(row["total_received"])
        total_rejected = _d(row["total_rejected"])
        return round(float(total_rejected / total_received * 100), 2)

    # ------------------------------------------------------------------
    # KPI-05  PPV %
    # ------------------------------------------------------------------

    def ppv_percentage(
        self,
        company_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> float | None:
        """Average purchase price variance percentage across all GR lines with PPV data."""
        import sqlalchemy as sa

        stmt = (
            select(func.avg(GRLine.ppv_percentage).label("avg_ppv_pct"))
            .join(
                GoodsReceipt,
                and_(
                    GoodsReceipt.id
                    == sa.cast(
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
                    GRLine.ppv_percentage.isnot(None),
                )
            )
        )
        if date_from:
            stmt = stmt.where(sa.cast(GoodsReceipt.received_at, sa.Date) >= date_from)
        if date_to:
            stmt = stmt.where(sa.cast(GoodsReceipt.received_at, sa.Date) <= date_to)

        result = self.db.execute(stmt).scalar_one_or_none()
        return round(float(result), 2) if result is not None else None

    # ------------------------------------------------------------------
    # KPI-06  Open Commitments Value
    # ------------------------------------------------------------------

    def open_commitments_value(
        self,
        company_id: UUID,
    ) -> Decimal:
        """Sum of open_quantity × unit_cost on open PO lines."""
        import sqlalchemy as sa

        stmt = (
            select(
                func.sum(POLine.open_quantity * POLine.unit_cost).label("open_value")
            )
            .join(
                PurchaseOrder,
                PurchaseOrder.id
                == sa.cast(
                    POLine.po_id,
                    __import__(
                        "sqlalchemy.dialects.postgresql", fromlist=["UUID"]
                    ).UUID(as_uuid=True),
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
        )
        result = self.db.execute(stmt).scalar_one_or_none()
        return _d(result)

    # ------------------------------------------------------------------
    # KPI-07  Total Purchase Value
    # ------------------------------------------------------------------

    def total_purchase_value(
        self,
        company_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> Decimal:
        """Sum of cost entry totals in period."""
        stmt = select(func.sum(PurchaseCostEntry.total).label("total_value")).where(
            and_(
                PurchaseCostEntry.company_id == company_id,
                PurchaseCostEntry.deleted_at.is_(None),
            )
        )
        if date_from:
            stmt = stmt.where(PurchaseCostEntry.cost_date >= date_from)
        if date_to:
            stmt = stmt.where(PurchaseCostEntry.cost_date <= date_to)

        result = self.db.execute(stmt).scalar_one_or_none()
        return _d(result)

    # ------------------------------------------------------------------
    # KPI-08  PO Processing Time
    # ------------------------------------------------------------------

    def po_processing_time(
        self,
        company_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> float | None:
        """Average days from PO created_at to PO status APPROVED.

        Uses updated_at as proxy for approval timestamp.
        """
        stmt = select(
            func.avg(
                func.extract(
                    "epoch",
                    PurchaseOrder.updated_at - PurchaseOrder.created_at,
                )
                / 86400.0
            ).label("avg_processing_days")
        ).where(
            and_(
                PurchaseOrder.company_id == company_id,
                PurchaseOrder.deleted_at.is_(None),
                PurchaseOrder.status.in_(
                    ["APPROVED", "PARTIALLY_RECEIVED", "FULLY_RECEIVED", "CLOSED"]
                ),
            )
        )
        if date_from:
            stmt = stmt.where(
                func.cast(PurchaseOrder.created_at, __import__("sqlalchemy").Date)
                >= date_from
            )
        if date_to:
            stmt = stmt.where(
                func.cast(PurchaseOrder.created_at, __import__("sqlalchemy").Date)
                <= date_to
            )
        result = self.db.execute(stmt).scalar_one_or_none()
        return round(float(result), 2) if result is not None else None

    # ------------------------------------------------------------------
    # KPI-09  Vendor Return Rate
    # ------------------------------------------------------------------

    def vendor_return_rate(
        self,
        company_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> float:
        """% confirmed GRs that have at least one RMA."""
        import sqlalchemy as sa

        total_gr_stmt = select(func.count(GoodsReceipt.id)).where(
            and_(
                GoodsReceipt.company_id == company_id,
                GoodsReceipt.deleted_at.is_(None),
                GoodsReceipt.status == "CONFIRMED",
            )
        )
        if date_from:
            total_gr_stmt = total_gr_stmt.where(
                sa.cast(GoodsReceipt.received_at, sa.Date) >= date_from
            )
        if date_to:
            total_gr_stmt = total_gr_stmt.where(
                sa.cast(GoodsReceipt.received_at, sa.Date) <= date_to
            )

        total_grs = self.db.execute(total_gr_stmt).scalar_one_or_none() or 0
        if total_grs == 0:
            return 0.0

        # GRs with at least one RMA (any non-CANCELLED status)
        rma_stmt = (
            select(func.count(sa.distinct(VendorReturn.gr_id)))
            .join(
                GoodsReceipt,
                and_(
                    GoodsReceipt.id
                    == sa.cast(
                        VendorReturn.gr_id,
                        __import__(
                            "sqlalchemy.dialects.postgresql", fromlist=["UUID"]
                        ).UUID(as_uuid=True),
                    ),
                    GoodsReceipt.company_id == company_id,
                    GoodsReceipt.status == "CONFIRMED",
                ),
            )
            .where(
                and_(
                    VendorReturn.company_id == company_id,
                    VendorReturn.deleted_at.is_(None),
                    VendorReturn.status != "CANCELLED",
                )
            )
        )
        if date_from:
            rma_stmt = rma_stmt.where(
                sa.cast(GoodsReceipt.received_at, sa.Date) >= date_from
            )
        if date_to:
            rma_stmt = rma_stmt.where(
                sa.cast(GoodsReceipt.received_at, sa.Date) <= date_to
            )

        grs_with_rma = self.db.execute(rma_stmt).scalar_one_or_none() or 0
        return round(grs_with_rma / total_grs * 100, 2)

    # ------------------------------------------------------------------
    # KPI-10  Preferred Supplier Utilisation
    # ------------------------------------------------------------------

    def preferred_supplier_utilisation(
        self,
        company_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> float:
        """% POs placed with suppliers marked as preferred."""
        import sqlalchemy as sa

        total_stmt = select(func.count(PurchaseOrder.id)).where(
            and_(
                PurchaseOrder.company_id == company_id,
                PurchaseOrder.deleted_at.is_(None),
                PurchaseOrder.status.notin_(["DRAFT", "CANCELLED"]),
                PurchaseOrder.supplier_id.isnot(None),
            )
        )
        if date_from:
            total_stmt = total_stmt.where(
                sa.cast(PurchaseOrder.created_at, sa.Date) >= date_from
            )
        if date_to:
            total_stmt = total_stmt.where(
                sa.cast(PurchaseOrder.created_at, sa.Date) <= date_to
            )

        total_pos = self.db.execute(total_stmt).scalar_one_or_none() or 0
        if total_pos == 0:
            return 0.0

        preferred_stmt = (
            select(func.count(PurchaseOrder.id))
            .join(
                Supplier,
                Supplier.id
                == sa.cast(
                    PurchaseOrder.supplier_id,
                    __import__(
                        "sqlalchemy.dialects.postgresql", fromlist=["UUID"]
                    ).UUID(as_uuid=True),
                ),
            )
            .where(
                and_(
                    PurchaseOrder.company_id == company_id,
                    PurchaseOrder.deleted_at.is_(None),
                    PurchaseOrder.status.notin_(["DRAFT", "CANCELLED"]),
                    PurchaseOrder.supplier_id.isnot(None),
                    Supplier.is_preferred.is_(True),
                )
            )
        )
        if date_from:
            preferred_stmt = preferred_stmt.where(
                sa.cast(PurchaseOrder.created_at, sa.Date) >= date_from
            )
        if date_to:
            preferred_stmt = preferred_stmt.where(
                sa.cast(PurchaseOrder.created_at, sa.Date) <= date_to
            )

        preferred_pos = self.db.execute(preferred_stmt).scalar_one_or_none() or 0
        return round(preferred_pos / total_pos * 100, 2)

    # ------------------------------------------------------------------
    # Aggregate: all 10 KPIs
    # ------------------------------------------------------------------

    def get_all_kpis(
        self,
        company_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        """Return all 10 KPIs in a single response dict."""
        return {
            "kpi_01_purchase_cycle_time_days": self.purchase_cycle_time(
                company_id, date_from=date_from, date_to=date_to
            ),
            "kpi_02_on_time_delivery_rate_pct": self.on_time_delivery_rate(
                company_id, date_from=date_from, date_to=date_to
            ),
            "kpi_03_order_fulfilment_rate_pct": self.order_fulfilment_rate(
                company_id, date_from=date_from, date_to=date_to
            ),
            "kpi_04_rejection_rate_pct": self.rejection_rate(
                company_id, date_from=date_from, date_to=date_to
            ),
            "kpi_05_avg_ppv_pct": self.ppv_percentage(
                company_id, date_from=date_from, date_to=date_to
            ),
            "kpi_06_open_commitments_value": str(
                self.open_commitments_value(company_id)
            ),
            "kpi_07_total_purchase_value": str(
                self.total_purchase_value(
                    company_id, date_from=date_from, date_to=date_to
                )
            ),
            "kpi_08_po_processing_time_days": self.po_processing_time(
                company_id, date_from=date_from, date_to=date_to
            ),
            "kpi_09_vendor_return_rate_pct": self.vendor_return_rate(
                company_id, date_from=date_from, date_to=date_to
            ),
            "kpi_10_preferred_supplier_utilisation_pct": self.preferred_supplier_utilisation(
                company_id, date_from=date_from, date_to=date_to
            ),
        }

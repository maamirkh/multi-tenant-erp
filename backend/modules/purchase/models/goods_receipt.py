"""Goods Receipt ORM models — Phase 6.

Phase 6 entities:
  GoodsReceipt  — physical receipt of goods against an approved PO
  GRLine        — individual received line items with PPV computation

All FK columns use PG_UUID(as_uuid=False) (string hex FK pattern).
company_id / id use Uuid(as_uuid=True) via TenantBaseModel.

Business rules:
  - GR only against APPROVED or PARTIALLY_RECEIVED PO
  - CONFIRMED = immutable; no edits after confirmation
  - Confirmation is atomic with Epic 5 stock movement write
  - PPV = (gr_unit_cost - po_unit_cost) * quantity_received

Spec ref: specs/006-purchase-management/data-model.md §GoodsReceipt Aggregate
Tasks: T148, T149
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

# ---------------------------------------------------------------------------
# GoodsReceipt  (T148)
# ---------------------------------------------------------------------------

GR_STATUSES = ("DRAFT", "CONFIRMED")


class GoodsReceipt(TenantBaseModel):
    """Physical receipt of goods against an approved Purchase Order.

    Lifecycle:
      DRAFT → CONFIRMED (immutable after confirmation)

    Invariants:
      - gr_number is unique per company (auto-generated GR-YYYY-NNNNNN)
      - PO must be in APPROVED or PARTIALLY_RECEIVED status
      - Confirmation is atomic: GR status, stock movements, PO status all change together
      - Once CONFIRMED, no edits or deletes are permitted
    """

    __tablename__ = "goods_receipts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','CONFIRMED')",
            name="ck_goods_receipts_status",
        ),
        UniqueConstraint(
            "company_id", "gr_number", name="uq_goods_receipts_company_number"
        ),
        # ix_goods_receipts_company_id is auto-created by TenantBaseModel (index=True on company_id)
        Index("ix_goods_receipts_po_id", "po_id"),
        Index("ix_goods_receipts_status", "status"),
        {"comment": "Goods receipt documents — physical receipt of ordered goods"},
    )

    gr_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Auto-generated document number e.g. GR-2026-000001",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="DRAFT",
        doc="Lifecycle status: DRAFT | CONFIRMED",
    )

    po_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to PurchaseOrder — must be APPROVED or PARTIALLY_RECEIVED",
    )

    supplier_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Supplier (denormalised from PO for fast querying)",
    )

    received_by: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to User who performed the receipt",
    )

    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when goods were physically received",
    )

    delivery_note_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Supplier delivery note / packing slip number",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Internal notes about this receipt",
    )

    warehouse_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to inventory warehouse (Epic 5). When set, triggers stock movement on confirm.",
    )

    landed_cost_ready: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Reserved hook for Epic 8.x landed cost computation",
    )


# ---------------------------------------------------------------------------
# GRLine  (T149)
# ---------------------------------------------------------------------------


class GRLine(TenantBaseModel):
    """Individual received line item on a Goods Receipt.

    PPV (Purchase Price Variance):
      ppv_amount      = (unit_cost − po_unit_cost) × quantity_received
      ppv_percentage  = ppv_amount / (po_unit_cost × quantity_received) × 100
                        (0 if po_unit_cost = 0)

    Invariants:
      - quantity_received >= 0
      - quantity_rejected >= 0
      - unit_cost >= 0
    """

    __tablename__ = "gr_lines"
    __table_args__ = (
        CheckConstraint(
            "quantity_received >= 0",
            name="ck_gr_lines_quantity_received_non_negative",
        ),
        CheckConstraint(
            "quantity_rejected >= 0",
            name="ck_gr_lines_quantity_rejected_non_negative",
        ),
        CheckConstraint(
            "unit_cost >= 0",
            name="ck_gr_lines_unit_cost_non_negative",
        ),
        Index("ix_gr_lines_gr_id", "gr_id"),
        Index("ix_gr_lines_po_line_id", "po_line_id"),
        {"comment": "Goods receipt line items with PPV computation"},
    )

    gr_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to GoodsReceipt",
    )

    po_line_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to POLine — identifies which PO line this receipt is for",
    )

    product_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to Epic 5 product catalog (null for free-text PO lines)",
    )

    quantity_received: Mapped[object] = mapped_column(
        Numeric(15, 3),
        nullable=False,
        server_default="0.000",
        doc="Quantity actually received (accepted)",
    )

    quantity_rejected: Mapped[object] = mapped_column(
        Numeric(15, 3),
        nullable=False,
        server_default="0.000",
        doc="Quantity rejected at goods receipt",
    )

    rejection_reason_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to PurchaseReasonCode — reason for rejection",
    )

    unit_cost: Mapped[object] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        server_default="0.0000",
        doc="Actual unit cost at time of receipt (may differ from PO unit cost)",
    )

    po_unit_cost: Mapped[object] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        server_default="0.0000",
        doc="PO unit cost captured at GR creation for PPV computation",
    )

    ppv_amount: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0.00",
        doc="Purchase Price Variance amount = (unit_cost - po_unit_cost) * quantity_received",
    )

    ppv_percentage: Mapped[object] = mapped_column(
        Numeric(8, 4),
        nullable=False,
        server_default="0.0000",
        doc="PPV percentage relative to PO cost",
    )

    # Tax readiness (T196) — captured at GR time, computation deferred to AP
    tax_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Tax code — tax readiness for future AP integration",
    )

    tax_rate: Mapped[object] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Tax rate — tax readiness for future AP integration",
    )

    tax_amount: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Tax amount — tax readiness for future AP integration",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Notes for this line",
    )

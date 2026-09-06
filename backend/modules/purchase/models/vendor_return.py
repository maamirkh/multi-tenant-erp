"""Vendor Return (RMA) ORM models — Phase 7.

Phase 7 entities:
  VendorReturn  — RMA aggregate root; return of goods from a confirmed GR
  ReturnLine    — individual return line items

All FK columns use PG_UUID(as_uuid=False) (string hex FK pattern).
company_id / id use Uuid(as_uuid=True) via TenantBaseModel.

Business rules:
  - RMA only against CONFIRMED GoodsReceipt
  - return_quantity per line ≤ (gr_line.quantity_received − gr_line.quantity_rejected)
  - DISPATCHED is atomic with Epic 5 PURCHASE_RETURN_OUTBOUND stock movement
  - COMPLETED sets credit_note_pending = True
  - State machine: DRAFT → SUBMITTED → APPROVED → DISPATCHED → COMPLETED
                   SUBMITTED/APPROVED → CANCELLED

Spec ref: specs/006-purchase-management/spec.md §18 Vendor Returns
Tasks: T169, T170
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

# ---------------------------------------------------------------------------
# VendorReturn  (T169)
# ---------------------------------------------------------------------------

RMA_STATUSES = (
    "DRAFT",
    "SUBMITTED",
    "APPROVED",
    "DISPATCHED",
    "COMPLETED",
    "CANCELLED",
)


class VendorReturn(TenantBaseModel):
    """RMA (Return Merchandise Authorisation) aggregate root.

    Lifecycle:
      DRAFT → SUBMITTED → APPROVED → DISPATCHED → COMPLETED
      SUBMITTED/APPROVED → CANCELLED

    Invariants:
      - rma_number is unique per company (auto-generated RMA-YYYY-NNNNNN)
      - RMA must reference a CONFIRMED GoodsReceipt
      - Return quantity per line ≤ accepted quantity on referenced GR line
      - Dispatch is atomic: status + Epic 5 stock deduction in one transaction
      - COMPLETED sets credit_note_pending = True
    """

    __tablename__ = "vendor_returns"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','DISPATCHED','COMPLETED','CANCELLED')",
            name="ck_vendor_returns_status",
        ),
        UniqueConstraint(
            "company_id", "rma_number", name="uq_vendor_returns_company_number"
        ),
        # ix_vendor_returns_company_id is auto-created by TenantBaseModel (index=True on company_id)
        Index("ix_vendor_returns_gr_id", "gr_id"),
        Index("ix_vendor_returns_status", "status"),
        Index("ix_vendor_returns_supplier_id", "supplier_id"),
        {"comment": "Vendor Return (RMA) documents — return of goods to supplier"},
    )

    rma_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Auto-generated RMA document number e.g. RMA-2026-000001",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="DRAFT",
        doc="Lifecycle status: DRAFT | SUBMITTED | APPROVED | DISPATCHED | COMPLETED | CANCELLED",
    )

    gr_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to GoodsReceipt — must be CONFIRMED",
    )

    supplier_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Supplier (denormalised from GR for fast querying)",
    )

    initiated_by: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to User who initiated the return",
    )

    reason_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to PurchaseReasonCode — overall return reason",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Internal notes for this RMA",
    )

    replacement_po_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="Optional FK to replacement PurchaseOrder",
    )

    credit_note_pending: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Set to True when RMA is COMPLETED — alerts finance a credit note is expected",
    )

    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when goods were dispatched back to supplier",
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when RMA was completed",
    )


# ---------------------------------------------------------------------------
# ReturnLine  (T170)
# ---------------------------------------------------------------------------


class ReturnLine(TenantBaseModel):
    """Individual return line item on a Vendor Return.

    Invariants:
      - quantity_returned ≥ 0
      - quantity_returned ≤ (gr_line.quantity_received − gr_line.quantity_rejected)
    """

    __tablename__ = "return_lines"
    __table_args__ = (
        CheckConstraint(
            "quantity_returned >= 0",
            name="ck_return_lines_quantity_non_negative",
        ),
        Index("ix_return_lines_return_id", "return_id"),
        Index("ix_return_lines_gr_line_id", "gr_line_id"),
        {"comment": "Vendor return line items"},
    )

    return_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to VendorReturn",
    )

    gr_line_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to GRLine being returned",
    )

    product_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to product (denormalised from GR line for fast querying)",
    )

    quantity_returned: Mapped[object] = mapped_column(
        # Numeric(15, 3) — same precision as GRLine
        __import__("sqlalchemy").Numeric(15, 3),
        nullable=False,
        server_default="0.000",
        doc="Quantity being returned to supplier",
    )

    reason_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to PurchaseReasonCode — line-level return reason",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Notes for this return line",
    )

"""Purchase Cost Entry ORM model — Phase 8.

PurchaseCostEntry is an immutable cost snapshot created automatically on GR
confirmation. It records the financial summary of a goods receipt so that
cost data is always available regardless of subsequent changes to the GR.

Invariants:
  - One PurchaseCostEntry per GoodsReceipt (gr_id unique per company)
  - Immutable after creation — no update endpoint exposed
  - invoice_id reserved for Epic 8 AP integration

Spec ref: specs/006-purchase-management/spec.md §19 Purchase Costing
Tasks: T189
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class PurchaseCostEntry(TenantBaseModel):
    """Immutable cost snapshot created on GR confirmation.

    Captures the full financial summary of a goods receipt at the moment it
    was confirmed. Used by Finance for cost analysis, PPV tracking and future
    AP matching.
    """

    __tablename__ = "purchase_cost_entries"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "gr_id",
            name="uq_purchase_cost_entries_company_gr",
        ),
        CheckConstraint(
            "subtotal >= 0",
            name="ck_purchase_cost_entries_subtotal_non_negative",
        ),
        CheckConstraint(
            "total_charges >= 0",
            name="ck_purchase_cost_entries_charges_non_negative",
        ),
        CheckConstraint(
            "total_discounts >= 0",
            name="ck_purchase_cost_entries_discounts_non_negative",
        ),
        CheckConstraint(
            "tax_amount >= 0",
            name="ck_purchase_cost_entries_tax_non_negative",
        ),
        Index("ix_purchase_cost_entries_po_id", "po_id"),
        Index("ix_purchase_cost_entries_supplier_id", "supplier_id"),
        {"comment": "Immutable cost snapshots created on GR confirmation"},
    )

    # References
    gr_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to GoodsReceipt — unique per company (one cost entry per GR)",
    )

    po_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to PurchaseOrder",
    )

    supplier_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Supplier — denormalised for reporting",
    )

    cost_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        doc="Date of GR confirmation (cost recognition date)",
    )

    # Financial summary (copied from PO with actual GR values)
    subtotal: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0.00",
        doc="Sum of (gr_line.unit_cost × quantity_received) for all lines",
    )

    total_charges: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0.00",
        doc="Sum of PO additional charges allocated to this GR",
    )

    total_discounts: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0.00",
        doc="Sum of header-level discount amounts allocated to this GR",
    )

    tax_amount: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0.00",
        doc="Tax amount captured from PO (not computed — future AP scope)",
    )

    total: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0.00",
        doc="Total = subtotal + total_charges − total_discounts + tax_amount",
    )

    # AP integration hooks (reserved for Epic 8)
    credit_note_pending: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="True if a vendor return credit note is pending against this GR",
    )

    invoice_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to AP Invoice — reserved for Epic 8 Accounts Payable",
    )

    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default="USD",
        doc="ISO 4217 currency code from PO",
    )

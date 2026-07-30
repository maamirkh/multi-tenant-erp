"""Purchase Order ORM models — Phase 5.

Phase 5 entities:
  PurchaseOrder       — supplier commitment document (full model, replaces Phase 4 stub)
  POLine              — individual line items on a purchase order
  POAdditionalCharge  — header-level freight/handling/insurance charges
  POAmendment         — immutable amendment audit records

The Phase 4 migration (019) created a minimal purchase_orders stub.
Migration 020 ALTERs that table to add all remaining columns and creates
the three new tables.

All FK columns use PG_UUID(as_uuid=False) (string hex FK pattern).
company_id / id use Uuid(as_uuid=True) via TenantBaseModel.

Spec ref: specs/006-purchase-management/data-model.md §Purchase Order Aggregate
Tasks: T120, T121, T122
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

# ---------------------------------------------------------------------------
# PurchaseOrder  (T120)
# ---------------------------------------------------------------------------

PO_STATUSES = (
    "DRAFT",
    "PENDING_APPROVAL",
    "APPROVED",
    "REJECTED",
    "PARTIALLY_RECEIVED",
    "FULLY_RECEIVED",
    "CLOSED",
    "CANCELLED",
)

CHARGE_TYPES = ("FREIGHT", "HANDLING", "INSURANCE", "OTHER")
AMENDMENT_STATUSES = ("PENDING", "APPROVED", "REJECTED")


class PurchaseOrder(TenantBaseModel):
    """Supplier commitment document.

    Lifecycle:
      DRAFT → PENDING_APPROVAL → APPROVED → PARTIALLY_RECEIVED → FULLY_RECEIVED → CLOSED
      PENDING_APPROVAL → REJECTED → DRAFT  (revise and resubmit)
      DRAFT / PENDING_APPROVAL / APPROVED → CANCELLED

    Invariants:
      - po_number is unique per company
      - APPROVED+ status: immutable direct edits; amendment workflow required
      - Supplier must be ACTIVE at submission
      - Credit limit evaluated at approval time
    """

    __tablename__ = "purchase_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','REJECTED',"
            "'PARTIALLY_RECEIVED','FULLY_RECEIVED','CLOSED','CANCELLED')",
            name="ck_purchase_orders_status",
        ),
        UniqueConstraint(
            "company_id", "po_number", name="uq_purchase_orders_company_number"
        ),
        Index("ix_purchase_orders_supplier_id", "supplier_id"),
        Index("ix_purchase_orders_status", "status"),
        {"comment": "Purchase order documents — supplier commitments"},
    )

    po_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Auto-generated document number e.g. PO-2026-000001",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default="DRAFT",
        doc="Lifecycle status",
    )

    supplier_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to Supplier — must be set before submission",
    )

    purchase_request_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to originating PurchaseRequest (null for direct POs)",
    )

    payment_terms_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to PaymentTerms",
    )

    delivery_address_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to SupplierAddress — reserved for future use",
    )

    expected_delivery_date: Mapped[date | None] = mapped_column(
        "expected_delivery_date",
        __import__("sqlalchemy").Date(),
        nullable=True,
        doc="Expected delivery date",
    )

    supplier_reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Supplier's own reference / order number",
    )

    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default="USD",
        doc="ISO 4217 currency code",
    )

    exchange_rate: Mapped[object] = mapped_column(
        Numeric(15, 6),
        nullable=True,
        doc="Exchange rate to company base currency — reserved for Epic 10",
    )

    subtotal: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0.00",
        doc="Sum of all POLine.line_total values",
    )

    total_charges: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0.00",
        doc="Sum of all POAdditionalCharge.amount values",
    )

    total_discounts: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0.00",
        doc="Sum of all header-level discount amounts",
    )

    tax_amount: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0.00",
        doc="Tax amount (captured, not computed)",
    )

    total: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0.00",
        doc="Total = subtotal + total_charges − total_discounts + tax_amount",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Internal notes visible to purchase team",
    )

    branch_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="Reserved for future multi-branch support",
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        doc="Optimistic lock version — incremented on each update",
    )

    reason_code_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to PurchaseReasonCode used for cancellation",
    )


# ---------------------------------------------------------------------------
# POLine  (T121)
# ---------------------------------------------------------------------------


class POLine(TenantBaseModel):
    """Individual line item on a purchase order.

    Invariants:
      - quantity_ordered must be > 0
      - unit_cost must be >= 0
      - line_total = (unit_cost × quantity_ordered) − line_discount_amount
      - open_quantity = quantity_ordered − quantity_received (maintained by service)
      - line_number is unique per PO
    """

    __tablename__ = "po_lines"
    __table_args__ = (
        CheckConstraint(
            "quantity_ordered > 0",
            name="ck_po_lines_quantity_ordered_positive",
        ),
        CheckConstraint(
            "unit_cost >= 0",
            name="ck_po_lines_unit_cost_non_negative",
        ),
        UniqueConstraint("po_id", "line_number", name="uq_po_lines_po_line"),
        Index("ix_po_lines_po_id", "po_id"),
        {"comment": "Purchase order line items"},
    )

    po_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to PurchaseOrder",
    )

    pr_line_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to originating PRLine (null for lines not from PR conversion)",
    )

    line_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="1-based sequential line number within the PO",
    )

    product_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to Epic 5 product catalog (optional — free-text description allowed)",
    )

    product_description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Free-text description of the goods or services ordered",
    )

    quantity_ordered: Mapped[object] = mapped_column(
        Numeric(15, 3),
        nullable=False,
        doc="Quantity ordered — must be > 0",
    )

    quantity_received: Mapped[object] = mapped_column(
        Numeric(15, 3),
        nullable=False,
        server_default="0.000",
        doc="Total quantity received via confirmed GRs",
    )

    quantity_rejected: Mapped[object] = mapped_column(
        Numeric(15, 3),
        nullable=False,
        server_default="0.000",
        doc="Total quantity rejected at goods receipt",
    )

    open_quantity: Mapped[object] = mapped_column(
        Numeric(15, 3),
        nullable=False,
        server_default="0.000",
        doc="Remaining quantity to receive = ordered − received (maintained by GRService)",
    )

    uom_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to unit of measure (Epic 5) — optional",
    )

    unit_cost: Mapped[object] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        server_default="0.0000",
        doc="Negotiated cost per unit — must be >= 0",
    )

    line_discount_percent: Mapped[object] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Line-level discount percentage",
    )

    line_discount_amount: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Line-level discount amount (takes precedence over percent if both set)",
    )

    line_total: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0.00",
        doc="Computed: (unit_cost × quantity_ordered) − line_discount_amount",
    )

    tax_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Tax code — tax readiness",
    )

    tax_rate: Mapped[object] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Tax rate — tax readiness",
    )

    tax_amount: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Line tax amount — captured not computed",
    )

    tax_inclusive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Whether unit_cost is tax-inclusive",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Line-level notes",
    )


# ---------------------------------------------------------------------------
# POAdditionalCharge  (T122)
# ---------------------------------------------------------------------------


class POAdditionalCharge(TenantBaseModel):
    """Header-level additional charge on a purchase order.

    Examples: freight, handling, insurance, other.
    """

    __tablename__ = "po_additional_charges"
    __table_args__ = (
        CheckConstraint(
            "charge_type IN ('FREIGHT','HANDLING','INSURANCE','OTHER')",
            name="ck_po_charges_charge_type",
        ),
        CheckConstraint(
            "amount >= 0",
            name="ck_po_charges_amount_non_negative",
        ),
        Index("ix_po_additional_charges_po_id", "po_id"),
        {"comment": "Additional header charges on purchase orders"},
    )

    po_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to PurchaseOrder",
    )

    charge_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Type of charge: FREIGHT / HANDLING / INSURANCE / OTHER",
    )

    description: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Description of this charge",
    )

    amount: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0.00",
        doc="Charge amount — must be >= 0",
    )


# ---------------------------------------------------------------------------
# POAmendment  (T122)
# ---------------------------------------------------------------------------


class POAmendment(TenantBaseModel):
    """Immutable record of each amendment applied to a PurchaseOrder.

    Created whenever an APPROVED+ PO is amended. The amendment record captures
    the before/after diff and the amendment's approval status.

    Invariants:
      - amendment_number is sequential per PO (auto-assigned by service)
      - reason is required
      - Once created, no fields may be updated (immutable audit record)
    """

    __tablename__ = "po_amendments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED')",
            name="ck_po_amendments_status",
        ),
        Index("ix_po_amendments_po_id", "po_id"),
        {"comment": "Amendment audit records for approved purchase orders"},
    )

    po_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to PurchaseOrder",
    )

    amendment_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Sequential amendment number per PO (1, 2, 3...)",
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Justification for this amendment — required",
    )

    change_summary: Mapped[object] = mapped_column(
        JSON,
        nullable=True,
        doc="Before/after diff of changed fields as JSON",
    )

    requested_by: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to user who requested this amendment",
    )

    approved_by: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to user who approved this amendment",
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when amendment was approved",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="PENDING",
        doc="Amendment status: PENDING / APPROVED / REJECTED",
    )

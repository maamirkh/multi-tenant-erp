"""Delivery Note aggregate ORM models — Phase 5.

Phase 5 entities:
  DeliveryNote     — aggregate root; records physical dispatch of goods
  DeliveryNoteLine — individual line items referencing SalesOrder lines

State Machine (DeliveryNote.status):
  DRAFT → DISPATCHED | CANCELLED
  DISPATCHED → DELIVERED
  DELIVERED → (terminal)
  CANCELLED → (terminal)

Spec ref: specs/007-sales-management/data-model.md §Delivery Note Aggregate
Task: T135, T136
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
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
# Valid enum values
# ---------------------------------------------------------------------------

_DN_STATUSES = "('DRAFT', 'DISPATCHED', 'DELIVERED', 'CANCELLED')"


# ---------------------------------------------------------------------------
# DeliveryNote — aggregate root
# ---------------------------------------------------------------------------


class DeliveryNote(TenantBaseModel):
    """Delivery Note aggregate root.

    Records the physical dispatch of goods against an approved Sales Order.
    Triggering inventory deduction via Epic 5 on DISPATCHED transition.

    Invariants (enforced at service layer):
      - delivery_number is unique per company and auto-generated.
      - Only APPROVED or PARTIALLY_DELIVERED orders can have a DN created.
      - DISPATCHED DeliveryNotes are immutable.
      - Sum of dispatched quantities must not exceed ordered quantities.

    Spec ref: specs/007-sales-management/data-model.md §DeliveryNote
    """

    __tablename__ = "delivery_notes"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "delivery_number",
            name="uq_delivery_notes_company_number",
        ),
        Index("ix_delivery_notes_company_order", "company_id", "order_id"),
        Index("ix_delivery_notes_company_status", "company_id", "status"),
        CheckConstraint(
            f"status IN {_DN_STATUSES}",
            name="ck_delivery_notes_status",
        ),
        CheckConstraint("version >= 1", name="ck_delivery_notes_version"),
        {"comment": "Delivery Note aggregate root — physical dispatch record"},
    )

    # ---- Document Identity ----

    delivery_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Auto-generated delivery number (unique per company)",
    )

    # ---- Order Reference ----

    order_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to SalesOrder aggregate root",
    )

    # ---- Customer Reference ----

    customer_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Customer aggregate root (denormalised for query efficiency)",
    )

    # ---- Address ----

    shipping_address_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to CustomerAddress (shipping); nullable — may default from order",
    )

    # ---- Dates ----

    dispatch_date: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="Actual dispatch date (ISO 8601: YYYY-MM-DD); set on DISPATCHED transition",
    )

    expected_delivery_date: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="Expected delivery date (ISO 8601: YYYY-MM-DD); nullable",
    )

    # ---- Carrier / Tracking ----

    carrier: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        doc="Carrier / courier name",
    )

    tracking_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Carrier tracking number",
    )

    # ---- State Machine ----

    status: Mapped[str] = mapped_column(
        String(15),
        nullable=False,
        server_default="DRAFT",
        doc="Current DN status per state machine: DRAFT → DISPATCHED → DELIVERED / CANCELLED",
    )

    # ---- Package / Weight ----

    total_packages: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Total number of packages dispatched",
    )

    total_weight: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3),
        nullable=True,
        doc="Total weight of shipment (in kg or configured unit)",
    )

    # ---- Dispatch Actor ----

    dispatched_by: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to User who dispatched; set on DISPATCHED transition",
    )

    # ---- Notes ----

    internal_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Internal notes (not visible to customer)",
    )

    # ---- Optimistic Locking ----

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        doc="Optimistic concurrency version counter",
    )


# ---------------------------------------------------------------------------
# DeliveryNoteLine
# ---------------------------------------------------------------------------


class DeliveryNoteLine(TenantBaseModel):
    """A single line item within a Delivery Note.

    References an OrderLine and records the quantity dispatched.
    The sum of quantity_dispatched across all DNs for an order line
    must not exceed quantity_ordered.

    Spec ref: specs/007-sales-management/data-model.md §DeliveryNoteLine
    """

    __tablename__ = "delivery_note_lines"
    __table_args__ = (
        Index(
            "ix_delivery_note_lines_dn",
            "company_id",
            "delivery_note_id",
        ),
        Index(
            "ix_delivery_note_lines_order_line",
            "company_id",
            "order_line_id",
        ),
        CheckConstraint(
            "quantity_dispatched > 0",
            name="ck_dn_lines_quantity_positive",
        ),
        {"comment": "Delivery Note line — quantity dispatched per order line"},
    )

    # ---- Parent Reference ----

    delivery_note_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to DeliveryNote aggregate root",
    )

    # ---- Order Line Reference ----

    order_line_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to OrderLine being fulfilled",
    )

    # ---- Product Reference (denormalised for inventory integration) ----

    product_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to Epic 5 Product; nullable (service/non-inventory items)",
    )

    # ---- Description ----

    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Line description (copied from order line)",
    )

    # ---- Quantity ----

    quantity_dispatched: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        doc="Quantity dispatched on this delivery note line",
    )

    unit_of_measure: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Unit of measure (EA, KG, L, etc.)",
    )

    # ---- Notes ----

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Line-level notes",
    )

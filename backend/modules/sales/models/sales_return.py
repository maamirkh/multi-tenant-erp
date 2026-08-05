"""Sales Return aggregate ORM models — Phase 7.

Phase 7 entities:
  SalesReturn  — aggregate root; RMA document for returning goods from customer
  ReturnLine   — individual line items with condition tracking and qty accepted/rejected

State Machine (SalesReturn.status):
  DRAFT → PENDING_APPROVAL | CANCELLED
  PENDING_APPROVAL → APPROVED | REJECTED | CANCELLED
  APPROVED → RECEIVED
  RECEIVED → COMPLETED  (skip INSPECTED for current phase)
  COMPLETED → (terminal)
  REJECTED  → (terminal)
  CANCELLED → (terminal)

Resolution types: CREDIT_NOTE | REPLACEMENT | REFUND_READINESS
Item conditions:  NEW | USED | DAMAGED | DEFECTIVE

Spec ref: specs/007-sales-management/data-model.md §SalesReturn
Task: T184, T185
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

_RETURN_STATUSES = (
    "('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', "
    "'RECEIVED', 'INSPECTED', 'COMPLETED', 'CANCELLED')"
)
_RESOLUTION_TYPES = "('CREDIT_NOTE', 'REPLACEMENT', 'REFUND_READINESS')"
_ITEM_CONDITIONS = "('NEW', 'USED', 'DAMAGED', 'DEFECTIVE')"


# ---------------------------------------------------------------------------
# SalesReturn — aggregate root
# ---------------------------------------------------------------------------


class SalesReturn(TenantBaseModel):
    """Sales Return aggregate root (RMA).

    Records a customer's request to return goods, the approval workflow,
    receipt of returned items, and resolution (credit note / replacement / refund).

    Invariants (enforced at service layer):
      - return_number is unique per company and auto-generated (SR-YYYY-NNNNNN).
      - reason_code_id is required.
      - Return quantities per line must not exceed delivered quantities.
      - Only DRAFT/PENDING_APPROVAL returns can be cancelled.

    Spec ref: specs/007-sales-management/data-model.md §SalesReturn
    """

    __tablename__ = "sales_returns"
    __table_args__ = (
        CheckConstraint(
            f"status IN {_RETURN_STATUSES}",
            name="ck_sales_returns_status",
        ),
        CheckConstraint(
            f"resolution_type IN {_RESOLUTION_TYPES}",
            name="ck_sales_returns_resolution_type",
        ),
        UniqueConstraint(
            "company_id", "return_number", name="uq_sales_returns_company_number"
        ),
        # ix_sales_returns_company_id is auto-created by TenantBaseModel (index=True on company_id)
        Index("ix_sales_returns_customer_id", "customer_id"),
        Index("ix_sales_returns_status", "status"),
        Index("ix_sales_returns_company_status", "company_id", "status"),
        Index("ix_sales_returns_order_id", "order_id"),
    )

    # ---- Identification ----
    return_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Auto-generated return number, e.g. SR-2026-000001",
    )

    # ---- References ----
    customer_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="Customer who is returning goods",
    )
    order_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="Original Sales Order (optional)",
    )
    invoice_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="Original Invoice (optional)",
    )
    replacement_order_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="Replacement SO created when resolution_type=REPLACEMENT",
    )

    # ---- Return Details ----
    return_date: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Return date in ISO 8601 format (YYYY-MM-DD)",
    )
    reason_code_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK SalesReasonCode — required",
    )
    reason_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Free-text description of return reason",
    )
    resolution_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="CREDIT_NOTE",
        doc="Resolution type: CREDIT_NOTE | REPLACEMENT | REFUND_READINESS",
    )

    # ---- Status & Workflow ----
    status: Mapped[str] = mapped_column(
        String(25),
        nullable=False,
        default="DRAFT",
        doc="Return lifecycle status",
    )
    approval_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        doc="Incremented on each submission to invalidate stale approval records",
    )

    # ---- Receipt ----
    received_by: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="User/warehouse staff who received the returned goods",
    )
    received_at: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        doc="ISO 8601 datetime when goods were received",
    )

    # ---- Financial ----
    credit_note_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Credit note amount (when resolution_type=CREDIT_NOTE)",
    )

    # ---- Notes ----
    internal_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ---- Optimistic Locking ----
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        doc="Optimistic lock version",
    )


# ---------------------------------------------------------------------------
# ReturnLine
# ---------------------------------------------------------------------------


class ReturnLine(TenantBaseModel):
    """Individual line item on a Sales Return.

    Tracks quantity returned, accepted, and rejected per product.
    Condition field enables quality inspection tracking.

    Spec ref: specs/007-sales-management/data-model.md §ReturnLine
    """

    __tablename__ = "sales_return_lines"
    __table_args__ = (
        CheckConstraint(
            "quantity_returned > 0", name="ck_sales_return_lines_qty_returned_positive"
        ),
        CheckConstraint(
            "quantity_accepted >= 0", name="ck_sales_return_lines_qty_accepted_nonneg"
        ),
        CheckConstraint(
            "quantity_rejected >= 0", name="ck_sales_return_lines_qty_rejected_nonneg"
        ),
        CheckConstraint(
            f"condition IN {_ITEM_CONDITIONS}",
            name="ck_sales_return_lines_condition",
        ),
        Index("ix_sales_return_lines_return_id", "return_id"),
        Index("ix_sales_return_lines_product_id", "product_id"),
    )

    # ---- References ----
    return_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK SalesReturn",
    )
    product_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
    )
    reason_code_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="Optional per-line reason code (overrides header reason)",
    )

    # ---- Item Details ----
    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    quantity_returned: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        doc="Quantity the customer is returning",
    )
    quantity_accepted: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        default=Decimal("0"),
        doc="Quantity accepted after inspection",
    )
    quantity_rejected: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        default=Decimal("0"),
        doc="Quantity rejected after inspection",
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        doc="Unit price from original document",
    )
    extended_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        doc="quantity_returned × unit_price",
    )
    condition: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="USED",
        doc="Item condition: NEW | USED | DAMAGED | DEFECTIVE",
    )

"""Sales Order aggregate ORM models — Phase 4.

Phase 4 entities:
  SalesOrder  — aggregate root; order header with state machine
  OrderLine   — individual line items with pricing and delivery tracking

State Machine (SalesOrder.status):
  DRAFT → PENDING_APPROVAL | CANCELLED
  PENDING_APPROVAL → APPROVED | REJECTED
  APPROVED → PARTIALLY_DELIVERED | DELIVERED | CANCELLED
  REJECTED → DRAFT (revision)
  PARTIALLY_DELIVERED → DELIVERED
  DELIVERED → INVOICED
  INVOICED → CLOSED
  CLOSED → (terminal)
  CANCELLED → (terminal)

Spec ref: specs/007-sales-management/data-model.md §Sales Order Aggregate
Task: T105, T106
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

_ORDER_STATUSES = (
    "('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', "
    "'PARTIALLY_DELIVERED', 'DELIVERED', 'INVOICED', 'CLOSED', 'CANCELLED')"
)
_ORDER_PRIORITIES = "('LOW', 'NORMAL', 'HIGH', 'URGENT')"
_DISCOUNT_TYPES = "('PERCENTAGE', 'AMOUNT')"
_DELIVERY_STATUSES = "('PENDING', 'PARTIALLY_DELIVERED', 'DELIVERED')"
_PRICE_SOURCES = (
    "('MANUAL', 'CUSTOMER_SPECIFIC', 'GROUP', 'CATEGORY', "
    "'PRICE_LIST', 'DEFAULT_LIST', 'BASE_PRICE')"
)


# ---------------------------------------------------------------------------
# SalesOrder — aggregate root
# ---------------------------------------------------------------------------


class SalesOrder(TenantBaseModel):
    """Sales Order aggregate root.

    Represents a confirmed sales commitment from a customer. Orders follow a
    state machine from DRAFT through approval, delivery, invoicing, and closure.
    Orders in PENDING_APPROVAL are immutable until approved or rejected.

    Invariants (enforced at service layer):
      - order_number is unique per company and auto-generated.
      - PENDING_APPROVAL orders cannot be edited.
      - cancellation_reason is required when transitioning to CANCELLED.
      - approval_version increments on each resubmission after REJECTED.

    Spec ref: specs/007-sales-management/data-model.md §SalesOrder
    """

    __tablename__ = "sales_orders"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "order_number",
            name="uq_sales_orders_company_number",
        ),
        Index(
            "ix_sales_orders_company_customer_status",
            "company_id",
            "customer_id",
            "status",
        ),
        Index("ix_sales_orders_company_status", "company_id", "status"),
        Index("ix_sales_orders_quotation", "company_id", "quotation_id"),
        CheckConstraint(
            f"status IN {_ORDER_STATUSES}",
            name="ck_sales_orders_status",
        ),
        CheckConstraint(
            f"priority IN {_ORDER_PRIORITIES}",
            name="ck_sales_orders_priority",
        ),
        CheckConstraint("subtotal >= 0", name="ck_sales_orders_subtotal"),
        CheckConstraint("total_amount >= 0", name="ck_sales_orders_total"),
        CheckConstraint(
            "approval_version >= 1", name="ck_sales_orders_approval_version"
        ),
        CheckConstraint("version >= 1", name="ck_sales_orders_version"),
        {"comment": "Sales order aggregate root"},
    )

    # ---- Document Identity ----

    order_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Auto-generated order number (unique per company)",
    )

    # ---- Customer Reference ----

    customer_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Customer aggregate root",
    )

    # ---- Quotation Reference (optional) ----

    quotation_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to SalesQuotation if converted from quotation; nullable for direct orders",
    )

    # ---- Dates ----

    order_date: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Order date (ISO 8601: YYYY-MM-DD)",
    )

    required_delivery_date: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="Required delivery date (ISO 8601: YYYY-MM-DD); nullable",
    )

    # ---- Currency / Payment ----

    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default="USD",
        doc="ISO 4217 currency code",
    )

    payment_term_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to PaymentTerm; nullable",
    )

    # ---- Addresses ----

    shipping_address_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to CustomerAddress (shipping); nullable",
    )

    billing_address_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to CustomerAddress (billing); nullable",
    )

    # ---- Sales Rep ----

    sales_rep_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to User (sales representative)",
    )

    # ---- Priority ----

    priority: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="NORMAL",
        doc="Order priority: LOW / NORMAL / HIGH / URGENT",
    )

    # ---- State Machine ----

    status: Mapped[str] = mapped_column(
        String(25),
        nullable=False,
        server_default="DRAFT",
        doc="Current order status per state machine",
    )

    # ---- Financial Totals ----

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0",
        doc="Sum of all line extended_amounts before header discounts",
    )

    discount_type: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="PERCENTAGE or AMOUNT; nullable when no header-level discount",
    )

    discount_value: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 4),
        nullable=True,
        doc="Discount value: percentage (0-100) or fixed amount",
    )

    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0",
        doc="Computed discount amount in currency",
    )

    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0",
        doc="Total tax amount",
    )

    charges_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0",
        doc="Additional charges (freight, handling, etc.)",
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0",
        doc="subtotal - discount_amount + tax_amount + charges_amount",
    )

    # ---- Notes ----

    internal_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Internal notes (not visible to customer)",
    )

    customer_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Notes visible to the customer",
    )

    # ---- Cancellation ----

    cancellation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Required when status transitions to CANCELLED",
    )

    # ---- Approval Tracking ----

    approval_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        doc="Increments on each resubmission after REJECTED",
    )

    # ---- Optimistic Locking ----

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        doc="Optimistic concurrency version counter",
    )


# ---------------------------------------------------------------------------
# OrderLine
# ---------------------------------------------------------------------------


class OrderLine(TenantBaseModel):
    """A single line item within a Sales Order.

    Tracks ordered quantities, delivered quantities, and remaining quantities.
    delivery_status auto-updates as Delivery Notes are dispatched.

    Spec ref: specs/007-sales-management/data-model.md §OrderLine
    """

    __tablename__ = "order_lines"
    __table_args__ = (
        Index("ix_order_lines_order", "company_id", "order_id"),
        CheckConstraint("quantity_ordered > 0", name="ck_order_lines_quantity_ordered"),
        CheckConstraint(
            "quantity_delivered >= 0", name="ck_order_lines_quantity_delivered"
        ),
        CheckConstraint("unit_price >= 0", name="ck_order_lines_unit_price"),
        CheckConstraint("line_number >= 1", name="ck_order_lines_line_number"),
        CheckConstraint(
            f"delivery_status IN {_DELIVERY_STATUSES}",
            name="ck_order_lines_delivery_status",
        ),
        {"comment": "Sales order line items"},
    )

    # ---- Parent FK ----

    order_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to SalesOrder",
    )

    # ---- Line Number ----

    line_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Sequential line number within the order",
    )

    # ---- Product Reference ----

    product_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to Epic 5 Product; nullable for free-text lines",
    )

    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Line description; required even when product_id is set",
    )

    # ---- Quantities ----

    quantity_ordered: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        doc="Original ordered quantity; must be > 0",
    )

    quantity_delivered: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        server_default="0",
        doc="Total quantity delivered across all Delivery Notes",
    )

    unit_of_measure: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="EA",
        doc="Unit of measure code (EA, KG, LTR, etc.)",
    )

    # ---- Pricing ----

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        doc="Unit price at time of order",
    )

    cost_price: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 4),
        nullable=True,
        doc="Cost price from Epic 5 for margin calculation; nullable",
    )

    discount_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Line discount percentage (0-100); nullable",
    )

    discount_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Computed line discount amount; nullable",
    )

    tax_category: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Tax category code (STANDARD, ZERO, EXEMPT); nullable",
    )

    tax_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
        doc="Tax rate applied; nullable; default 0",
    )

    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0",
        doc="Line tax amount",
    )

    extended_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        doc="quantity_ordered × unit_price - discount_amount",
    )

    # ---- Delivery Tracking ----

    delivery_status: Mapped[str] = mapped_column(
        String(25),
        nullable=False,
        server_default="PENDING",
        doc="PENDING / PARTIALLY_DELIVERED / DELIVERED",
    )

    # ---- Price Source ----

    price_source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="MANUAL",
        doc="How price was resolved: MANUAL / CUSTOMER_SPECIFIC / GROUP / CATEGORY / PRICE_LIST / DEFAULT_LIST / BASE_PRICE",
    )

    # ---- Notes ----

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Line-level notes; nullable",
    )

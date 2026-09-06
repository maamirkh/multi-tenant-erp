"""Sales Quotation aggregate ORM models — Phase 3.

Phase 3 entities:
  SalesQuotation   — aggregate root; quotation header with state machine
  QuotationLine    — individual line items with pricing
  QuotationRevision — immutable revision snapshot (JSONB)

State Machine (SalesQuotation.status):
  DRAFT → SENT_TO_CUSTOMER | CANCELLED
  SENT_TO_CUSTOMER → ACCEPTED | REJECTED | EXPIRED | CANCELLED
  ACCEPTED → CONVERTED | CANCELLED
  REJECTED → (terminal)
  CONVERTED → (terminal)
  EXPIRED → (terminal)
  CANCELLED → (terminal)

Spec ref: specs/007-sales-management/data-model.md §Sales Quotation Aggregate
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

# ---------------------------------------------------------------------------
# Valid status values
# ---------------------------------------------------------------------------

_QUOTATION_STATUSES = "('DRAFT', 'SENT_TO_CUSTOMER', 'ACCEPTED', 'REJECTED', 'CONVERTED', 'EXPIRED', 'CANCELLED')"
_DISCOUNT_TYPES = "('PERCENTAGE', 'AMOUNT')"


# ---------------------------------------------------------------------------
# SalesQuotation — aggregate root
# ---------------------------------------------------------------------------


class SalesQuotation(TenantBaseModel):
    """Sales Quotation aggregate root.

    Represents a commercial offer made to a customer. Quotations follow a
    state machine from DRAFT through to CONVERTED (accepted and turned into
    a Sales Order) or one of several terminal states.

    Invariants (enforced at service layer):
      - quotation_number is unique per company and auto-generated.
      - validity_date >= quotation_date.
      - Only ACCEPTED quotations can be converted to Sales Orders.
      - revision_number increments on each change to a DRAFT quotation.

    Spec ref: specs/007-sales-management/data-model.md §SalesQuotation
    """

    __tablename__ = "sales_quotations"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "quotation_number",
            name="uq_sales_quotations_company_number",
        ),
        Index(
            "ix_sales_quotations_company_customer_status",
            "company_id",
            "customer_id",
            "status",
        ),
        Index("ix_sales_quotations_company_status", "company_id", "status"),
        CheckConstraint(
            f"status IN {_QUOTATION_STATUSES}",
            name="ck_sales_quotations_status",
        ),
        CheckConstraint("subtotal >= 0", name="ck_sales_quotations_subtotal"),
        CheckConstraint("total_amount >= 0", name="ck_sales_quotations_total"),
        CheckConstraint("revision_number >= 1", name="ck_sales_quotations_revision"),
        CheckConstraint("version >= 1", name="ck_sales_quotations_version"),
        {"comment": "Sales quotation aggregate root"},
    )

    # ---- Document Identity ----

    quotation_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Auto-generated quotation number (unique per company)",
    )

    # ---- Customer Reference ----

    customer_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Customer aggregate root",
    )

    # ---- Dates ----

    quotation_date: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Quotation date (ISO 8601: YYYY-MM-DD)",
    )

    validity_date: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Quotation validity date (ISO 8601: YYYY-MM-DD); >= quotation_date",
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
        doc="FK to SalesPaymentTerm; nullable",
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

    # ---- Revision ----

    revision_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        doc="Increments on each revision of a DRAFT quotation",
    )

    # ---- State Machine ----

    status: Mapped[str] = mapped_column(
        String(25),
        nullable=False,
        server_default="DRAFT",
        doc="Current quotation status per state machine",
    )

    # ---- Financial Totals ----

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0",
        doc="Sum of all line extended_amounts before discounts",
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

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0",
        doc="subtotal - discount_amount + tax_amount",
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
        doc="Notes visible to the customer on the quotation document",
    )

    # ---- Conversion Reference ----

    converted_order_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to SalesOrder; populated on ACCEPTED → CONVERTED transition",
    )

    # ---- Optimistic Locking ----

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        doc="Optimistic concurrency version counter",
    )


# ---------------------------------------------------------------------------
# QuotationLine
# ---------------------------------------------------------------------------


class QuotationLine(TenantBaseModel):
    """A single line item within a Sales Quotation.

    Each line references a product (optional for free-text lines) and
    stores pricing with optional line-level discount.

    Spec ref: specs/007-sales-management/data-model.md §QuotationLine
    """

    __tablename__ = "quotation_lines"
    __table_args__ = (
        Index("ix_quotation_lines_quotation", "company_id", "quotation_id"),
        CheckConstraint("quantity > 0", name="ck_quotation_lines_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_quotation_lines_unit_price"),
        CheckConstraint("line_number >= 1", name="ck_quotation_lines_line_number"),
        {"comment": "Sales quotation line items"},
    )

    # ---- Parent FK ----

    quotation_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to SalesQuotation",
    )

    # ---- Line Number ----

    line_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Sequential line number within the quotation",
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

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        doc="Ordered quantity; must be > 0",
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
        doc="Unit price; resolved via PricingService 7-level hierarchy",
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
        doc="Tax category code (e.g. STANDARD, ZERO, EXEMPT); nullable",
    )

    extended_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        doc="quantity × unit_price - discount_amount",
    )

    # ---- Notes ----

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Line-level notes; nullable",
    )


# ---------------------------------------------------------------------------
# QuotationRevision
# ---------------------------------------------------------------------------


class QuotationRevision(TenantBaseModel):
    """Immutable revision snapshot for a Sales Quotation.

    Captured whenever the quotation is revised. Stores a complete JSONB
    snapshot of the quotation header and all lines at the time of revision.

    Spec ref: specs/007-sales-management/data-model.md §QuotationRevision
    """

    __tablename__ = "quotation_revisions"
    __table_args__ = (
        Index("ix_quotation_revisions_quotation", "company_id", "quotation_id"),
        CheckConstraint(
            "revision_number >= 1",
            name="ck_quotation_revisions_revision_number",
        ),
        {"comment": "Immutable revision history snapshots for quotations"},
    )

    # ---- Parent FK ----

    quotation_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to SalesQuotation",
    )

    # ---- Revision Number ----

    revision_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Revision number at time of snapshot",
    )

    # ---- Snapshot ----

    snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        doc="Full quotation + lines snapshot as JSONB at revision time",
    )

    # ---- Modification Metadata ----

    modified_by: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to User who created this revision",
    )

    modified_at: Mapped[str] = mapped_column(
        # Genuine defect found live during pre-Epic-9 hardening audit
        # (2026-08-14): String(30) is too short for utcnow().isoformat()'s
        # actual output (32 chars with microseconds + UTC offset, e.g.
        # "2026-08-15T07:57:23.605415+00:00"), causing a real Postgres
        # StringDataRightTruncation error on every quotation creation.
        # Invisible to the SQLite test suite (SQLite doesn't enforce
        # VARCHAR length limits). Widened with margin.
        String(40),
        nullable=False,
        doc="ISO 8601 datetime when revision was captured",
    )

    change_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Human-readable description of what changed in this revision",
    )

"""Sales Invoice aggregate ORM models — Phase 6.

Phase 6 entities:
  SalesInvoice  — aggregate root; financial document requesting payment
  InvoiceLine   — individual line items linked to order/delivery lines
  InvoiceCharge — additional charges (freight, handling, etc.)

State Machine (SalesInvoice.status):
  DRAFT → ISSUED | CANCELLED
  ISSUED → PAID (future) | CREDIT_NOTE_ISSUED
  PAID → (terminal)
  CANCELLED → (terminal)
  CREDIT_NOTE_ISSUED → (terminal)

Invariants:
  - invoice_number is unique per company, gap-free, auto-generated.
  - ISSUED invoices are immutable.
  - Cancelled invoices retain their number (void, no reuse).

Spec ref: specs/007-sales-management/data-model.md §Sales Invoice Aggregate
Task: T158, T159, T160
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    Boolean,
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
# Valid enum values (enforced via CheckConstraint)
# ---------------------------------------------------------------------------

_INVOICE_STATUSES = "('DRAFT', 'ISSUED', 'PAID', 'CANCELLED', 'CREDIT_NOTE_ISSUED')"
_CHARGE_TYPES = "('FREIGHT', 'HANDLING', 'INSURANCE', 'OTHER')"


# ---------------------------------------------------------------------------
# SalesInvoice — aggregate root
# ---------------------------------------------------------------------------


class SalesInvoice(TenantBaseModel):
    """Sales Invoice aggregate root.

    Represents a financial document requesting payment from the customer.
    Invoice numbers are strictly sequential and gap-free per company.
    ISSUED invoices are immutable; correction is via credit notes.

    Spec ref: specs/007-sales-management/data-model.md §SalesInvoice
    """

    __tablename__ = "sales_invoices"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "invoice_number",
            name="uq_sales_invoices_company_number",
        ),
        CheckConstraint(
            f"status IN {_INVOICE_STATUSES}",
            name="ck_sales_invoices_status",
        ),
        Index("ix_sales_invoices_company_status", "company_id", "status"),
        Index(
            "ix_sales_invoices_company_customer_status",
            "company_id",
            "customer_id",
            "status",
        ),
        Index("ix_sales_invoices_company_order", "company_id", "order_id"),
        {"schema": None},
    )

    # ---- Identification -------------------------------------------------------
    invoice_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Auto-generated, gap-free sequential number per company (SI-YYYY-NNNNNN).",
    )

    # ---- References -----------------------------------------------------------
    customer_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        index=True,
        doc="FK Customer aggregate root.",
    )
    order_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK SalesOrder; nullable for manual/direct invoices.",
    )
    delivery_note_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK DeliveryNote; nullable for direct/order-based invoicing.",
    )
    payment_term_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK SalesPaymentTerm; drives due date calculation.",
    )
    billing_address_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK CustomerAddress; billing address for this invoice.",
    )

    # ---- Dates ----------------------------------------------------------------
    invoice_date: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Invoice date (ISO 8601: YYYY-MM-DD).",
    )
    due_date: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Payment due date (calculated from payment terms).",
    )

    # ---- Currency -------------------------------------------------------------
    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        doc="ISO 4217 currency code (e.g. USD, EUR, GBP).",
    )

    # ---- State ----------------------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(25),
        nullable=False,
        default="DRAFT",
        server_default="DRAFT",
        doc="Invoice status (DRAFT / ISSUED / PAID / CANCELLED / CREDIT_NOTE_ISSUED).",
    )

    # ---- Amounts --------------------------------------------------------------
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        doc="Sum of all line extended amounts before charges.",
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        doc="Total discount across all lines.",
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        doc="Total tax amount (future: tax engine hook).",
    )
    charges_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        doc="Total of all additional charges (freight, handling, etc.).",
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        doc="Grand total: subtotal - discount + tax + charges.",
    )

    # ---- Credit note ----------------------------------------------------------
    credit_note_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Credit note amount when status = CREDIT_NOTE_ISSUED.",
    )

    # ---- Display fields -------------------------------------------------------
    amount_in_words: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Auto-generated textual representation of total_amount.",
    )
    internal_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Internal notes not visible to customer.",
    )
    customer_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Notes visible to the customer on the invoice document.",
    )

    # ---- Versioning -----------------------------------------------------------
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        doc="Optimistic locking version counter.",
    )


# ---------------------------------------------------------------------------
# InvoiceLine — owned entity
# ---------------------------------------------------------------------------


class InvoiceLine(TenantBaseModel):
    """Invoice line item owned by SalesInvoice.

    Each line represents a product or service being billed. Lines link back
    to the originating OrderLine or DeliveryNoteLine for traceability.

    Spec ref: specs/007-sales-management/data-model.md §InvoiceLine
    """

    __tablename__ = "invoice_lines"
    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_invoice_lines_quantity_positive",
        ),
        Index("ix_invoice_lines_invoice", "invoice_id"),
        Index("ix_invoice_lines_order_line", "order_line_id"),
        {"schema": None},
    )

    # ---- Parent reference -----------------------------------------------------
    invoice_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        index=True,
        doc="FK SalesInvoice; owner of this line.",
    )

    # ---- Line position --------------------------------------------------------
    line_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Sequential line number within the invoice (1-based).",
    )

    # ---- Product / description ------------------------------------------------
    product_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK Inventory Product; nullable for description-only lines.",
    )
    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Line description (product name or service description).",
    )

    # ---- Quantity & pricing ---------------------------------------------------
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        doc="Quantity billed (must be > 0).",
    )
    unit_of_measure: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Unit of measure (e.g. EA, KG, HR).",
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        doc="Per-unit price before discounts.",
    )

    # ---- Discounts ------------------------------------------------------------
    discount_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Line-level percentage discount (mutually exclusive with discount_amount).",
    )
    discount_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Line-level fixed discount (mutually exclusive with discount_percentage).",
    )

    # ---- Tax ------------------------------------------------------------------
    tax_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
        default=Decimal("0"),
        doc="Tax rate as a decimal fraction (e.g. 0.15 = 15%). Future tax engine hook.",
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        doc="Calculated tax amount for this line.",
    )

    # ---- Total ----------------------------------------------------------------
    extended_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        doc="Net amount: (quantity * unit_price) - discount, before tax.",
    )

    # ---- Source references ----------------------------------------------------
    delivery_note_line_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK DeliveryNoteLine; for delivery-based invoicing traceability.",
    )
    order_line_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK OrderLine; for order-based invoicing traceability.",
    )


# ---------------------------------------------------------------------------
# InvoiceCharge — owned entity
# ---------------------------------------------------------------------------


class InvoiceCharge(TenantBaseModel):
    """Additional charge on a sales invoice (freight, handling, etc.).

    Charges are separate from line items and represent non-product billing
    components. A tax_applicable flag enables future tax engine integration.

    Spec ref: specs/007-sales-management/data-model.md §InvoiceCharge
    """

    __tablename__ = "invoice_charges"
    __table_args__ = (
        CheckConstraint(
            f"charge_type IN {_CHARGE_TYPES}",
            name="ck_invoice_charges_type",
        ),
        CheckConstraint(
            "amount > 0",
            name="ck_invoice_charges_amount_positive",
        ),
        Index("ix_invoice_charges_invoice", "invoice_id"),
        {"schema": None},
    )

    # ---- Parent reference -----------------------------------------------------
    invoice_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        index=True,
        doc="FK SalesInvoice; owner of this charge.",
    )

    # ---- Charge details -------------------------------------------------------
    charge_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Charge category: FREIGHT / HANDLING / INSURANCE / OTHER.",
    )
    description: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        doc="Human-readable charge description.",
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        doc="Charge amount (must be > 0).",
    )
    tax_applicable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="Whether tax is applicable to this charge (future tax engine hook).",
    )

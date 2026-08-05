"""Customer aggregate ORM models — Phase 1.

Phase 1 entities:
  Customer          — aggregate root with full lifecycle state machine
  CustomerContact   — contact persons for a customer
  CustomerAddress   — billing/shipping addresses for a customer
  CustomerBankDetail — bank account details for a customer
  CustomerNote      — append-only internal notes

State Machine (enforced at service layer):
  DRAFT    → ACTIVE      (requires ≥1 contact, ≥1 billing address, payment_term set)
  ACTIVE   → ON_HOLD     (manual by Sales/Finance Manager)
  ACTIVE   → BLOCKED     (credit exceeded or manual by Finance Manager)
  ON_HOLD  → ACTIVE      (manual release)
  BLOCKED  → ACTIVE      (credit resolved + manual unblock)
  ACTIVE   → INACTIVE    (no open orders required)
  INACTIVE → ACTIVE      (manual reactivation)

Spec ref: specs/007-sales-management/data-model.md §Customer Aggregate
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
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

# ---------------------------------------------------------------------------
# Status / type constants for CHECK constraints
# ---------------------------------------------------------------------------

_CUSTOMER_STATUSES = "('DRAFT', 'ACTIVE', 'ON_HOLD', 'BLOCKED', 'INACTIVE')"
_CUSTOMER_TYPES = "('INDIVIDUAL', 'COMPANY', 'GOVERNMENT', 'INTERNAL')"
_CREDIT_STATUSES = "('GOOD', 'WARNING', 'EXCEEDED', 'HOLD')"
_RATINGS = "('A', 'B', 'C', 'D', 'F')"
_ADDRESS_TYPES = "('BILLING', 'SHIPPING', 'BOTH')"


# ---------------------------------------------------------------------------
# Customer aggregate root
# ---------------------------------------------------------------------------


class Customer(TenantBaseModel):
    """Customer aggregate root.

    Represents a customer that the company sells goods or services to.

    Status State Machine:
      DRAFT    → ACTIVE      (activation — customer qualified)
      ACTIVE   → ON_HOLD     (manual hold)
      ACTIVE   → BLOCKED     (credit exceeded or manual block)
      ON_HOLD  → ACTIVE      (hold released)
      BLOCKED  → ACTIVE      (block resolved)
      ACTIVE   → INACTIVE    (deactivated)
      INACTIVE → ACTIVE      (reactivated)

    Invariants (enforced at service layer):
      - customer_code unique per company and immutable after creation.
      - DRAFT/INACTIVE customers cannot appear on sales documents.
      - ON_HOLD/BLOCKED customers block new sales orders.
      - credit_status auto-computed from credit_used vs credit_limit.

    Spec ref: specs/007-sales-management/data-model.md §Customer
    """

    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "customer_code",
            name="uq_customers_company_code",
        ),
        Index("ix_customers_company_status", "company_id", "status"),
        Index("ix_customers_company_type", "company_id", "customer_type"),
        Index("ix_customers_tsvector", "tsvector_search", postgresql_using="gin"),
        CheckConstraint(
            f"customer_type IN {_CUSTOMER_TYPES}",
            name="ck_customers_customer_type",
        ),
        CheckConstraint(
            f"status IN {_CUSTOMER_STATUSES}",
            name="ck_customers_status",
        ),
        CheckConstraint(
            f"credit_status IN {_CREDIT_STATUSES}",
            name="ck_customers_credit_status",
        ),
        CheckConstraint(
            f"rating IS NULL OR rating IN {_RATINGS}",
            name="ck_customers_rating",
        ),
        CheckConstraint(
            "credit_limit >= 0",
            name="ck_customers_credit_limit",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_customers_version",
        ),
        {"comment": "Customer aggregate root — core customer master record"},
    )

    # ---- Identity ----

    customer_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Unique customer code per company (immutable after creation, e.g. 'CUST-0001')",
    )

    # ---- Classification ----

    customer_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="COMPANY",
        doc="INDIVIDUAL / COMPANY / GOVERNMENT / INTERNAL",
    )

    category_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to CustomerCategory — mandatory classification",
    )

    group_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to CustomerGroup — optional secondary classification",
    )

    # ---- Names ----

    legal_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Legal entity name of the customer",
    )

    trading_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        doc="Trading name / DBA name (optional)",
    )

    # ---- Status ----

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="DRAFT",
        doc="DRAFT / ACTIVE / ON_HOLD / BLOCKED / INACTIVE",
    )

    # ---- Payment & Credit ----

    payment_term_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to SalesPaymentTerm — required before activation",
    )

    credit_limit: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0",
        doc="Credit limit for this customer (0 = no credit)",
    )

    credit_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="GOOD",
        doc="GOOD / WARNING / EXCEEDED / HOLD — auto-computed from credit usage",
    )

    # ---- Rating ----

    rating: Mapped[str | None] = mapped_column(
        String(1),
        nullable=True,
        doc="Customer rating: A / B / C / D / F",
    )

    # ---- Currency & Tax ----

    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default="USD",
        doc="ISO 4217 currency code",
    )

    tax_registration_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Customer tax/VAT registration number",
    )

    tax_exempt: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Whether this customer is tax-exempt",
    )

    tax_exempt_certificate: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Tax exemption certificate reference number",
    )

    tax_exempt_expiry: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="Tax exemption expiry date (ISO 8601 date string YYYY-MM-DD)",
    )

    # ---- Business Profile ----

    website: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Customer website URL",
    )

    industry: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Customer industry classification",
    )

    annual_revenue_range: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Annual revenue range (e.g. '1M-10M')",
    )

    # ---- Custom Fields ----

    custom_fields: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Custom field values (max 20 fields, JSONB)",
    )

    # ---- Internal Notes ----

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Internal notes about this customer",
    )

    # ---- Optimistic Locking ----

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        doc="Optimistic concurrency version counter",
    )

    # ---- Full-Text Search ----

    tsvector_search: Mapped[str | None] = mapped_column(
        TSVECTOR,
        nullable=True,
        doc="PostgreSQL FTS vector for customer search (updated by service layer)",
    )


# ---------------------------------------------------------------------------
# CustomerContact
# ---------------------------------------------------------------------------


class CustomerContact(TenantBaseModel):
    """Contact person for a customer.

    Invariants (enforced at service layer):
      - Exactly one contact must have is_primary=True per customer.
      - At least one contact required before customer activation.
    """

    __tablename__ = "customer_contacts"
    __table_args__ = (
        Index("ix_customer_contacts_customer_id", "customer_id"),
        Index("ix_customer_contacts_company_customer", "company_id", "customer_id"),
        {"comment": "Customer contact persons"},
    )

    customer_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Customer (parent aggregate)",
    )

    contact_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Full contact name",
    )

    title: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Job title or salutation",
    )

    email: Mapped[str | None] = mapped_column(
        String(254),
        nullable=True,
        doc="Contact email address",
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        doc="Contact phone number",
    )

    mobile: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        doc="Contact mobile number",
    )

    department: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Department or team",
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Whether this is the primary contact for the customer",
    )

    is_billing_contact: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Whether this contact receives billing correspondence",
    )

    is_shipping_contact: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Whether this contact receives shipping correspondence",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Internal notes about this contact",
    )


# ---------------------------------------------------------------------------
# CustomerAddress
# ---------------------------------------------------------------------------


class CustomerAddress(TenantBaseModel):
    """Billing or shipping address for a customer.

    Invariants (enforced at service layer):
      - Exactly one default billing address per customer.
      - Exactly one default shipping address per customer.
      - At least one billing address required before customer activation.
    """

    __tablename__ = "customer_addresses"
    __table_args__ = (
        Index("ix_customer_addresses_customer_id", "customer_id"),
        Index("ix_customer_addresses_company_customer", "company_id", "customer_id"),
        CheckConstraint(
            f"address_type IN {_ADDRESS_TYPES}",
            name="ck_customer_addresses_type",
        ),
        {"comment": "Customer billing and shipping addresses"},
    )

    customer_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Customer (parent aggregate)",
    )

    address_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="BILLING",
        doc="BILLING / SHIPPING / BOTH",
    )

    address_label: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Human-readable label (e.g. 'Head Office', 'Warehouse')",
    )

    address_line_1: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        doc="Primary address line",
    )

    address_line_2: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
        doc="Secondary address line (suite, floor, unit…)",
    )

    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="City",
    )

    state_province: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="State / province / region",
    )

    postal_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Postal / ZIP code",
    )

    country_code: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        doc="ISO 3166-1 alpha-2 country code (e.g. 'US', 'GB')",
    )

    is_default_billing: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Whether this is the default billing address for this customer",
    )

    is_default_shipping: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Whether this is the default shipping address for this customer",
    )


# ---------------------------------------------------------------------------
# CustomerBankDetail
# ---------------------------------------------------------------------------


class CustomerBankDetail(TenantBaseModel):
    """Bank account details for a customer.

    Used for direct debit or payment reconciliation purposes.
    """

    __tablename__ = "customer_bank_details"
    __table_args__ = (
        Index("ix_customer_bank_details_customer_id", "customer_id"),
        {"comment": "Customer bank account details"},
    )

    customer_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Customer (parent aggregate)",
    )

    bank_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Name of the bank",
    )

    branch_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        doc="Branch name",
    )

    account_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Bank account number",
    )

    iban: Mapped[str | None] = mapped_column(
        String(34),
        nullable=True,
        doc="IBAN (International Bank Account Number)",
    )

    swift_bic: Mapped[str | None] = mapped_column(
        String(11),
        nullable=True,
        doc="SWIFT / BIC code",
    )

    account_holder_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Name of the account holder",
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Whether this is the default bank account for this customer",
    )


# ---------------------------------------------------------------------------
# CustomerNote
# ---------------------------------------------------------------------------


class CustomerNote(TenantBaseModel):
    """Append-only internal note for a customer.

    Invariants:
      - Notes cannot be edited after creation (append-only).
      - Notes cannot be hard-deleted; soft-delete only.
    """

    __tablename__ = "customer_notes"
    __table_args__ = (
        Index("ix_customer_notes_customer_id", "customer_id"),
        {"comment": "Append-only internal notes for customers"},
    )

    customer_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Customer (parent aggregate)",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Note content",
    )

    author_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="UUID of the user who authored this note",
    )

    author_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Display name of the author (denormalized for history)",
    )

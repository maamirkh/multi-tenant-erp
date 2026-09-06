"""Purchase master data ORM models — Phase 0 + Phase 1.

Phase 0 entities:
  SupplierCategory   — hierarchical supplier classification tree (max depth 5)
  PaymentTerms       — company payment terms master list
  PurchaseReasonCode — typed reason codes for returns, cancellations, rejections

Phase 1 entities (Supplier aggregate root):
  Supplier        — aggregate root with full lifecycle (DRAFT→ACTIVE→…→ARCHIVED)
  SupplierContact — contact persons for a supplier
  SupplierAddress — postal/billing/shipping addresses for a supplier

Spec ref: specs/006-purchase-management/data-model.md §Master Data Entities
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
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class SupplierCategory(TenantBaseModel):
    """Hierarchical supplier category classification tree.

    Categories form a tree structure with unlimited nesting up to SUPPLIER_CATEGORY_MAX_DEPTH
    (enforced at the application layer, not the database).

    Invariants (enforced at service layer):
      - ``code`` is unique per company.
      - ``parent_id`` must belong to the same company.
      - No circular parent references.
      - Tree depth ≤ SUPPLIER_CATEGORY_MAX_DEPTH (5).
    """

    __tablename__ = "supplier_categories"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "code",
            name="uq_sup_categories_company_code",
        ),
        Index("ix_sup_categories_parent_id", "parent_id"),
        Index("ix_sup_categories_company_status", "company_id", "status"),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_sup_categories_status",
        ),
        {"comment": "Hierarchical supplier category tree, scoped per company"},
    )

    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Unique supplier category code per company (e.g. 'TECH-001')",
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Human-readable category name",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional description of the category",
    )

    parent_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to parent SupplierCategory — NULL for root categories",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="active",
        doc="'active' or 'inactive'",
    )


class PaymentTerms(TenantBaseModel):
    """Company payment terms master.

    Defines the agreed payment schedule between the company and its suppliers.
    Referenced by the Supplier aggregate as the default payment agreement.

    Examples:
      - Net 30 (net_days=30)
      - 2/10 Net 30 (discount_percent=2.00, discount_days=10, net_days=30)
      - Immediate (net_days=0)
    """

    __tablename__ = "payment_terms"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "code",
            name="uq_payment_terms_company_code",
        ),
        CheckConstraint(
            "net_days >= 0",
            name="ck_payment_terms_net_days",
        ),
        CheckConstraint(
            "discount_days IS NULL OR discount_days >= 0",
            name="ck_payment_terms_discount_days",
        ),
        CheckConstraint(
            "discount_percent IS NULL OR (discount_percent >= 0 AND discount_percent <= 100)",
            name="ck_payment_terms_discount_percent",
        ),
        {"comment": "Company payment terms master for supplier agreements"},
    )

    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Unique payment terms code per company (e.g. 'NET30', '2-10-NET30')",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Human-readable payment terms name (e.g. 'Net 30 Days')",
    )

    net_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="30",
        doc="Number of days until payment is due",
    )

    discount_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Days within which early-payment discount applies (nullable)",
    )

    discount_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Early-payment discount percentage (nullable, e.g. 2.00 = 2%)",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional description of the payment terms",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Whether these payment terms are available for new supplier assignments",
    )


class PurchaseReasonCode(TenantBaseModel):
    """Typed reason codes for purchase workflow events.

    Used across multiple purchase workflows:
      - RETURN: Reason for vendor return / RMA
      - CANCELLATION: Reason for PR/PO cancellation
      - REJECTION: Reason for approval rejection
      - GENERAL: General-purpose purchase reason

    Invariants:
      - ``code`` is unique per company per ``reason_type``.
    """

    __tablename__ = "purchase_reason_codes"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "code",
            "reason_type",
            name="uq_purchase_reason_company_code_type",
        ),
        Index("ix_purchase_reason_type", "reason_type"),
        CheckConstraint(
            "reason_type IN ('RETURN', 'CANCELLATION', 'REJECTION', 'GENERAL')",
            name="ck_purchase_reason_type",
        ),
        {"comment": "Typed reason codes for returns, cancellations, and rejections"},
    )

    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Unique reason code per company per type (e.g. 'WRONG-ITEM')",
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Human-readable reason name",
    )

    reason_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Reason type: RETURN / CANCELLATION / REJECTION / GENERAL",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Whether this reason code is available for selection",
    )


# ---------------------------------------------------------------------------
# Phase 1: Supplier Aggregate Root
# ---------------------------------------------------------------------------


class Supplier(TenantBaseModel):
    """Supplier aggregate root.

    Represents a vendor/supplier that the company procures goods or services from.

    Status State Machine:
      DRAFT    → ACTIVE      (activation — supplier qualified)
      ACTIVE   → INACTIVE    (deactivation)
      ACTIVE   → BLOCKED     (compliance/dispute block)
      INACTIVE → ACTIVE      (reactivation)
      BLOCKED  → ACTIVE      (block resolved)
      ACTIVE   → ARCHIVED    (decommission — requires no open approved POs)
      INACTIVE → ARCHIVED    (decommission)

    Invariants (enforced at service layer):
      - supplier_code unique per company.
      - BLOCKED/ARCHIVED suppliers ineligible for new purchase documents.
      - Supplier with open approved POs cannot be archived.
      - is_preferred flag change restricted to Purchase Manager role.

    Spec ref: specs/006-purchase-management/data-model.md §Supplier (Aggregate Root)
    """

    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "supplier_code",
            name="uq_suppliers_company_code",
        ),
        Index("ix_suppliers_company_status", "company_id", "status"),
        Index("ix_suppliers_company_preferred", "company_id", "is_preferred"),
        CheckConstraint(
            "supplier_type IN ('GOODS', 'SERVICES', 'BOTH')",
            name="ck_suppliers_supplier_type",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'INACTIVE', 'BLOCKED', 'ARCHIVED')",
            name="ck_suppliers_status",
        ),
        CheckConstraint(
            "rating_score IS NULL OR (rating_score >= 0 AND rating_score <= 10)",
            name="ck_suppliers_rating_score",
        ),
        {"comment": "Supplier aggregate root — core supplier master record"},
    )

    supplier_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Unique supplier code per company (e.g. 'SUP-001')",
    )

    vendor_code: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        doc="Internal accounting vendor code reference (optional)",
    )

    legal_name: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        doc="Legal entity name of the supplier",
    )

    trading_name: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
        doc="Trading name / DBA name (optional)",
    )

    supplier_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="GOODS",
        doc="GOODS / SERVICES / BOTH",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="DRAFT",
        doc="DRAFT / ACTIVE / INACTIVE / BLOCKED / ARCHIVED",
    )

    category_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to SupplierCategory (nullable)",
    )

    payment_terms_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to PaymentTerms (nullable)",
    )

    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default="USD",
        doc="ISO 4217 currency code (default company base currency)",
    )

    tax_registration_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Supplier tax/VAT registration number",
    )

    tax_category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Tax category classification",
    )

    tax_region: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Tax jurisdiction / region",
    )

    website: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Supplier website URL",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Internal notes about this supplier",
    )

    is_preferred: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Whether this supplier is designated as preferred (Purchase Manager only)",
    )

    rating_score: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 1),
        nullable=True,
        doc="Composite supplier rating score (0.0–10.0, computed from GRs)",
    )

    lead_time_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Default supplier lead time in days",
    )

    branch_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="Reserved for Branch Management Epic — not yet active",
    )

    tsvector_search: Mapped[str | None] = mapped_column(
        TSVECTOR,
        nullable=True,
        doc="PostgreSQL FTS vector for supplier search (updated by DB trigger/service)",
    )


class SupplierContact(TenantBaseModel):
    """Contact person for a supplier.

    Each supplier can have multiple contacts. One contact is flagged is_primary.

    Spec ref: specs/006-purchase-management/data-model.md §SupplierContact
    """

    __tablename__ = "supplier_contacts"
    __table_args__ = (
        Index("ix_sup_contacts_supplier_id", "supplier_id"),
        {"comment": "Supplier contact persons (communication details)"},
    )

    supplier_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Supplier (parent aggregate)",
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Contact first name",
    )

    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Contact last name",
    )

    role: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Contact role (e.g. 'Accounts Receivable')",
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Contact email address",
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Contact phone number",
    )

    mobile: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Contact mobile number",
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Whether this is the primary contact for the supplier",
    )


class SupplierAddress(TenantBaseModel):
    """Postal / billing / shipping address for a supplier.

    Each supplier can have multiple addresses of different types.
    One address per type can be flagged is_default.

    Spec ref: specs/006-purchase-management/data-model.md §SupplierAddress
    """

    __tablename__ = "supplier_addresses"
    __table_args__ = (
        Index("ix_sup_addresses_supplier_id", "supplier_id"),
        CheckConstraint(
            "address_type IN ('BILLING', 'SHIPPING', 'REGISTERED', 'OTHER')",
            name="ck_sup_addresses_type",
        ),
        {"comment": "Supplier postal / billing / shipping addresses"},
    )

    supplier_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Supplier (parent aggregate)",
    )

    address_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="BILLING",
        doc="BILLING / SHIPPING / REGISTERED / OTHER",
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

    state: Mapped[str | None] = mapped_column(
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

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Whether this is the default address for this type",
    )

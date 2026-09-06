"""Sales master data ORM models — Phase 0.

Phase 0 entities:
  CustomerCategory    — customer classification with default credit/payment terms
  CustomerGroup       — secondary classification for reporting and discount eligibility
  SalesPaymentTerm    — sales-scoped payment terms master list
  SalesReasonCode     — typed reason codes for returns, cancellations, rejections
  SalesSequence       — auto-numbering sequences for sales documents
  SalesConfiguration  — company-level sales settings

Spec ref: specs/007-sales-management/data-model.md §Master Data Entities
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


class CustomerCategory(TenantBaseModel):
    """Customer classification category.

    Categories determine default pricing, payment terms, and credit limits
    for customers assigned to them.

    Invariants (enforced at service layer):
      - ``code`` is unique per company.
      - At least one category must exist per company.
    """

    __tablename__ = "customer_categories"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "code",
            name="uq_customer_categories_company_code",
        ),
        Index("ix_customer_categories_company_active", "company_id", "is_active"),
        CheckConstraint(
            "default_credit_limit >= 0",
            name="ck_customer_categories_credit_limit",
        ),
        {"comment": "Customer classification categories, scoped per company"},
    )

    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Unique customer category code per company (e.g. 'RETAIL')",
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Human-readable category name",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional description of this category",
    )

    default_payment_term_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="Default payment term for customers in this category",
    )

    default_credit_limit: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0",
        doc="Default credit limit for new customers in this category",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Whether this category is active and available for assignment",
    )


class CustomerGroup(TenantBaseModel):
    """Secondary customer classification for reporting and discount eligibility.

    Invariants (enforced at service layer):
      - ``code`` is unique per company.
    """

    __tablename__ = "customer_groups"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "code",
            name="uq_customer_groups_company_code",
        ),
        Index("ix_customer_groups_company_active", "company_id", "is_active"),
        {"comment": "Secondary customer classification for reporting and discounts"},
    )

    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Unique customer group code per company (e.g. 'VIP')",
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Human-readable group name",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional description of this group",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Whether this group is active and available for assignment",
    )


class SalesPaymentTerm(TenantBaseModel):
    """Sales-scoped payment terms master data.

    Payment terms define the due days, early-payment discount window,
    and discount percentage for customer invoices.
    """

    __tablename__ = "sales_payment_terms"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "code",
            name="uq_sales_payment_terms_company_code",
        ),
        Index("ix_sales_payment_terms_company_active", "company_id", "is_active"),
        CheckConstraint(
            "due_days >= 0",
            name="ck_sales_payment_terms_due_days",
        ),
        {"comment": "Sales payment terms master data, scoped per company"},
    )

    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Unique payment term code per company (e.g. 'NET30')",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Human-readable payment term name",
    )

    due_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Number of days until payment is due",
    )

    discount_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Early-payment discount window in days",
    )

    discount_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Early-payment discount percentage (e.g. 2.00 for 2%)",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional description of payment terms",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Whether this payment term is active and available for assignment",
    )


class SalesReasonCode(TenantBaseModel):
    """Reason codes for sales returns, cancellations, rejections.

    Invariants (enforced at service layer):
      - (company_id, code, reason_type) is unique.
    """

    __tablename__ = "sales_reason_codes"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "code",
            "reason_type",
            name="uq_sales_reason_codes_company_code_type",
        ),
        Index("ix_sales_reason_codes_company_type", "company_id", "reason_type"),
        CheckConstraint(
            "reason_type IN ('RETURN', 'CANCELLATION', 'REJECTION', 'GENERAL')",
            name="ck_sales_reason_codes_type",
        ),
        {"comment": "Typed reason codes for sales returns, cancellations, rejections"},
    )

    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Reason code identifier (e.g. 'DEFECTIVE')",
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
        doc="Whether this reason code is active",
    )


class SalesSequence(TenantBaseModel):
    """Auto-numbering sequence for sales documents.

    Each (company_id, document_type, year) combination has exactly one
    sequence record. The ``current_value`` is incremented with SELECT FOR UPDATE
    to guarantee uniqueness under concurrent document creation.

    Document types: SQ / SO / DN / SI / SR
    Format example: SO-2026-000147
    """

    __tablename__ = "sales_sequences"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "document_type",
            "year",
            name="uq_sales_seq_company_type_year",
        ),
        Index("ix_sales_sequences_type", "document_type"),
        CheckConstraint(
            "document_type IN ('SQ', 'SO', 'DN', 'SI', 'SR')",
            name="ck_sales_seq_document_type",
        ),
        CheckConstraint(
            "current_value >= 0",
            name="ck_sales_seq_current_value",
        ),
        {
            "comment": "Auto-numbering sequences for sales documents, locked with SELECT FOR UPDATE"
        },
    )

    document_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Document type: SQ / SO / DN / SI / SR",
    )

    prefix: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="''",
        doc="Company-configurable prefix (e.g. 'SO', 'SI')",
    )

    current_value: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        doc="Last issued sequence number — incremented atomically with SELECT FOR UPDATE",
    )

    year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Year component for year-based reset (NULL if reset_yearly=False)",
    )

    reset_yearly: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Reset sequence counter at the start of each calendar year",
    )

    format_pattern: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="'{PREFIX}-{YEAR}-{SEQ:06d}'",
        doc="Number format pattern, e.g. '{PREFIX}-{YEAR}-{SEQ:06d}'",
    )


class SalesConfiguration(TenantBaseModel):
    """Company-level sales configuration.

    One record per company (enforced via unique constraint on company_id).
    Created automatically with system defaults when a company first uses
    the sales module.
    """

    __tablename__ = "sales_configuration"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_sales_configuration_company"),
        CheckConstraint(
            "default_quotation_validity_days >= 1",
            name="ck_sales_config_validity_days",
        ),
        CheckConstraint(
            "credit_warning_threshold >= 0 AND credit_warning_threshold <= 100",
            name="ck_sales_config_credit_threshold",
        ),
        CheckConstraint(
            "reservation_expiry_hours >= 1",
            name="ck_sales_config_reservation_hours",
        ),
        {"comment": "Company-level sales configuration — one row per company"},
    )

    default_quotation_validity_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="30",
        doc="Default validity period for new quotations (days)",
    )

    quotation_expiry_warning_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="3",
        doc="Days before expiry to warn about quotation expiration",
    )

    auto_approve_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Orders below this amount auto-approve (null = no auto-approve)",
    )

    minimum_margin_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Minimum margin percentage for margin guard (null = no guard)",
    )

    credit_warning_threshold: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default="80.00",
        doc="Credit usage percentage that triggers WARNING status (0-100)",
    )

    reservation_expiry_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="48",
        doc="Hours before inventory reservations expire",
    )

    require_quotation_before_order: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Require a converted quotation before creating a sales order",
    )

    tax_inclusive_pricing: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Whether prices include tax by default",
    )

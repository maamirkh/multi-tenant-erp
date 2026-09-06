"""Purchase supplier enrichment ORM models — Phase 2.

Phase 2 entities (Supplier enrichment):
  CreditLimit     — per-supplier credit limit with enforcement mode
  BankDetails     — banking details (Finance Manager restricted)
  SupplierRating  — composite rating score computed from GRs
  SupplierDocument — compliance documents with expiry tracking
  SupplierLeadTime — default and per-product lead times

All FK columns use PG_UUID(as_uuid=False) (string hex FK pattern).
company_id / id use Uuid(as_uuid=True) via TenantBaseModel.

Spec ref: specs/006-purchase-management/data-model.md §Supplier Aggregate (Phases 2–3)
Tasks: T055, T056, T057
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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
# CreditLimit
# ---------------------------------------------------------------------------


class CreditLimit(TenantBaseModel):
    """Per-supplier credit limit with enforcement mode.

    One active credit limit per supplier. Enforcement mode overrides the
    company-level PurchasePolicy.credit_limit_mode for this specific supplier.

    Enforcement modes:
      BLOCK — reject PO approval if outstanding + new PO value > credit limit
      WARN  — allow PO but notify Purchase Manager
      OFF   — skip credit limit check for this supplier

    Invariants:
      - One CreditLimit per supplier (unique supplier_id + company_id).
      - credit_limit_amount >= 0.
    """

    __tablename__ = "credit_limits"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "supplier_id",
            name="uq_credit_limits_company_supplier",
        ),
        CheckConstraint(
            "credit_limit_amount >= 0",
            name="ck_credit_limits_amount",
        ),
        CheckConstraint(
            "enforcement_mode IN ('BLOCK', 'WARN', 'OFF')",
            name="ck_credit_limits_enforcement_mode",
        ),
        Index("ix_credit_limits_supplier_id", "supplier_id"),
        {"comment": "Per-supplier credit limits with configurable enforcement mode"},
    )

    supplier_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Supplier (parent aggregate)",
    )

    credit_limit_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0",
        doc="Maximum outstanding PO value allowed for this supplier",
    )

    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default="USD",
        doc="ISO 4217 currency code for the credit limit amount",
    )

    enforcement_mode: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="WARN",
        doc="BLOCK / WARN / OFF — overrides company policy for this supplier",
    )


# ---------------------------------------------------------------------------
# BankDetails
# ---------------------------------------------------------------------------


class BankDetails(TenantBaseModel):
    """Banking details for a supplier.

    Finance Manager restricted — create/update/delete requires FINANCE_MANAGER role.
    Multiple bank accounts per supplier are allowed; one can be flagged is_primary.

    Spec ref: specs/006-purchase-management/data-model.md §BankDetails
    """

    __tablename__ = "bank_details"
    __table_args__ = (
        Index("ix_bank_details_supplier_id", "supplier_id"),
        {"comment": "Supplier banking details (Finance Manager restricted)"},
    )

    supplier_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Supplier (parent aggregate)",
    )

    bank_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Name of the bank",
    )

    account_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Account holder name",
    )

    account_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Bank account number",
    )

    iban: Mapped[str | None] = mapped_column(
        String(34),
        nullable=True,
        doc="International Bank Account Number (IBAN) — nullable",
    )

    swift_bic: Mapped[str | None] = mapped_column(
        String(11),
        nullable=True,
        doc="SWIFT/BIC code — nullable",
    )

    routing_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Routing/sort code — nullable",
    )

    bank_country: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        doc="ISO 3166-1 alpha-2 country code of the bank",
    )

    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default="USD",
        doc="Currency code for this bank account",
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Whether this is the primary/preferred bank account",
    )


# ---------------------------------------------------------------------------
# SupplierRating
# ---------------------------------------------------------------------------


class SupplierRating(TenantBaseModel):
    """Computed supplier performance rating.

    One active rating record per supplier (unique on supplier_id + company_id).
    Composite score formula (enforced at service layer):
      score = (on_time_rate × 0.40 + fill_rate × 0.40 + (100 - rejection_rate) × 0.20) / 10

    Manual override allows Purchase Manager to set a fixed score with reason.
    When manual_override_score is set, it replaces composite_score on the Supplier.

    Spec ref: specs/006-purchase-management/data-model.md §SupplierRating
    """

    __tablename__ = "supplier_ratings"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "supplier_id",
            name="uq_supplier_ratings_company_supplier",
        ),
        CheckConstraint(
            "on_time_rate >= 0 AND on_time_rate <= 100",
            name="ck_supplier_ratings_on_time",
        ),
        CheckConstraint(
            "fill_rate >= 0 AND fill_rate <= 100",
            name="ck_supplier_ratings_fill_rate",
        ),
        CheckConstraint(
            "rejection_rate >= 0 AND rejection_rate <= 100",
            name="ck_supplier_ratings_rejection_rate",
        ),
        CheckConstraint(
            "composite_score >= 0 AND composite_score <= 10",
            name="ck_supplier_ratings_composite",
        ),
        CheckConstraint(
            "manual_override_score IS NULL OR (manual_override_score >= 0 AND manual_override_score <= 10)",
            name="ck_supplier_ratings_override",
        ),
        Index("ix_supplier_ratings_supplier_id", "supplier_id"),
        {"comment": "Computed supplier performance rating — one per supplier"},
    )

    supplier_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Supplier (parent aggregate)",
    )

    on_time_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default="0",
        doc="Percentage of deliveries received on or before expected date (0–100)",
    )

    fill_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default="0",
        doc="Percentage of ordered quantity actually received (0–100)",
    )

    rejection_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default="0",
        doc="Percentage of received items rejected / returned (0–100)",
    )

    composite_score: Mapped[Decimal] = mapped_column(
        Numeric(3, 1),
        nullable=False,
        server_default="0",
        doc="Weighted composite score (0.0–10.0)",
    )

    gr_count_window: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        doc="Number of GR records used for this computation",
    )

    manual_override_score: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 1),
        nullable=True,
        doc="Manual override score set by Purchase Manager (replaces computed score when set)",
    )

    manual_override_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Reason for manual score override",
    )

    last_computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="Timestamp of the last automatic computation",
    )


# ---------------------------------------------------------------------------
# SupplierDocument
# ---------------------------------------------------------------------------


class SupplierDocument(TenantBaseModel):
    """Compliance document attached to a supplier.

    Used for trade licenses, ISO certificates, insurance, and similar
    time-limited compliance documents. Documents with expiry_date are
    monitored by SupplierDocumentAlertService.

    Spec ref: specs/006-purchase-management/data-model.md §SupplierDocument
    """

    __tablename__ = "supplier_documents"
    __table_args__ = (
        Index("ix_supplier_documents_supplier_id", "supplier_id"),
        Index("ix_supplier_documents_expiry", "company_id", "expiry_date"),
        {"comment": "Compliance documents for suppliers (trade license, certs, etc.)"},
    )

    supplier_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Supplier (parent aggregate)",
    )

    document_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Type of document (e.g. 'Trade License', 'ISO Certificate')",
    )

    document_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Official document reference number",
    )

    issue_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Date the document was issued",
    )

    expiry_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Date the document expires — triggers expiry alert when approaching",
    )

    file_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        doc="S3 / storage URL of the uploaded document file",
    )


# ---------------------------------------------------------------------------
# SupplierLeadTime
# ---------------------------------------------------------------------------


class SupplierLeadTime(TenantBaseModel):
    """Supplier lead time — default and per-product overrides.

    The Supplier model has a default lead_time_days field. This table stores
    per-product-supplier lead time overrides for more precise procurement
    planning.

    When product_id is NULL: represents the supplier-level default lead time.
    When product_id is set: represents the lead time for that specific product
    from this supplier.

    Spec ref: specs/006-purchase-management/tasks.md §T057
    """

    __tablename__ = "supplier_lead_times"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "supplier_id",
            "product_id",
            name="uq_supplier_lead_times_supplier_product",
        ),
        CheckConstraint(
            "lead_time_days >= 0",
            name="ck_supplier_lead_times_days",
        ),
        Index("ix_supplier_lead_times_supplier_id", "supplier_id"),
        {"comment": "Supplier lead times — per supplier and per product override"},
    )

    supplier_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Supplier (parent aggregate)",
    )

    product_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to Product (Epic 5); NULL = supplier-level default",
    )

    lead_time_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Expected lead time in days from order to delivery",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional notes about this lead time (e.g. seasonal variations)",
    )

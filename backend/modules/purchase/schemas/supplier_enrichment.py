"""Pydantic schemas for Phase 2 Supplier enrichment entities.

Covers:
  - CreditLimit   (create, update, read)
  - BankDetails   (create, update, read) — Finance Manager restricted
  - SupplierRating (read, manual override)
  - SupplierDocument (create, read)
  - SupplierLeadTime (create, update, read)
  - ExpiringDocumentsResponse

Spec ref: specs/006-purchase-management/data-model.md §Supplier Aggregate (Phases 2–3)
Task: T065
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from modules.purchase.schemas.base import PurchaseBaseSchema

VALID_ENFORCEMENT_MODES = ("BLOCK", "WARN", "OFF")


# ---------------------------------------------------------------------------
# CreditLimit
# ---------------------------------------------------------------------------


class CreditLimitCreate(PurchaseBaseSchema):
    """Request body for setting a supplier credit limit."""

    credit_limit_amount: Decimal = Field(..., ge=0, description="Credit limit amount")
    currency_code: str = Field("USD", min_length=3, max_length=3)
    enforcement_mode: str = Field("WARN", description="BLOCK / WARN / OFF")

    @field_validator("enforcement_mode")
    @classmethod
    def validate_enforcement_mode(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in VALID_ENFORCEMENT_MODES:
            raise ValueError(
                f"enforcement_mode must be one of {VALID_ENFORCEMENT_MODES}"
            )
        return v

    @field_validator("currency_code")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        return v.upper().strip()


class CreditLimitUpdate(PurchaseBaseSchema):
    """Request body for updating a supplier credit limit."""

    credit_limit_amount: Decimal | None = Field(None, ge=0)
    currency_code: str | None = Field(None, min_length=3, max_length=3)
    enforcement_mode: str | None = None

    @field_validator("enforcement_mode")
    @classmethod
    def validate_enforcement_mode(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.upper().strip()
        if v not in VALID_ENFORCEMENT_MODES:
            raise ValueError(
                f"enforcement_mode must be one of {VALID_ENFORCEMENT_MODES}"
            )
        return v


class CreditLimitRead(PurchaseBaseSchema):
    """Response schema for a supplier credit limit."""

    id: UUID
    company_id: UUID
    supplier_id: UUID
    credit_limit_amount: Decimal
    currency_code: str
    enforcement_mode: str
    created_at: datetime
    updated_at: datetime | None


class CreditLimitCheckResult(PurchaseBaseSchema):
    """Result of a credit limit check at PO approval time."""

    supplier_id: UUID
    credit_limit_amount: Decimal
    currency_code: str
    outstanding_po_value: Decimal
    new_po_total: Decimal
    total_exposure: Decimal
    enforcement_mode: str
    exceeds_limit: bool
    action: str  # BLOCKED / WARNED / ALLOWED / SKIPPED


# ---------------------------------------------------------------------------
# BankDetails
# ---------------------------------------------------------------------------


class BankDetailsCreate(PurchaseBaseSchema):
    """Request body for adding supplier bank details (Finance Manager only)."""

    bank_name: str = Field(..., min_length=1, max_length=200)
    account_name: str = Field(..., min_length=1, max_length=200)
    account_number: str = Field(..., min_length=1, max_length=50)
    iban: str | None = Field(None, max_length=34)
    swift_bic: str | None = Field(None, max_length=11)
    routing_number: str | None = Field(None, max_length=20)
    bank_country: str = Field(
        ..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2"
    )
    currency_code: str = Field("USD", min_length=3, max_length=3)
    is_primary: bool = False

    @field_validator("bank_country")
    @classmethod
    def country_uppercase(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("currency_code")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        return v.upper().strip()


class BankDetailsUpdate(PurchaseBaseSchema):
    """Request body for updating supplier bank details (Finance Manager only)."""

    bank_name: str | None = Field(None, min_length=1, max_length=200)
    account_name: str | None = Field(None, min_length=1, max_length=200)
    account_number: str | None = Field(None, min_length=1, max_length=50)
    iban: str | None = None
    swift_bic: str | None = None
    routing_number: str | None = None
    bank_country: str | None = Field(None, min_length=2, max_length=2)
    currency_code: str | None = Field(None, min_length=3, max_length=3)
    is_primary: bool | None = None


class BankDetailsRead(PurchaseBaseSchema):
    """Response schema for supplier bank details."""

    id: UUID
    company_id: UUID
    supplier_id: UUID
    bank_name: str
    account_name: str
    account_number: str
    iban: str | None
    swift_bic: str | None
    routing_number: str | None
    bank_country: str
    currency_code: str
    is_primary: bool
    created_at: datetime
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# SupplierRating
# ---------------------------------------------------------------------------


class SupplierRatingRead(PurchaseBaseSchema):
    """Response schema for a supplier rating record."""

    id: UUID
    company_id: UUID
    supplier_id: UUID
    on_time_rate: Decimal
    fill_rate: Decimal
    rejection_rate: Decimal
    composite_score: Decimal
    gr_count_window: int
    manual_override_score: Decimal | None
    manual_override_reason: str | None
    last_computed_at: datetime
    created_at: datetime
    updated_at: datetime | None


class SupplierRatingManualOverride(PurchaseBaseSchema):
    """Request body for manually overriding a supplier rating (Purchase Manager only)."""

    override_score: Decimal = Field(
        ..., ge=0, le=10, description="Manual score 0.0–10.0"
    )
    override_reason: str = Field(
        ..., min_length=1, max_length=2000, description="Mandatory reason for override"
    )


class SupplierRatingClearOverride(PurchaseBaseSchema):
    """Request body for clearing a manual rating override."""

    reason: str | None = None


# ---------------------------------------------------------------------------
# SupplierDocument
# ---------------------------------------------------------------------------


class SupplierDocumentCreate(PurchaseBaseSchema):
    """Request body for adding a compliance document to a supplier."""

    document_type: str = Field(
        ..., min_length=1, max_length=100, description="e.g. 'Trade License'"
    )
    document_number: str | None = Field(None, max_length=100)
    issue_date: date | None = None
    expiry_date: date | None = None
    file_url: str | None = Field(None, max_length=1000)


class SupplierDocumentRead(PurchaseBaseSchema):
    """Response schema for a supplier compliance document."""

    id: UUID
    company_id: UUID
    supplier_id: UUID
    document_type: str
    document_number: str | None
    issue_date: date | None
    expiry_date: date | None
    file_url: str | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime | None


class ExpiringDocumentItem(PurchaseBaseSchema):
    """Single item in the expiring documents report."""

    document_id: UUID
    supplier_id: UUID
    supplier_code: str
    legal_name: str
    document_type: str
    document_number: str | None
    expiry_date: date
    days_until_expiry: int


class ExpiringDocumentsResponse(PurchaseBaseSchema):
    """Response for the expiring documents alert check."""

    total: int
    documents: list[ExpiringDocumentItem]


# ---------------------------------------------------------------------------
# SupplierLeadTime
# ---------------------------------------------------------------------------


class SupplierLeadTimeCreate(PurchaseBaseSchema):
    """Request body for setting a supplier lead time."""

    product_id: UUID | None = Field(
        None, description="NULL = supplier default; set for product-specific"
    )
    lead_time_days: int = Field(..., ge=0, description="Lead time in days")
    notes: str | None = None


class SupplierLeadTimeUpdate(PurchaseBaseSchema):
    """Request body for updating a supplier lead time."""

    lead_time_days: int | None = Field(None, ge=0)
    notes: str | None = None


class SupplierLeadTimeRead(PurchaseBaseSchema):
    """Response schema for a supplier lead time record."""

    id: UUID
    company_id: UUID
    supplier_id: UUID
    product_id: UUID | None
    lead_time_days: int
    notes: str | None
    created_at: datetime
    updated_at: datetime | None

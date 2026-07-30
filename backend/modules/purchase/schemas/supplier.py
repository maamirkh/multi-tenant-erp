"""Pydantic schemas for the Supplier aggregate — Phase 1.

Covers:
  - Supplier (create, update, read, list)
  - SupplierContact (create, update, read)
  - SupplierAddress (create, update, read)
  - SupplierSearch (query params)
  - SupplierLifecycleAction (activate, deactivate, block, etc.)
  - BulkImportResult

Spec ref: specs/006-purchase-management/data-model.md §Supplier Aggregate
Task: T040
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from modules.purchase.schemas.base import PurchaseBaseSchema

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SUPPLIER_TYPES = ("GOODS", "SERVICES", "BOTH")
VALID_SUPPLIER_STATUSES = ("DRAFT", "ACTIVE", "INACTIVE", "BLOCKED", "ARCHIVED")
VALID_ADDRESS_TYPES = ("BILLING", "SHIPPING", "REGISTERED", "OTHER")


# ---------------------------------------------------------------------------
# Supplier Contact
# ---------------------------------------------------------------------------


class SupplierContactCreate(PurchaseBaseSchema):
    """Request body for adding a supplier contact."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: str | None = Field(None, max_length=100)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    mobile: str | None = Field(None, max_length=50)
    is_primary: bool = False


class SupplierContactUpdate(PurchaseBaseSchema):
    """Request body for updating a supplier contact."""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    is_primary: bool | None = None


class SupplierContactRead(PurchaseBaseSchema):
    """Response schema for a supplier contact."""

    id: UUID
    company_id: UUID
    supplier_id: UUID
    first_name: str
    last_name: str
    role: str | None
    email: str | None
    phone: str | None
    mobile: str | None
    is_primary: bool


# ---------------------------------------------------------------------------
# Supplier Address
# ---------------------------------------------------------------------------


class SupplierAddressCreate(PurchaseBaseSchema):
    """Request body for adding a supplier address."""

    address_type: str = Field(
        "BILLING", description="BILLING / SHIPPING / REGISTERED / OTHER"
    )
    address_line_1: str = Field(..., min_length=1, max_length=300)
    address_line_2: str | None = Field(None, max_length=300)
    city: str = Field(..., min_length=1, max_length=100)
    state: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country_code: str = Field(
        ..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2"
    )
    is_default: bool = False

    @field_validator("address_type")
    @classmethod
    def validate_address_type(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in VALID_ADDRESS_TYPES:
            raise ValueError(f"address_type must be one of {VALID_ADDRESS_TYPES}")
        return v

    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        return v.upper().strip()


class SupplierAddressUpdate(PurchaseBaseSchema):
    """Request body for updating a supplier address."""

    address_line_1: str | None = Field(None, min_length=1, max_length=300)
    address_line_2: str | None = None
    city: str | None = Field(None, min_length=1, max_length=100)
    state: str | None = None
    postal_code: str | None = None
    country_code: str | None = Field(None, min_length=2, max_length=2)
    is_default: bool | None = None


class SupplierAddressRead(PurchaseBaseSchema):
    """Response schema for a supplier address."""

    id: UUID
    company_id: UUID
    supplier_id: UUID
    address_type: str
    address_line_1: str
    address_line_2: str | None
    city: str
    state: str | None
    postal_code: str | None
    country_code: str
    is_default: bool


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------


class SupplierCreate(PurchaseBaseSchema):
    """Request body for creating a supplier."""

    supplier_code: str = Field(
        ..., min_length=1, max_length=30, description="Unique code per company"
    )
    vendor_code: str | None = Field(None, max_length=30)
    legal_name: str = Field(..., min_length=1, max_length=300)
    trading_name: str | None = Field(None, max_length=300)
    supplier_type: str = Field("GOODS", description="GOODS / SERVICES / BOTH")
    category_id: UUID | None = None
    payment_terms_id: UUID | None = None
    currency_code: str = Field("USD", min_length=3, max_length=3)
    tax_registration_number: str | None = Field(None, max_length=50)
    tax_category: str | None = Field(None, max_length=50)
    tax_region: str | None = Field(None, max_length=100)
    website: str | None = Field(None, max_length=500)
    notes: str | None = None
    lead_time_days: int | None = Field(None, ge=0)

    @field_validator("supplier_code")
    @classmethod
    def code_uppercase(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("supplier_type")
    @classmethod
    def validate_supplier_type(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in VALID_SUPPLIER_TYPES:
            raise ValueError(f"supplier_type must be one of {VALID_SUPPLIER_TYPES}")
        return v

    @field_validator("currency_code")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        return v.upper().strip()


class SupplierUpdate(PurchaseBaseSchema):
    """Request body for updating a supplier's mutable fields."""

    vendor_code: str | None = Field(None, max_length=30)
    legal_name: str | None = Field(None, min_length=1, max_length=300)
    trading_name: str | None = None
    supplier_type: str | None = None
    category_id: UUID | None = None
    payment_terms_id: UUID | None = None
    currency_code: str | None = Field(None, min_length=3, max_length=3)
    tax_registration_number: str | None = None
    tax_category: str | None = None
    tax_region: str | None = None
    website: str | None = None
    notes: str | None = None
    lead_time_days: int | None = Field(None, ge=0)

    @field_validator("supplier_type")
    @classmethod
    def validate_supplier_type(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.upper().strip()
        if v not in VALID_SUPPLIER_TYPES:
            raise ValueError(f"supplier_type must be one of {VALID_SUPPLIER_TYPES}")
        return v


class SupplierRead(PurchaseBaseSchema):
    """Response schema for a single supplier."""

    id: UUID
    company_id: UUID
    supplier_code: str
    vendor_code: str | None
    legal_name: str
    trading_name: str | None
    supplier_type: str
    status: str
    category_id: UUID | None
    payment_terms_id: UUID | None
    currency_code: str
    tax_registration_number: str | None
    tax_category: str | None
    tax_region: str | None
    website: str | None
    notes: str | None
    is_preferred: bool
    rating_score: Decimal | None
    lead_time_days: int | None
    created_at: datetime
    updated_at: datetime | None


class SupplierList(PurchaseBaseSchema):
    """Response schema for supplier list items (compact)."""

    id: UUID
    company_id: UUID
    supplier_code: str
    legal_name: str
    trading_name: str | None
    supplier_type: str
    status: str
    is_preferred: bool
    rating_score: Decimal | None
    lead_time_days: int | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Lifecycle action bodies
# ---------------------------------------------------------------------------


class SupplierActivateRequest(PurchaseBaseSchema):
    """Request body for activating a supplier (optional reason)."""

    reason: str | None = None


class SupplierDeactivateRequest(PurchaseBaseSchema):
    """Request body for deactivating a supplier."""

    reason: str | None = None


class SupplierBlockRequest(PurchaseBaseSchema):
    """Request body for blocking a supplier. Reason is mandatory."""

    reason: str = Field(
        ..., min_length=1, max_length=1000, description="Mandatory block reason"
    )


class SupplierReactivateRequest(PurchaseBaseSchema):
    """Request body for reactivating a blocked/inactive supplier."""

    reason: str | None = None


class SupplierArchiveRequest(PurchaseBaseSchema):
    """Request body for archiving a supplier (decommission)."""

    reason: str | None = None


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class SupplierSearchParams(PurchaseBaseSchema):
    """Query parameters for supplier search."""

    query: str | None = None
    status: str | None = None
    category_id: UUID | None = None
    supplier_type: str | None = None
    is_preferred: bool | None = None
    skip: int = Field(0, ge=0)
    limit: int = Field(20, ge=1, le=200)


# ---------------------------------------------------------------------------
# Bulk import
# ---------------------------------------------------------------------------


class SupplierImportRow(PurchaseBaseSchema):
    """One row from a bulk supplier import file."""

    supplier_code: str
    legal_name: str
    trading_name: str | None = None
    supplier_type: str = "GOODS"
    currency_code: str = "USD"
    contact_email: str | None = None
    contact_name: str | None = None
    website: str | None = None
    notes: str | None = None
    lead_time_days: int | None = None
    tax_registration_number: str | None = None


class SupplierImportRowError(PurchaseBaseSchema):
    """Row-level validation error from bulk import."""

    row_number: int
    supplier_code: str | None
    errors: list[str]


class BulkImportResult(PurchaseBaseSchema):
    """Result of a supplier bulk import operation."""

    total_rows: int
    created: int
    skipped: int
    failed: int
    errors: list[SupplierImportRowError]

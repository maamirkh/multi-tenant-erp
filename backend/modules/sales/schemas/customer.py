"""Pydantic schemas for Customer aggregate — Phase 1.

Covers:
  - Customer (create, update, read, list)
  - CustomerContact (create, update, read)
  - CustomerAddress (create, update, read)
  - CustomerBankDetail (create, update, read)
  - CustomerNote (create, read)
  - CustomerStatusTransition (for lifecycle operations)

Spec ref: specs/007-sales-management/data-model.md §Customer Aggregate
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from modules.sales.schemas.base import SalesBaseSchema

# ---------------------------------------------------------------------------
# CustomerContact schemas
# ---------------------------------------------------------------------------


class CustomerContactCreate(SalesBaseSchema):
    """Request body for adding a contact to a customer."""

    contact_name: str = Field(..., min_length=1, max_length=200)
    title: str | None = Field(None, max_length=100)
    email: str | None = Field(None, max_length=254)
    phone: str | None = Field(None, max_length=30)
    mobile: str | None = Field(None, max_length=30)
    department: str | None = Field(None, max_length=100)
    is_primary: bool = False
    is_billing_contact: bool = False
    is_shipping_contact: bool = False
    notes: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is not None and "@" not in v:
            raise ValueError("Invalid email address")
        return v


class CustomerContactUpdate(SalesBaseSchema):
    """Request body for updating a contact."""

    contact_name: str | None = Field(None, min_length=1, max_length=200)
    title: str | None = None
    email: str | None = Field(None, max_length=254)
    phone: str | None = None
    mobile: str | None = None
    department: str | None = None
    is_primary: bool | None = None
    is_billing_contact: bool | None = None
    is_shipping_contact: bool | None = None
    notes: str | None = None


class CustomerContactRead(SalesBaseSchema):
    """Response schema for a customer contact."""

    id: UUID
    customer_id: str
    contact_name: str
    title: str | None
    email: str | None
    phone: str | None
    mobile: str | None
    department: str | None
    is_primary: bool
    is_billing_contact: bool
    is_shipping_contact: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# CustomerAddress schemas
# ---------------------------------------------------------------------------


class CustomerAddressCreate(SalesBaseSchema):
    """Request body for adding an address to a customer."""

    address_type: str = Field(
        ...,
        description="BILLING / SHIPPING / BOTH",
    )
    address_label: str | None = Field(None, max_length=100)
    address_line_1: str = Field(..., min_length=1, max_length=300)
    address_line_2: str | None = Field(None, max_length=300)
    city: str = Field(..., min_length=1, max_length=100)
    state_province: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country_code: str = Field(..., min_length=2, max_length=2)
    is_default_billing: bool = False
    is_default_shipping: bool = False

    @field_validator("address_type")
    @classmethod
    def validate_address_type(cls, v: str) -> str:
        v = v.upper()
        if v not in ("BILLING", "SHIPPING", "BOTH"):
            raise ValueError("address_type must be BILLING, SHIPPING, or BOTH")
        return v

    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        return v.upper()


class CustomerAddressUpdate(SalesBaseSchema):
    """Request body for updating an address."""

    address_type: str | None = None
    address_label: str | None = None
    address_line_1: str | None = Field(None, min_length=1, max_length=300)
    address_line_2: str | None = None
    city: str | None = Field(None, min_length=1, max_length=100)
    state_province: str | None = None
    postal_code: str | None = None
    country_code: str | None = Field(None, min_length=2, max_length=2)
    is_default_billing: bool | None = None
    is_default_shipping: bool | None = None


class CustomerAddressRead(SalesBaseSchema):
    """Response schema for a customer address."""

    id: UUID
    customer_id: str
    address_type: str
    address_label: str | None
    address_line_1: str
    address_line_2: str | None
    city: str
    state_province: str | None
    postal_code: str | None
    country_code: str
    is_default_billing: bool
    is_default_shipping: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# CustomerBankDetail schemas
# ---------------------------------------------------------------------------


class CustomerBankDetailCreate(SalesBaseSchema):
    """Request body for adding a bank detail to a customer."""

    bank_name: str = Field(..., min_length=1, max_length=200)
    branch_name: str | None = Field(None, max_length=200)
    account_number: str = Field(..., min_length=1, max_length=50)
    iban: str | None = Field(None, max_length=34)
    swift_bic: str | None = Field(None, max_length=11)
    account_holder_name: str = Field(..., min_length=1, max_length=200)
    is_default: bool = False


class CustomerBankDetailUpdate(SalesBaseSchema):
    """Request body for updating a bank detail."""

    bank_name: str | None = Field(None, min_length=1, max_length=200)
    branch_name: str | None = None
    account_number: str | None = Field(None, min_length=1, max_length=50)
    iban: str | None = None
    swift_bic: str | None = None
    account_holder_name: str | None = Field(None, min_length=1, max_length=200)
    is_default: bool | None = None


class CustomerBankDetailRead(SalesBaseSchema):
    """Response schema for a customer bank detail."""

    id: UUID
    customer_id: str
    bank_name: str
    branch_name: str | None
    account_number: str
    iban: str | None
    swift_bic: str | None
    account_holder_name: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# CustomerNote schemas
# ---------------------------------------------------------------------------


class CustomerNoteCreate(SalesBaseSchema):
    """Request body for adding a note to a customer."""

    content: str = Field(..., min_length=1, description="Note content")


class CustomerNoteRead(SalesBaseSchema):
    """Response schema for a customer note."""

    id: UUID
    customer_id: str
    content: str
    author_id: str
    author_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Customer schemas
# ---------------------------------------------------------------------------


class CustomerCreate(SalesBaseSchema):
    """Request body for creating a new customer (starts in DRAFT)."""

    customer_code: str = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Unique customer code per company (immutable after creation)",
    )
    legal_name: str = Field(..., min_length=1, max_length=200)
    trading_name: str | None = Field(None, max_length=200)
    customer_type: str = Field(
        default="COMPANY",
        description="INDIVIDUAL / COMPANY / GOVERNMENT / INTERNAL",
    )
    category_id: UUID = Field(..., description="CustomerCategory ID")
    group_id: UUID | None = None
    payment_term_id: UUID | None = None
    credit_limit: Decimal = Field(default=Decimal("0"), ge=0)
    rating: str | None = None
    currency_code: str = Field(
        default="USD", min_length=3, max_length=3, description="ISO 4217"
    )
    tax_registration_number: str | None = Field(None, max_length=50)
    tax_exempt: bool = False
    tax_exempt_certificate: str | None = Field(None, max_length=100)
    tax_exempt_expiry: str | None = None
    website: str | None = Field(None, max_length=500)
    industry: str | None = Field(None, max_length=100)
    annual_revenue_range: str | None = Field(None, max_length=50)
    custom_fields: dict[str, Any] | None = None
    notes: str | None = None

    @field_validator("customer_code")
    @classmethod
    def code_uppercase(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("customer_type")
    @classmethod
    def validate_customer_type(cls, v: str) -> str:
        v = v.upper()
        if v not in ("INDIVIDUAL", "COMPANY", "GOVERNMENT", "INTERNAL"):
            raise ValueError(
                "customer_type must be INDIVIDUAL, COMPANY, GOVERNMENT, or INTERNAL"
            )
        return v

    @field_validator("currency_code")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        return v.upper()

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: str | None) -> str | None:
        if v is not None and v.upper() not in ("A", "B", "C", "D", "F"):
            raise ValueError("rating must be A, B, C, D, or F")
        return v.upper() if v else None

    @model_validator(mode="after")
    def validate_custom_fields(self) -> CustomerCreate:
        if self.custom_fields and len(self.custom_fields) > 20:
            raise ValueError("custom_fields may not exceed 20 entries")
        return self


class CustomerUpdate(SalesBaseSchema):
    """Request body for updating a customer's core fields."""

    legal_name: str | None = Field(None, min_length=1, max_length=200)
    trading_name: str | None = None
    customer_type: str | None = None
    category_id: UUID | None = None
    group_id: UUID | None = None
    payment_term_id: UUID | None = None
    credit_limit: Decimal | None = Field(None, ge=0)
    rating: str | None = None
    currency_code: str | None = Field(None, min_length=3, max_length=3)
    tax_registration_number: str | None = None
    tax_exempt: bool | None = None
    tax_exempt_certificate: str | None = None
    tax_exempt_expiry: str | None = None
    website: str | None = None
    industry: str | None = None
    annual_revenue_range: str | None = None
    custom_fields: dict[str, Any] | None = None
    notes: str | None = None


class CustomerRead(SalesBaseSchema):
    """Response schema for a single customer."""

    id: UUID
    company_id: UUID
    customer_code: str
    legal_name: str
    trading_name: str | None
    customer_type: str
    category_id: str
    group_id: str | None
    status: str
    payment_term_id: str | None
    credit_limit: Decimal
    credit_status: str
    rating: str | None
    currency_code: str
    tax_registration_number: str | None
    tax_exempt: bool
    tax_exempt_certificate: str | None
    tax_exempt_expiry: str | None
    website: str | None
    industry: str | None
    annual_revenue_range: str | None
    custom_fields: dict[str, Any] | None
    notes: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None

    model_config = {"from_attributes": True}


class CustomerListItem(SalesBaseSchema):
    """Lightweight customer representation for list views."""

    id: UUID
    customer_code: str
    legal_name: str
    trading_name: str | None
    customer_type: str
    status: str
    credit_status: str
    rating: str | None
    currency_code: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerStatusTransition(SalesBaseSchema):
    """Request body for customer status lifecycle transitions."""

    action: str = Field(
        ...,
        description=(
            "One of: activate, hold, release_hold, block, unblock, deactivate, reactivate"
        ),
    )
    reason: str | None = Field(None, max_length=500)

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        valid = {
            "activate",
            "hold",
            "release_hold",
            "block",
            "unblock",
            "deactivate",
            "reactivate",
        }
        if v not in valid:
            raise ValueError(f"action must be one of: {', '.join(sorted(valid))}")
        return v


class CustomerCreditUpdate(SalesBaseSchema):
    """Request body for updating customer credit settings."""

    credit_limit: Decimal = Field(..., ge=0, description="New credit limit")
    credit_status: str | None = Field(
        None,
        description="Override credit status: GOOD / WARNING / EXCEEDED / HOLD",
    )

    @field_validator("credit_status")
    @classmethod
    def validate_credit_status(cls, v: str | None) -> str | None:
        if v is not None and v.upper() not in (
            "GOOD",
            "WARNING",
            "EXCEEDED",
            "HOLD",
        ):
            raise ValueError("credit_status must be GOOD, WARNING, EXCEEDED, or HOLD")
        return v.upper() if v else None


class CustomerImportRow(SalesBaseSchema):
    """Single row from a customer CSV/Excel import."""

    customer_code: str
    legal_name: str
    trading_name: str | None = None
    customer_type: str = "COMPANY"
    category_code: str = ""
    group_code: str | None = None
    payment_term_code: str | None = None
    credit_limit: Decimal = Decimal("0")
    currency_code: str = "USD"
    tax_registration_number: str | None = None
    website: str | None = None
    industry: str | None = None


class CustomerImportResult(SalesBaseSchema):
    """Result of a bulk customer import operation."""

    total_rows: int
    imported: int
    skipped: int
    errors: list[dict[str, str]]

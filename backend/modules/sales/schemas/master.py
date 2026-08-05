"""Pydantic schemas for sales master data entities.

Covers:
  - CustomerCategory (create, update, read)
  - CustomerGroup (create, update, read)
  - SalesPaymentTerm (create, update, read)
  - SalesReasonCode (create, update, read)
  - SalesConfiguration (read, update)
  - FeatureFlag (read, update)

Spec ref: specs/007-sales-management/data-model.md §Master Data Entities
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from modules.sales.schemas.base import SalesBaseSchema

# ---------------------------------------------------------------------------
# Customer Category
# ---------------------------------------------------------------------------


class CustomerCategoryCreate(SalesBaseSchema):
    """Request body for creating a customer category."""

    code: str = Field(
        ..., min_length=1, max_length=20, description="Unique code per company"
    )
    name: str = Field(..., min_length=1, max_length=200, description="Category name")
    description: str | None = Field(None, max_length=2000)
    default_payment_term_id: UUID | None = Field(
        None, description="Default payment term for customers in this category"
    )
    default_credit_limit: Decimal = Field(
        default=Decimal("0"), ge=0, description="Default credit limit"
    )

    @field_validator("code")
    @classmethod
    def code_uppercase(cls, v: str) -> str:
        return v.strip().upper()


class CustomerCategoryUpdate(SalesBaseSchema):
    """Request body for updating a customer category."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    default_payment_term_id: UUID | None = None
    default_credit_limit: Decimal | None = Field(None, ge=0)
    is_active: bool | None = None


class CustomerCategoryRead(SalesBaseSchema):
    """Response schema for a single customer category."""

    id: UUID
    company_id: UUID
    code: str
    name: str
    description: str | None
    default_payment_term_id: UUID | None
    default_credit_limit: Decimal
    is_active: bool


# ---------------------------------------------------------------------------
# Customer Group
# ---------------------------------------------------------------------------


class CustomerGroupCreate(SalesBaseSchema):
    """Request body for creating a customer group."""

    code: str = Field(
        ..., min_length=1, max_length=20, description="Unique code per company"
    )
    name: str = Field(..., min_length=1, max_length=200, description="Group name")
    description: str | None = Field(None, max_length=2000)

    @field_validator("code")
    @classmethod
    def code_uppercase(cls, v: str) -> str:
        return v.strip().upper()


class CustomerGroupUpdate(SalesBaseSchema):
    """Request body for updating a customer group."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    is_active: bool | None = None


class CustomerGroupRead(SalesBaseSchema):
    """Response schema for a single customer group."""

    id: UUID
    company_id: UUID
    code: str
    name: str
    description: str | None
    is_active: bool


# ---------------------------------------------------------------------------
# Sales Payment Term
# ---------------------------------------------------------------------------


class SalesPaymentTermCreate(SalesBaseSchema):
    """Request body for creating a sales payment term."""

    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=100)
    due_days: int = Field(..., ge=0, description="Days until payment is due")
    discount_days: int | None = Field(
        None, ge=0, description="Early-payment discount window"
    )
    discount_percent: Decimal | None = Field(
        None, ge=0, le=100, description="Early-payment discount percentage"
    )
    description: str | None = None

    @field_validator("code")
    @classmethod
    def code_uppercase(cls, v: str) -> str:
        return v.strip().upper()


class SalesPaymentTermUpdate(SalesBaseSchema):
    """Request body for updating a sales payment term."""

    name: str | None = Field(None, min_length=1, max_length=100)
    due_days: int | None = Field(None, ge=0)
    discount_days: int | None = Field(None, ge=0)
    discount_percent: Decimal | None = Field(None, ge=0, le=100)
    description: str | None = None
    is_active: bool | None = None


class SalesPaymentTermRead(SalesBaseSchema):
    """Response schema for a sales payment term."""

    id: UUID
    company_id: UUID
    code: str
    name: str
    due_days: int
    discount_days: int | None
    discount_percent: Decimal | None
    description: str | None
    is_active: bool


# ---------------------------------------------------------------------------
# Sales Reason Code
# ---------------------------------------------------------------------------


class SalesReasonCodeCreate(SalesBaseSchema):
    """Request body for creating a sales reason code."""

    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=200)
    reason_type: str = Field(
        ..., description="RETURN / CANCELLATION / REJECTION / GENERAL"
    )

    @field_validator("code")
    @classmethod
    def code_uppercase(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("reason_type")
    @classmethod
    def reason_type_uppercase(cls, v: str) -> str:
        v = v.strip().upper()
        valid = ("RETURN", "CANCELLATION", "REJECTION", "GENERAL")
        if v not in valid:
            raise ValueError(f"reason_type must be one of {valid}")
        return v


class SalesReasonCodeUpdate(SalesBaseSchema):
    """Request body for updating a sales reason code."""

    name: str | None = Field(None, min_length=1, max_length=200)
    is_active: bool | None = None


class SalesReasonCodeRead(SalesBaseSchema):
    """Response schema for a sales reason code."""

    id: UUID
    company_id: UUID
    code: str
    name: str
    reason_type: str
    is_active: bool


# ---------------------------------------------------------------------------
# Sales Configuration
# ---------------------------------------------------------------------------


class SalesConfigurationRead(SalesBaseSchema):
    """Response schema for company sales configuration."""

    id: UUID
    company_id: UUID
    default_quotation_validity_days: int
    quotation_expiry_warning_days: int
    auto_approve_threshold: Decimal | None
    minimum_margin_percentage: Decimal | None
    credit_warning_threshold: Decimal
    reservation_expiry_hours: int
    require_quotation_before_order: bool
    tax_inclusive_pricing: bool


class SalesConfigurationUpdate(SalesBaseSchema):
    """Request body for updating company sales configuration."""

    default_quotation_validity_days: int | None = Field(None, ge=1)
    quotation_expiry_warning_days: int | None = Field(None, ge=0)
    auto_approve_threshold: Decimal | None = Field(None, ge=0)
    minimum_margin_percentage: Decimal | None = Field(None, ge=0, le=100)
    credit_warning_threshold: Decimal | None = Field(None, ge=0, le=100)
    reservation_expiry_hours: int | None = Field(None, ge=1)
    require_quotation_before_order: bool | None = None
    tax_inclusive_pricing: bool | None = None


# ---------------------------------------------------------------------------
# Feature Flag
# ---------------------------------------------------------------------------


class SalesFeatureFlagRead(SalesBaseSchema):
    """Response schema for a sales feature flag state."""

    flag_key: str
    label: str
    description: str
    is_enabled: bool
    is_overridden: bool
    default_enabled: bool


class SalesFeatureFlagUpdate(SalesBaseSchema):
    """Request body for updating a sales feature flag."""

    is_enabled: bool
    description: str | None = None

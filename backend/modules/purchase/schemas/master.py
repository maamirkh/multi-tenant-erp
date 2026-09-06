"""Pydantic schemas for purchase master data entities.

Covers:
  - SupplierCategory (create, update, read, list)
  - PaymentTerms (create, update, read)
  - PurchaseReasonCode (create, update, read)
  - PurchasePolicy (read, update)
  - FeatureFlag (read, update)

Spec ref: specs/006-purchase-management/data-model.md §Master Data Entities
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from modules.purchase.schemas.base import PurchaseBaseSchema

# ---------------------------------------------------------------------------
# Supplier Category
# ---------------------------------------------------------------------------


class SupplierCategoryCreate(PurchaseBaseSchema):
    """Request body for creating a supplier category."""

    code: str = Field(
        ..., min_length=1, max_length=20, description="Unique code per company"
    )
    name: str = Field(..., min_length=1, max_length=200, description="Category name")
    parent_id: UUID | None = Field(
        None, description="Parent category ID (null for root)"
    )
    description: str | None = Field(None, max_length=2000)

    @field_validator("code")
    @classmethod
    def code_uppercase(cls, v: str) -> str:
        return v.strip().upper()


class SupplierCategoryUpdate(PurchaseBaseSchema):
    """Request body for updating a supplier category."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None


class SupplierCategoryRead(PurchaseBaseSchema):
    """Response schema for a single supplier category."""

    id: UUID
    company_id: UUID
    code: str
    name: str
    parent_id: UUID | None
    description: str | None
    status: str


class SupplierCategoryList(PurchaseBaseSchema):
    """Lightweight schema for category list items."""

    id: UUID
    code: str
    name: str
    parent_id: UUID | None
    status: str


# ---------------------------------------------------------------------------
# Payment Terms
# ---------------------------------------------------------------------------


class PaymentTermsCreate(PurchaseBaseSchema):
    """Request body for creating payment terms."""

    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=100)
    net_days: int = Field(..., ge=0, description="Days until payment is due")
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


class PaymentTermsUpdate(PurchaseBaseSchema):
    """Request body for updating payment terms."""

    name: str | None = Field(None, min_length=1, max_length=100)
    net_days: int | None = Field(None, ge=0)
    discount_days: int | None = Field(None, ge=0)
    discount_percent: Decimal | None = Field(None, ge=0, le=100)
    description: str | None = None
    is_active: bool | None = None


class PaymentTermsRead(PurchaseBaseSchema):
    """Response schema for payment terms."""

    id: UUID
    company_id: UUID
    code: str
    name: str
    net_days: int
    discount_days: int | None
    discount_percent: Decimal | None
    description: str | None
    is_active: bool


# ---------------------------------------------------------------------------
# Purchase Reason Code
# ---------------------------------------------------------------------------


class PurchaseReasonCodeCreate(PurchaseBaseSchema):
    """Request body for creating a purchase reason code."""

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


class PurchaseReasonCodeUpdate(PurchaseBaseSchema):
    """Request body for updating a purchase reason code."""

    name: str | None = Field(None, min_length=1, max_length=200)
    is_active: bool | None = None


class PurchaseReasonCodeRead(PurchaseBaseSchema):
    """Response schema for a purchase reason code."""

    id: UUID
    company_id: UUID
    code: str
    name: str
    reason_type: str
    is_active: bool


# ---------------------------------------------------------------------------
# Purchase Policy
# ---------------------------------------------------------------------------


class PurchasePolicyRead(PurchaseBaseSchema):
    """Response schema for company purchase policy."""

    id: UUID
    company_id: UUID
    direct_po_allowed: bool
    pr_approval_required: bool
    po_approval_required: bool
    over_receipt_policy: str
    credit_limit_mode: str
    ppv_alert_threshold_percent: Decimal
    supplier_rating_window: int


class PurchasePolicyUpdate(PurchaseBaseSchema):
    """Request body for updating company purchase policy."""

    direct_po_allowed: bool | None = None
    pr_approval_required: bool | None = None
    po_approval_required: bool | None = None
    over_receipt_policy: str | None = Field(None, description="BLOCK / WARN / ALLOW")
    credit_limit_mode: str | None = Field(None, description="BLOCK / WARN / OFF")
    ppv_alert_threshold_percent: Decimal | None = Field(None, ge=0, le=100)
    supplier_rating_window: int | None = Field(None, ge=1)

    @field_validator("over_receipt_policy")
    @classmethod
    def validate_over_receipt(cls, v: str | None) -> str | None:
        if v is not None and v not in ("BLOCK", "WARN", "ALLOW"):
            raise ValueError("over_receipt_policy must be BLOCK, WARN, or ALLOW")
        return v

    @field_validator("credit_limit_mode")
    @classmethod
    def validate_credit_limit(cls, v: str | None) -> str | None:
        if v is not None and v not in ("BLOCK", "WARN", "OFF"):
            raise ValueError("credit_limit_mode must be BLOCK, WARN, or OFF")
        return v


# ---------------------------------------------------------------------------
# Feature Flag
# ---------------------------------------------------------------------------


class PurchaseFeatureFlagRead(PurchaseBaseSchema):
    """Response schema for a purchase feature flag state."""

    flag_key: str
    label: str
    description: str
    is_enabled: bool
    is_overridden: bool
    default_enabled: bool


class PurchaseFeatureFlagUpdate(PurchaseBaseSchema):
    """Request body for updating a purchase feature flag."""

    is_enabled: bool
    description: str | None = None

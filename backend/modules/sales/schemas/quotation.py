"""Pydantic v2 schemas for Sales Quotation aggregate — Phase 3.

Schemas:
  QuotationLineCreate / QuotationLineUpdate / QuotationLineRead
  QuotationRevisionRead
  SalesQuotationCreate / SalesQuotationUpdate / SalesQuotationRead
  QuotationSendRequest / QuotationAcceptRequest / QuotationRejectRequest
  QuotationCancelRequest / QuotationConvertResponse

Task: T092
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# QuotationLine schemas
# ---------------------------------------------------------------------------


class QuotationLineCreate(BaseModel):
    """Schema for creating a quotation line."""

    product_id: UUID | None = None
    description: str = Field(..., min_length=1, max_length=500)
    quantity: Decimal = Field(..., gt=0)
    unit_of_measure: str = Field(default="EA", max_length=20)
    unit_price: Decimal = Field(..., ge=0)
    discount_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    tax_category: str | None = Field(default=None, max_length=20)
    notes: str | None = None


class QuotationLineUpdate(BaseModel):
    """Schema for updating a quotation line (all fields optional)."""

    description: str | None = Field(default=None, min_length=1, max_length=500)
    quantity: Decimal | None = Field(default=None, gt=0)
    unit_of_measure: str | None = Field(default=None, max_length=20)
    unit_price: Decimal | None = Field(default=None, ge=0)
    discount_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    tax_category: str | None = None
    notes: str | None = None


class QuotationLineRead(BaseModel):
    """Schema for reading a quotation line."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    quotation_id: UUID
    line_number: int
    product_id: UUID | None
    description: str
    quantity: Decimal
    unit_of_measure: str
    unit_price: Decimal
    discount_percentage: Decimal | None
    discount_amount: Decimal | None
    tax_category: str | None
    extended_amount: Decimal
    notes: str | None


# ---------------------------------------------------------------------------
# QuotationRevision schemas
# ---------------------------------------------------------------------------


class QuotationRevisionRead(BaseModel):
    """Schema for reading a quotation revision snapshot."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    quotation_id: UUID
    revision_number: int
    snapshot: dict[str, Any]
    modified_by: UUID
    modified_at: str
    change_summary: str | None


# ---------------------------------------------------------------------------
# SalesQuotation schemas
# ---------------------------------------------------------------------------


class SalesQuotationCreate(BaseModel):
    """Schema for creating a new sales quotation."""

    customer_id: UUID
    quotation_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    validity_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    currency_code: str = Field(default="USD", min_length=3, max_length=3)
    payment_term_id: UUID | None = None
    shipping_address_id: UUID | None = None
    billing_address_id: UUID | None = None
    sales_rep_id: UUID
    discount_type: str | None = Field(default=None, pattern=r"^(PERCENTAGE|AMOUNT)$")
    discount_value: Decimal | None = Field(default=None, ge=0)
    internal_notes: str | None = None
    customer_notes: str | None = None
    lines: list[QuotationLineCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_validity_date(self) -> SalesQuotationCreate:
        if self.validity_date < self.quotation_date:
            raise ValueError("validity_date must be >= quotation_date")
        return self


class SalesQuotationUpdate(BaseModel):
    """Schema for updating a DRAFT quotation (all fields optional)."""

    validity_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    payment_term_id: UUID | None = None
    shipping_address_id: UUID | None = None
    billing_address_id: UUID | None = None
    sales_rep_id: UUID | None = None
    discount_type: str | None = Field(default=None, pattern=r"^(PERCENTAGE|AMOUNT)$")
    discount_value: Decimal | None = Field(default=None, ge=0)
    internal_notes: str | None = None
    customer_notes: str | None = None


class SalesQuotationRead(BaseModel):
    """Schema for reading a sales quotation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    quotation_number: str
    customer_id: UUID
    quotation_date: str
    validity_date: str
    currency_code: str
    payment_term_id: UUID | None
    shipping_address_id: UUID | None
    billing_address_id: UUID | None
    sales_rep_id: UUID
    revision_number: int
    status: str
    subtotal: Decimal
    discount_type: str | None
    discount_value: Decimal | None
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    internal_notes: str | None
    customer_notes: str | None
    converted_order_id: UUID | None
    version: int
    lines: list[QuotationLineRead] = Field(default_factory=list)


class SalesQuotationListItem(BaseModel):
    """Lightweight schema for quotation list responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    quotation_number: str
    customer_id: UUID
    quotation_date: str
    validity_date: str
    currency_code: str
    status: str
    total_amount: Decimal
    revision_number: int


# ---------------------------------------------------------------------------
# State transition request schemas
# ---------------------------------------------------------------------------


class QuotationSendRequest(BaseModel):
    """Request to send a DRAFT quotation to the customer."""

    notes: str | None = None


class QuotationAcceptRequest(BaseModel):
    """Request to mark a SENT_TO_CUSTOMER quotation as ACCEPTED."""

    notes: str | None = None


class QuotationRejectRequest(BaseModel):
    """Request to mark a SENT_TO_CUSTOMER quotation as REJECTED."""

    reason: str = Field(..., min_length=1, max_length=1000)


class QuotationCancelRequest(BaseModel):
    """Request to cancel a quotation from any live status."""

    reason: str = Field(..., min_length=1, max_length=1000)


class QuotationConvertResponse(BaseModel):
    """Response after converting an ACCEPTED quotation to a Sales Order."""

    quotation_id: UUID
    quotation_number: str
    order_id: UUID
    order_number: str
    message: str = "Quotation successfully converted to Sales Order"

"""Pydantic v2 schemas for Sales Order aggregate — Phase 4.

Schemas:
  OrderLineCreate / OrderLineUpdate / OrderLineRead
  SalesOrderCreate / SalesOrderUpdate / SalesOrderRead / SalesOrderListItem
  OrderSubmitRequest / OrderApproveRequest / OrderRejectRequest / OrderCancelRequest
  SalesApprovalMatrixCreate / SalesApprovalMatrixRead
  SalesMatrixRuleCreate / SalesMatrixRuleRead
  SalesApprovalRecordRead
  ApprovalInboxItem

Task: T117
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# OrderLine schemas
# ---------------------------------------------------------------------------


class OrderLineCreate(BaseModel):
    """Schema for adding a line to a Sales Order."""

    product_id: UUID | None = None
    description: str = Field(..., min_length=1, max_length=500)
    quantity_ordered: Decimal = Field(..., gt=0)
    unit_of_measure: str = Field(default="EA", max_length=20)
    unit_price: Decimal = Field(..., ge=0)
    cost_price: Decimal | None = Field(default=None, ge=0)
    discount_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    tax_category: str | None = Field(default=None, max_length=20)
    tax_rate: Decimal | None = Field(default=None, ge=0)
    price_source: str = Field(default="MANUAL", max_length=20)
    notes: str | None = None


class OrderLineUpdate(BaseModel):
    """Schema for updating an order line (all fields optional)."""

    description: str | None = Field(default=None, min_length=1, max_length=500)
    quantity_ordered: Decimal | None = Field(default=None, gt=0)
    unit_of_measure: str | None = Field(default=None, max_length=20)
    unit_price: Decimal | None = Field(default=None, ge=0)
    cost_price: Decimal | None = Field(default=None, ge=0)
    discount_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    tax_category: str | None = None
    tax_rate: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class OrderLineRead(BaseModel):
    """Schema for reading an order line."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    order_id: UUID
    line_number: int
    product_id: UUID | None
    description: str
    quantity_ordered: Decimal
    quantity_delivered: Decimal
    unit_of_measure: str
    unit_price: Decimal
    cost_price: Decimal | None
    discount_percentage: Decimal | None
    discount_amount: Decimal | None
    tax_category: str | None
    tax_rate: Decimal | None
    tax_amount: Decimal
    extended_amount: Decimal
    delivery_status: str
    price_source: str
    notes: str | None


# ---------------------------------------------------------------------------
# SalesOrder schemas
# ---------------------------------------------------------------------------


class SalesOrderCreate(BaseModel):
    """Schema for creating a Sales Order (direct or from quotation)."""

    customer_id: UUID
    quotation_id: UUID | None = None
    order_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    required_delivery_date: str | None = Field(
        default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    currency_code: str = Field(default="USD", min_length=3, max_length=3)
    payment_term_id: UUID | None = None
    shipping_address_id: UUID | None = None
    billing_address_id: UUID | None = None
    sales_rep_id: UUID
    priority: str = Field(default="NORMAL", pattern="^(LOW|NORMAL|HIGH|URGENT)$")
    internal_notes: str | None = None
    customer_notes: str | None = None
    lines: list[OrderLineCreate] = Field(default_factory=list)


class SalesOrderUpdate(BaseModel):
    """Schema for updating a DRAFT Sales Order (all fields optional)."""

    required_delivery_date: str | None = Field(
        default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    payment_term_id: UUID | None = None
    shipping_address_id: UUID | None = None
    billing_address_id: UUID | None = None
    priority: str | None = Field(default=None, pattern="^(LOW|NORMAL|HIGH|URGENT)$")
    internal_notes: str | None = None
    customer_notes: str | None = None


class SalesOrderRead(BaseModel):
    """Schema for reading a Sales Order with full details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    order_number: str
    customer_id: UUID
    quotation_id: UUID | None
    order_date: str
    required_delivery_date: str | None
    currency_code: str
    payment_term_id: UUID | None
    shipping_address_id: UUID | None
    billing_address_id: UUID | None
    sales_rep_id: UUID
    priority: str
    status: str
    subtotal: Decimal
    discount_type: str | None
    discount_value: Decimal | None
    discount_amount: Decimal
    tax_amount: Decimal
    charges_amount: Decimal
    total_amount: Decimal
    internal_notes: str | None
    customer_notes: str | None
    cancellation_reason: str | None
    approval_version: int
    version: int
    lines: list[OrderLineRead] = Field(default_factory=list)


class SalesOrderListItem(BaseModel):
    """Lightweight schema for order list views."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_number: str
    customer_id: UUID
    order_date: str
    status: str
    priority: str
    total_amount: Decimal
    currency_code: str
    sales_rep_id: UUID
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# State transition request schemas
# ---------------------------------------------------------------------------


class OrderSubmitRequest(BaseModel):
    """Request body for submitting an order for approval."""

    submitted_by: UUID


class OrderApproveRequest(BaseModel):
    """Request body for approving an order."""

    approver_id: UUID
    comments: str | None = None


class OrderRejectRequest(BaseModel):
    """Request body for rejecting an order."""

    approver_id: UUID
    rejection_reason: str = Field(..., min_length=1)
    comments: str | None = None


class OrderCancelRequest(BaseModel):
    """Request body for cancelling an order."""

    cancellation_reason: str = Field(..., min_length=1)
    cancelled_by: UUID


class OrderCloseRequest(BaseModel):
    """Request body for closing an invoiced order."""

    closed_by: UUID


# ---------------------------------------------------------------------------
# ApprovalMatrix schemas
# ---------------------------------------------------------------------------


class SalesMatrixRuleCreate(BaseModel):
    """Schema for adding a rule to an approval matrix."""

    approval_level: int = Field(..., ge=1)
    min_amount: Decimal = Field(default=Decimal("0"), ge=0)
    max_amount: Decimal | None = Field(default=None, ge=0)
    approver_role: str | None = Field(default=None, max_length=50)
    approver_user_id: UUID | None = None
    customer_category_id: UUID | None = None
    auto_approve: bool = False


class SalesMatrixRuleRead(BaseModel):
    """Schema for reading an approval matrix rule."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    matrix_id: UUID
    approval_level: int
    min_amount: Decimal
    max_amount: Decimal | None
    approver_role: str | None
    approver_user_id: UUID | None
    customer_category_id: UUID | None
    auto_approve: bool


class SalesApprovalMatrixCreate(BaseModel):
    """Schema for creating an approval matrix."""

    name: str = Field(..., min_length=1, max_length=200)
    document_type: str = Field(..., pattern="^(SALES_ORDER|SALES_RETURN)$")
    is_active: bool = True
    rules: list[SalesMatrixRuleCreate] = Field(default_factory=list)


class SalesApprovalMatrixUpdate(BaseModel):
    """Schema for updating an approval matrix."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None


class SalesApprovalMatrixRead(BaseModel):
    """Schema for reading an approval matrix with its rules."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    name: str
    document_type: str
    is_active: bool
    rules: list[SalesMatrixRuleRead] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# ApprovalRecord schemas
# ---------------------------------------------------------------------------


class SalesApprovalRecordRead(BaseModel):
    """Schema for reading an approval record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    document_type: str
    document_id: UUID
    approval_level: int
    approver_id: UUID
    decision: str
    comments: str | None
    decided_at: str | None
    approval_version: int


class ApprovalInboxItem(BaseModel):
    """Approval inbox item combining record with order summary."""

    model_config = ConfigDict(from_attributes=True)

    record_id: UUID
    document_type: str
    document_id: UUID
    order_number: str | None = None
    customer_id: str | None = None
    total_amount: str | None = None
    approval_level: int
    submitted_at: str | None = None

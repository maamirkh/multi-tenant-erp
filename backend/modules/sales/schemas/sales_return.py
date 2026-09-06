"""Sales Return Pydantic schemas — Phase 7.

Schemas:
  ReturnLineCreate      — create a return line
  ReturnLineRead        — full line response
  SalesReturnCreate     — create a new return (DRAFT)
  SalesReturnRead       — full return response
  SalesReturnListItem   — minimal representation for list views
  SalesReturnListResponse — paginated list wrapper
  ReturnSubmitRequest   — submit for approval
  ReturnApproveRequest  — approve the return
  ReturnRejectRequest   — reject the return
  ReturnReceiveRequest  — receive returned goods
  ReturnCompleteRequest — complete with resolution

Spec ref: specs/007-sales-management/spec.md §19 Sales Returns
Task: T192
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import field_validator

from modules.sales.schemas.base import SalesBaseSchema

# ---------------------------------------------------------------------------
# ReturnLine schemas
# ---------------------------------------------------------------------------


class ReturnLineCreate(SalesBaseSchema):
    product_id: UUID | None = None
    description: str
    quantity_returned: Decimal
    unit_price: Decimal
    condition: Literal["NEW", "USED", "DAMAGED", "DEFECTIVE"] = "USED"
    reason_code_id: UUID | None = None

    @field_validator("quantity_returned")
    @classmethod
    def qty_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("quantity_returned must be positive")
        return v

    @field_validator("unit_price")
    @classmethod
    def unit_price_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("unit_price cannot be negative")
        return v


class ReturnLineRead(SalesBaseSchema):
    id: UUID
    company_id: UUID
    return_id: str
    product_id: str | None
    description: str
    quantity_returned: Decimal
    quantity_accepted: Decimal
    quantity_rejected: Decimal
    unit_price: Decimal
    extended_amount: Decimal
    condition: str
    reason_code_id: str | None
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# SalesReturn schemas
# ---------------------------------------------------------------------------


class SalesReturnCreate(SalesBaseSchema):
    customer_id: UUID
    order_id: UUID | None = None
    invoice_id: UUID | None = None
    return_date: str  # ISO 8601 YYYY-MM-DD
    reason_code_id: UUID
    reason_description: str | None = None
    resolution_type: Literal["CREDIT_NOTE", "REPLACEMENT", "REFUND_READINESS"] = (
        "CREDIT_NOTE"
    )
    lines: list[ReturnLineCreate]
    internal_notes: str | None = None

    @field_validator("lines")
    @classmethod
    def lines_not_empty(cls, v: list[ReturnLineCreate]) -> list[ReturnLineCreate]:
        if not v:
            raise ValueError("At least one return line is required")
        return v


class SalesReturnRead(SalesBaseSchema):
    id: UUID
    company_id: UUID
    return_number: str
    customer_id: str
    order_id: str | None
    invoice_id: str | None
    replacement_order_id: str | None
    return_date: str
    reason_code_id: str
    reason_description: str | None
    resolution_type: str
    status: str
    approval_version: int
    received_by: str | None
    received_at: str | None
    credit_note_amount: Decimal | None
    internal_notes: str | None
    version: int
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None
    lines: list[ReturnLineRead] = []


class SalesReturnListItem(SalesBaseSchema):
    id: UUID
    return_number: str
    customer_id: str
    order_id: str | None
    return_date: str
    resolution_type: str
    status: str
    created_at: datetime | None


class SalesReturnListResponse(SalesBaseSchema):
    items: list[SalesReturnListItem]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Action request schemas
# ---------------------------------------------------------------------------


class ReturnSubmitRequest(SalesBaseSchema):
    pass  # no extra fields required; submitter is the current user


class ReturnApproveRequest(SalesBaseSchema):
    auto_approved: bool = False


class ReturnRejectRequest(SalesBaseSchema):
    rejection_reason: str

    @field_validator("rejection_reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("rejection_reason cannot be empty")
        return v


class ReturnReceiveRequest(SalesBaseSchema):
    """Payload for recording receipt of returned goods.

    accepted_lines: list of {line_id: UUID, quantity_accepted: Decimal, quantity_rejected: Decimal}
    """

    accepted_lines: list[ReturnLineReceiptItem]


class ReturnLineReceiptItem(SalesBaseSchema):
    line_id: UUID
    quantity_accepted: Decimal
    quantity_rejected: Decimal

    @field_validator("quantity_accepted", "quantity_rejected")
    @classmethod
    def non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Quantities cannot be negative")
        return v


# Fix forward reference
ReturnReceiveRequest.model_rebuild()


class ReturnCompleteRequest(SalesBaseSchema):
    credit_note_amount: Decimal | None = (
        None  # required when resolution_type=CREDIT_NOTE
    )
    notes: str | None = None

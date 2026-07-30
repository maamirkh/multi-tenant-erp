"""Purchase Request Pydantic schemas — Phase 4.

Schemas:
  PRLineCreate / PRLineUpdate / PRLineRead
  PurchaseRequestCreate / PurchaseRequestUpdate / PurchaseRequestRead
  PurchaseRequestListRead  — lightweight list representation
  PRSubmitRequest          — payload for submit action
  PRApproveRequest         — payload for approve action (delegates to approval engine)
  PRRejectRequest          — payload for reject action
  PRCancelRequest          — payload for cancel action

Spec ref: specs/006-purchase-management/spec.md §23 Functional Requirements
Task: T110
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from modules.purchase.schemas.base import PaginatedResponse, PurchaseBaseSchema

PR_STATUSES = (
    "DRAFT",
    "SUBMITTED",
    "UNDER_REVIEW",
    "APPROVED",
    "REJECTED",
    "CANCELLED",
)


# ---------------------------------------------------------------------------
# PRLine schemas
# ---------------------------------------------------------------------------


class PRLineCreate(PurchaseBaseSchema):
    product_id: UUID | None = Field(
        None, description="Optional product catalog reference"
    )
    product_description: str = Field(..., min_length=1, max_length=500)
    quantity: Decimal = Field(..., gt=0, description="Must be > 0")
    uom_id: UUID | None = Field(None, description="Optional unit of measure")
    estimated_unit_cost: Decimal = Field(Decimal("0.0000"), ge=0)
    notes: str | None = Field(None, max_length=2000)


class PRLineUpdate(PurchaseBaseSchema):
    product_id: UUID | None = None
    product_description: str | None = Field(None, min_length=1, max_length=500)
    quantity: Decimal | None = Field(None, gt=0)
    uom_id: UUID | None = None
    estimated_unit_cost: Decimal | None = Field(None, ge=0)
    notes: str | None = None


class PRLineRead(PurchaseBaseSchema):
    id: UUID
    company_id: UUID
    pr_id: str
    line_number: int
    product_id: str | None = None
    product_description: str
    quantity: Decimal
    uom_id: str | None = None
    estimated_unit_cost: Decimal
    estimated_line_total: Decimal
    notes: str | None = None


# ---------------------------------------------------------------------------
# PurchaseRequest schemas
# ---------------------------------------------------------------------------


class PurchaseRequestCreate(PurchaseBaseSchema):
    title: str = Field(..., min_length=1, max_length=300)
    department: str | None = Field(None, max_length=100)
    required_by_date: date | None = None
    notes: str | None = Field(None, max_length=5000)
    currency_code: str = Field("USD", min_length=3, max_length=3)
    lines: list[PRLineCreate] = Field(default_factory=list)

    @field_validator("currency_code")
    @classmethod
    def currency_code_upper(cls, v: str) -> str:
        return v.upper()


class PurchaseRequestUpdate(PurchaseBaseSchema):
    title: str | None = Field(None, min_length=1, max_length=300)
    department: str | None = Field(None, max_length=100)
    required_by_date: date | None = None
    notes: str | None = None
    currency_code: str | None = Field(None, min_length=3, max_length=3)

    @field_validator("currency_code")
    @classmethod
    def currency_code_upper(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class PurchaseRequestRead(PurchaseBaseSchema):
    id: UUID
    company_id: UUID
    pr_number: str
    title: str
    status: str
    requestor_id: str
    department: str | None = None
    required_by_date: date | None = None
    notes: str | None = None
    total_estimated_cost: Decimal
    currency_code: str
    converted_to_po_id: str | None = None
    branch_id: str | None = None
    lines: list[PRLineRead] = Field(default_factory=list)


class PurchaseRequestListRead(PurchaseBaseSchema):
    """Lightweight schema for list responses (no lines)."""

    id: UUID
    company_id: UUID
    pr_number: str
    title: str
    status: str
    requestor_id: str
    department: str | None = None
    required_by_date: date | None = None
    total_estimated_cost: Decimal
    currency_code: str
    converted_to_po_id: str | None = None


# ---------------------------------------------------------------------------
# Action request schemas
# ---------------------------------------------------------------------------


class PRSubmitRequest(PurchaseBaseSchema):
    """Payload for the submit action (DRAFT → SUBMITTED)."""

    notes: str | None = Field(None, description="Optional submission notes")


class PRCancelRequest(PurchaseBaseSchema):
    """Payload for the cancel action."""

    reason: str | None = Field(None, max_length=500, description="Cancellation reason")


# Type alias for paginated list
PurchaseRequestPage = PaginatedResponse[PurchaseRequestListRead]

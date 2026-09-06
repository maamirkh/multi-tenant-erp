"""Pydantic schemas for Phase 6 — Inventory Adjustment endpoints.

Spec ref: specs/005-inventory-management/spec.md §15 / FR-IO-012
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# Request schemas
# =============================================================================


class AdjustmentCreateRequest(BaseModel):
    """Create a new inventory adjustment (DRAFT)."""

    product_id: UUID = Field(..., description="Product being adjusted")
    warehouse_id: UUID = Field(..., description="Warehouse where stock is adjusted")
    movement_type: Literal["ADJUSTMENT_IN", "ADJUSTMENT_OUT"] = Field(
        ..., description="Direction: IN increases stock, OUT decreases stock"
    )
    quantity: str = Field(..., description="Adjustment quantity (positive value)")
    variant_id: UUID | None = Field(
        None, description="Product variant (null = base product)"
    )
    reason_code_id: UUID | None = Field(
        None, description="Reason code for this adjustment"
    )
    unit_cost: str | None = Field(None, description="Unit cost at time of adjustment")
    currency_code: str | None = Field(
        None, max_length=3, description="ISO 4217 currency code"
    )
    notes: str | None = Field(
        None, max_length=2000, description="Adjustment justification"
    )

    @field_validator("quantity", "unit_cost", mode="before")
    @classmethod
    def coerce_numeric(cls, v: object) -> object:
        return v  # Passed as string; Decimal conversion happens in service


class AdjustmentSubmitRequest(BaseModel):
    """Submit a DRAFT adjustment for approval (or auto-approve if flag disabled)."""

    # No additional fields required; actor is taken from auth token


class AdjustmentApproveRequest(BaseModel):
    """Approve a PENDING_APPROVAL adjustment."""

    # No additional fields; approver identity from auth token


class AdjustmentRejectRequest(BaseModel):
    """Reject a PENDING_APPROVAL adjustment."""

    rejection_reason: str = Field(
        ..., min_length=1, max_length=2000, description="Mandatory reason for rejection"
    )


# =============================================================================
# Response schemas
# =============================================================================


class AdjustmentResponse(BaseModel):
    """Full adjustment response payload."""

    id: UUID
    company_id: UUID
    product_id: str
    variant_id: str | None
    warehouse_id: str
    reason_code_id: str | None
    movement_type: str
    quantity: str
    unit_cost: str | None
    currency_code: str | None
    notes: str | None
    status: str
    version: int
    old_quantity: str | None
    new_quantity: str | None
    submitted_by: str | None
    approved_by: str | None
    rejected_by: str | None
    rejection_reason: str | None
    reference_movement_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator(
        "quantity", "unit_cost", "old_quantity", "new_quantity", mode="before"
    )
    @classmethod
    def coerce_decimal_to_str(cls, v: object) -> object:
        if v is None:
            return v
        return str(v)

    @classmethod
    def from_orm(cls, obj: object) -> AdjustmentResponse:
        return cls.model_validate(obj)

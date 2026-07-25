"""Pydantic schemas for Phase 7 — Stock Transfers & Reservations.

Spec ref: specs/005-inventory-management/spec.md §16 / FR-IO-013
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# Transfer request schemas
# =============================================================================


class TransferLineRequest(BaseModel):
    """One line in a stock transfer create request."""

    product_id: UUID = Field(..., description="Product to transfer")
    variant_id: UUID | None = Field(None, description="Variant (null = base product)")
    quantity: str = Field(..., description="Quantity to transfer (positive)")
    unit_cost: str | None = Field(None, description="Unit cost at time of transfer")
    currency_code: str | None = Field(
        None, max_length=3, description="ISO 4217 currency code"
    )


class TransferCreateRequest(BaseModel):
    """Create a new DRAFT stock transfer."""

    source_warehouse_id: UUID = Field(..., description="Source warehouse")
    destination_warehouse_id: UUID = Field(..., description="Destination warehouse")
    lines: list[TransferLineRequest] = Field(
        ..., min_length=1, description="At least one transfer line required"
    )
    notes: str | None = Field(None, max_length=2000)
    reference_no: str | None = Field(None, max_length=100)


class TransferCancelRequest(BaseModel):
    """Cancel a transfer — reason is mandatory."""

    cancelled_reason: str = Field(
        ..., min_length=1, max_length=2000, description="Reason for cancellation"
    )


# =============================================================================
# Reservation request schemas
# =============================================================================


class StockReserveRequest(BaseModel):
    """Reserve stock against a product+warehouse combination."""

    product_id: UUID = Field(..., description="Product to reserve")
    warehouse_id: UUID = Field(..., description="Warehouse to reserve from")
    quantity: str = Field(..., description="Quantity to reserve (positive)")
    variant_id: UUID | None = Field(None, description="Variant (null = base product)")
    reference_type: str | None = Field(
        None, max_length=50, description="e.g. SALES_ORDER"
    )
    reference_id: str | None = Field(None, description="ID of the referencing document")


class StockReleaseRequest(BaseModel):
    """Release a previously reserved stock quantity."""

    product_id: UUID = Field(..., description="Product to release reservation for")
    warehouse_id: UUID = Field(..., description="Warehouse")
    quantity: str = Field(..., description="Quantity to release (positive)")
    variant_id: UUID | None = Field(None, description="Variant (null = base product)")


# =============================================================================
# Response schemas
# =============================================================================


class TransferLineResponse(BaseModel):
    """Response for a single transfer line."""

    id: UUID
    transfer_id: str
    product_id: str
    variant_id: str | None
    quantity: str
    unit_cost: str | None
    currency_code: str | None
    source_movement_id: str | None
    destination_movement_id: str | None
    reversal_movement_id: str | None

    model_config = {"from_attributes": True}

    @field_validator("quantity", "unit_cost", mode="before")
    @classmethod
    def coerce_decimal_to_str(cls, v: object) -> object:
        if v is None:
            return v
        return str(v)


class TransferResponse(BaseModel):
    """Full transfer response payload."""

    id: UUID
    company_id: UUID
    status: str
    version: int
    source_warehouse_id: str
    destination_warehouse_id: str
    reference_no: str | None
    notes: str | None
    dispatched_at: datetime | None
    received_at: datetime | None
    cancelled_at: datetime | None
    cancelled_reason: str | None
    lines: list[TransferLineResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StockReservationResponse(BaseModel):
    """Response after reserve or release operation."""

    product_id: str
    warehouse_id: str
    variant_id: str | None
    qty_reserved: str
    qty_on_hand: str
    available_quantity: str
    message: str

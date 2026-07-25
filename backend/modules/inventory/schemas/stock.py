"""Stock Pydantic schemas — request/response models for inventory stock API.

Spec ref: specs/005-inventory-management/spec.md §15
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Movement type / direction literals
# ---------------------------------------------------------------------------

MovementType = Literal[
    "OPENING",
    "PURCHASE_RECEIPT",
    "SALES_ISSUE",
    "ADJUSTMENT_IN",
    "ADJUSTMENT_OUT",
    "TRANSFER_IN",
    "TRANSFER_OUT",
    "RETURN_IN",
    "RETURN_OUT",
    "DAMAGE",
    "WRITE_OFF",
    "SNAPSHOT",
]
Direction = Literal["IN", "OUT"]
SnapshotStatus = Literal["PENDING", "COMPLETED", "FAILED"]


# ---------------------------------------------------------------------------
# Opening stock request
# ---------------------------------------------------------------------------


class OpeningStockRequest(BaseModel):
    """Payload for recording opening/initial stock."""

    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    quantity: Decimal = Field(
        ..., gt=0, description="Quantity to record (must be positive)"
    )
    unit_cost: Decimal | None = Field(
        default=None, ge=0, description="Unit cost for WAC calculation"
    )
    currency_code: str | None = Field(
        default=None, max_length=3, description="ISO 4217 currency code"
    )
    variant_id: uuid.UUID | None = Field(default=None)
    notes: str | None = Field(default=None)
    performed_at: datetime | None = Field(
        default=None, description="Override timestamp for backdating"
    )


# ---------------------------------------------------------------------------
# Adjustment request
# ---------------------------------------------------------------------------


class AdjustmentRequest(BaseModel):
    """Payload for a manual stock adjustment (in or out)."""

    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    movement_type: Literal["ADJUSTMENT_IN", "ADJUSTMENT_OUT"]
    quantity: Decimal = Field(..., gt=0)
    unit_cost: Decimal | None = Field(default=None, ge=0)
    currency_code: str | None = Field(default=None, max_length=3)
    variant_id: uuid.UUID | None = Field(default=None)
    reference_type: str | None = Field(default=None, max_length=50)
    reference_id: uuid.UUID | None = Field(default=None)
    notes: str | None = Field(default=None)
    performed_at: datetime | None = Field(default=None)


# ---------------------------------------------------------------------------
# Stock position response
# ---------------------------------------------------------------------------


class StockPositionResponse(BaseModel):
    """Current stock position for a product+warehouse combination."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    product_id: str
    variant_id: str | None
    warehouse_id: str
    qty_on_hand: Decimal
    qty_reserved: Decimal
    qty_damaged: Decimal
    unit_cost: Decimal | None
    currency_code: str | None
    safety_stock: Decimal
    minimum_stock: Decimal
    maximum_stock: Decimal | None
    reorder_level: Decimal
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Stock movement response
# ---------------------------------------------------------------------------


class StockMovementResponse(BaseModel):
    """Immutable stock ledger entry."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    product_id: str
    variant_id: str | None
    warehouse_id: str
    movement_type: str
    direction: str
    quantity: Decimal
    unit_cost: Decimal | None
    currency_code: str | None
    total_cost: Decimal | None
    reference_type: str | None
    reference_id: str | None
    notes: str | None
    performed_at: datetime
    created_at: datetime


# ---------------------------------------------------------------------------
# Snapshot schemas
# ---------------------------------------------------------------------------


class SnapshotCreateRequest(BaseModel):
    """Payload for triggering an inventory snapshot."""

    snapshot_name: str | None = Field(default=None, max_length=200)


class SnapshotResponse(BaseModel):
    """Inventory snapshot header."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    snapshot_name: str | None
    status: str
    total_products: int
    total_warehouses: int
    created_at: datetime
    updated_at: datetime


class SnapshotLineResponse(BaseModel):
    """One line within an inventory snapshot."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    snapshot_id: str
    product_id: str
    variant_id: str | None
    warehouse_id: str
    qty_on_hand: Decimal
    qty_reserved: Decimal
    qty_damaged: Decimal
    unit_cost: Decimal | None
    currency_code: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Threshold update request
# ---------------------------------------------------------------------------


class ThresholdUpdateRequest(BaseModel):
    """Update stock level thresholds on an existing position."""

    safety_stock: Decimal | None = Field(default=None, ge=0)
    minimum_stock: Decimal | None = Field(default=None, ge=0)
    maximum_stock: Decimal | None = Field(default=None, ge=0)
    reorder_level: Decimal | None = Field(default=None, ge=0)

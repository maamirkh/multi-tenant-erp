"""Pydantic schemas for inventory alerts and reorder rules — Phase 8.

Spec ref: specs/005-inventory-management/spec.md §15 / FR-IO-016
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Literals
# ---------------------------------------------------------------------------

AlertType = Literal["OUT_OF_STOCK", "SAFETY_STOCK_BREACH", "LOW_STOCK", "OVERSTOCK"]
AlertStatus = Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"]
SuggestionStatus = Literal["PENDING", "ACKNOWLEDGED", "CONVERTED"]


# ---------------------------------------------------------------------------
# ReorderRule schemas
# ---------------------------------------------------------------------------


class ReorderRuleCreate(BaseModel):
    """Payload to create a reorder rule for a product."""

    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None
    warehouse_id: uuid.UUID | None = Field(
        default=None,
        description="If None the rule applies to all warehouses (global rule)",
    )
    reorder_level: Decimal = Field(
        ..., ge=0, description="Qty below which a suggestion is triggered"
    )
    reorder_quantity: Decimal = Field(..., gt=0, description="Qty to suggest ordering")
    is_active: bool = True


class ReorderRuleUpdate(BaseModel):
    """Payload to update an existing reorder rule (all fields optional)."""

    reorder_level: Decimal | None = Field(default=None, ge=0)
    reorder_quantity: Decimal | None = Field(default=None, gt=0)
    is_active: bool | None = None


class ReorderRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    product_id: str
    variant_id: str | None
    warehouse_id: str | None
    reorder_level: Decimal
    reorder_quantity: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("reorder_level", "reorder_quantity", mode="before")
    @classmethod
    def coerce_decimal(cls, v: object) -> Decimal:
        return Decimal(str(v))


# ---------------------------------------------------------------------------
# LowStockAlert schemas
# ---------------------------------------------------------------------------


class AlertAcknowledgeRequest(BaseModel):
    """Payload to acknowledge an alert."""

    notes: str | None = Field(default=None, max_length=500)


class LowStockAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    product_id: str
    variant_id: str | None
    warehouse_id: str
    alert_type: AlertType
    status: AlertStatus
    current_quantity: Decimal
    threshold_quantity: Decimal
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    resolved_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    @field_validator("current_quantity", "threshold_quantity", mode="before")
    @classmethod
    def coerce_decimal(cls, v: object) -> Decimal:
        return Decimal(str(v))


# ---------------------------------------------------------------------------
# ReorderSuggestion schemas
# ---------------------------------------------------------------------------


class SuggestionAcknowledgeRequest(BaseModel):
    """Payload to acknowledge a reorder suggestion."""

    notes: str | None = Field(default=None, max_length=500)


class ReorderSuggestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    product_id: str
    variant_id: str | None
    warehouse_id: str
    suggested_quantity: Decimal
    triggered_by_alert_id: str | None
    status: SuggestionStatus
    created_at: datetime
    updated_at: datetime

    @field_validator("suggested_quantity", mode="before")
    @classmethod
    def coerce_decimal(cls, v: object) -> Decimal:
        return Decimal(str(v))

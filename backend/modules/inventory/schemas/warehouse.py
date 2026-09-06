"""Warehouse Pydantic schemas — request/response models for warehouse API.

Spec ref: specs/005-inventory-management/spec.md §16
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enums as literals
# ---------------------------------------------------------------------------

WarehouseType = Literal["MAIN", "BRANCH", "TRANSIT", "VIRTUAL", "CONSIGNMENT"]
WarehouseStatus = Literal["ACTIVE", "INACTIVE", "ARCHIVED"]


# ---------------------------------------------------------------------------
# Warehouse request schemas
# ---------------------------------------------------------------------------


class WarehouseCreateRequest(BaseModel):
    """Payload for creating a new warehouse."""

    code: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Unique warehouse code per company",
    )
    name: str = Field(
        ..., min_length=1, max_length=200, description="Human-readable warehouse name"
    )
    warehouse_type: WarehouseType = Field(default="MAIN", description="Warehouse type")
    # Address (all optional)
    address_line1: str | None = Field(default=None, max_length=300)
    address_line2: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    state_province: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country_code: str | None = Field(default=None, max_length=3)
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None)


class WarehouseUpdateRequest(BaseModel):
    """Payload for updating warehouse details (partial update)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    warehouse_type: WarehouseType | None = Field(default=None)
    address_line1: str | None = Field(default=None, max_length=300)
    address_line2: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    state_province: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country_code: str | None = Field(default=None, max_length=3)
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None)


# ---------------------------------------------------------------------------
# Warehouse response schema
# ---------------------------------------------------------------------------


class WarehouseResponse(BaseModel):
    """Full warehouse representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    name: str
    warehouse_type: str
    status: str
    branch_id: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state_province: str | None
    postal_code: str | None
    country_code: str | None
    phone: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# WarehouseLocation schemas
# ---------------------------------------------------------------------------


class LocationCreateRequest(BaseModel):
    """Payload for adding a warehouse location."""

    location_code: str = Field(
        ..., min_length=1, max_length=50, description="Code unique within the warehouse"
    )
    aisle: str | None = Field(default=None, max_length=20)
    zone: str | None = Field(default=None, max_length=50)
    shelf: str | None = Field(default=None, max_length=20)
    is_active: bool = Field(default=True)


class LocationUpdateRequest(BaseModel):
    """Payload for updating a warehouse location."""

    aisle: str | None = Field(default=None, max_length=20)
    zone: str | None = Field(default=None, max_length=50)
    shelf: str | None = Field(default=None, max_length=20)
    is_active: bool | None = Field(default=None)


class LocationResponse(BaseModel):
    """Warehouse location representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    warehouse_id: str
    location_code: str
    aisle: str | None
    zone: str | None
    shelf: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

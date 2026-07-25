"""Pydantic request/response schemas for the Product aggregate.

Covers: Product, ProductVariant, ProductBarcode, ProductImage.

Spec ref: specs/005-inventory-management/spec.md §14
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from modules.inventory.schemas.base import InventoryBaseSchema, PaginatedResponse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_PRODUCT_TYPES = {"STANDARD", "VARIANT", "SERVICE", "BUNDLE", "RAW_MATERIAL"}
_VALID_STATUSES = {"DRAFT", "ACTIVE", "INACTIVE", "DISCONTINUED", "ARCHIVED"}
_VALID_BARCODE_TYPES = {"EAN13", "EAN8", "QR", "CODE128", "CUSTOM"}


# =============================================================================
# ProductBarcode schemas
# =============================================================================


class BarcodeAddRequest(InventoryBaseSchema):
    """Request body to add a barcode to a product or variant."""

    barcode_value: str = Field(min_length=1, max_length=100)
    barcode_type: str = Field(description="EAN13, EAN8, QR, CODE128, or CUSTOM")
    is_primary: bool = Field(default=False)
    variant_id: uuid.UUID | None = Field(default=None)

    @field_validator("barcode_type")
    @classmethod
    def validate_barcode_type(cls, v: str) -> str:
        v = v.upper()
        if v not in _VALID_BARCODE_TYPES:
            raise ValueError(
                f"barcode_type must be one of {sorted(_VALID_BARCODE_TYPES)}"
            )
        return v


class BarcodeResponse(InventoryBaseSchema):
    """Response schema for a single barcode record."""

    id: uuid.UUID
    product_id: str
    variant_id: str | None = None
    barcode_value: str
    barcode_type: str
    is_primary: bool
    created_at: datetime | None = None


# =============================================================================
# ProductVariant schemas
# =============================================================================


class VariantCreateRequest(InventoryBaseSchema):
    """Request body to create a new product variant."""

    variant_code: str = Field(
        min_length=1,
        max_length=100,
        description="Unique SKU for this variant within the company",
    )
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value attribute dictionary (e.g. {'size': 'L', 'colour': 'Red'})",
    )
    is_stock_tracked: bool = Field(default=True)

    @field_validator("variant_code")
    @classmethod
    def normalise_code(cls, v: str) -> str:
        return v.strip().upper()


class VariantResponse(InventoryBaseSchema):
    """Response schema for a product variant."""

    id: uuid.UUID
    product_id: str
    company_id: uuid.UUID
    variant_code: str
    attributes: dict[str, Any] | None = None
    is_stock_tracked: bool
    status: str


# =============================================================================
# Product core schemas
# =============================================================================


class ProductCreateRequest(InventoryBaseSchema):
    """Request body to create a new product."""

    product_code: str = Field(
        min_length=1,
        max_length=50,
        description="Unique product code (SKU) within the company",
    )
    name: str = Field(min_length=1, max_length=300)
    product_type: str = Field(
        default="STANDARD",
        description="STANDARD, VARIANT, SERVICE, BUNDLE, or RAW_MATERIAL",
    )
    base_uom_id: uuid.UUID = Field(description="Base unit of measure UUID (required)")
    description: str | None = Field(default=None, max_length=10000)
    short_description: str | None = Field(default=None, max_length=500)
    category_id: uuid.UUID | None = Field(default=None)
    brand_id: uuid.UUID | None = Field(default=None)
    # Procurement metadata
    hs_code: str | None = Field(default=None, max_length=20)
    country_of_origin: str | None = Field(default=None, max_length=100)
    lead_time_days: int | None = Field(default=None, ge=0)
    min_order_qty: float | None = Field(default=None, gt=0)
    max_order_qty: float | None = Field(default=None, gt=0)
    reorder_point: float | None = Field(default=None, ge=0)
    weight_kg: float | None = Field(default=None, ge=0)
    width_cm: float | None = Field(default=None, ge=0)
    height_cm: float | None = Field(default=None, ge=0)
    depth_cm: float | None = Field(default=None, ge=0)
    is_serialized: bool = Field(default=False)
    is_batch_tracked: bool = Field(default=False)
    cost_price: float | None = Field(default=None, ge=0)

    @field_validator("product_code")
    @classmethod
    def normalise_code(cls, v: str) -> str:
        if " " in v.strip():
            raise ValueError("product_code must not contain spaces.")
        return v.strip().upper()

    @field_validator("product_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        v = v.upper()
        if v not in _VALID_PRODUCT_TYPES:
            raise ValueError(
                f"product_type must be one of {sorted(_VALID_PRODUCT_TYPES)}"
            )
        return v

    @model_validator(mode="after")
    def validate_order_qty(self) -> ProductCreateRequest:
        if (
            self.min_order_qty is not None
            and self.max_order_qty is not None
            and self.min_order_qty > self.max_order_qty
        ):
            raise ValueError("min_order_qty cannot exceed max_order_qty.")
        return self


class ProductUpdateRequest(InventoryBaseSchema):
    """Request body to update product fields (all optional — patch semantics)."""

    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=10000)
    short_description: str | None = Field(default=None, max_length=500)
    category_id: uuid.UUID | None = Field(default=None)
    brand_id: uuid.UUID | None = Field(default=None)
    hs_code: str | None = Field(default=None, max_length=20)
    country_of_origin: str | None = Field(default=None, max_length=100)
    lead_time_days: int | None = Field(default=None, ge=0)
    min_order_qty: float | None = Field(default=None, gt=0)
    max_order_qty: float | None = Field(default=None, gt=0)
    reorder_point: float | None = Field(default=None, ge=0)
    weight_kg: float | None = Field(default=None, ge=0)
    width_cm: float | None = Field(default=None, ge=0)
    height_cm: float | None = Field(default=None, ge=0)
    depth_cm: float | None = Field(default=None, ge=0)
    is_serialized: bool | None = Field(default=None)
    is_batch_tracked: bool | None = Field(default=None)
    cost_price: float | None = Field(default=None, ge=0)


class ProductStatusRequest(InventoryBaseSchema):
    """Request body for lifecycle status transitions."""

    action: str = Field(
        description="Lifecycle action: activate, deactivate, discontinue, archive"
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        v = v.lower()
        allowed = {"activate", "deactivate", "discontinue", "archive"}
        if v not in allowed:
            raise ValueError(f"action must be one of {sorted(allowed)}")
        return v


class ProductResponse(InventoryBaseSchema):
    """Response schema for a single product."""

    id: uuid.UUID
    company_id: uuid.UUID
    product_code: str
    name: str
    product_type: str
    status: str
    description: str | None = None
    short_description: str | None = None
    base_uom_id: str
    category_id: str | None = None
    brand_id: str | None = None
    hs_code: str | None = None
    country_of_origin: str | None = None
    lead_time_days: int | None = None
    min_order_qty: float | None = None
    max_order_qty: float | None = None
    reorder_point: float | None = None
    weight_kg: float | None = None
    width_cm: float | None = None
    height_cm: float | None = None
    depth_cm: float | None = None
    is_serialized: bool
    is_batch_tracked: bool
    cost_price: float | None = None
    created_by: uuid.UUID | None = None


# Re-export PaginatedResponse so callers can do:
#   from modules.inventory.schemas.product import ProductResponse, ProductListResponse
ProductListResponse = PaginatedResponse[ProductResponse]


# =============================================================================
# Lookup / scanner API schemas (Phase 10 — T263 / T264)
# =============================================================================


class LookupResult(InventoryBaseSchema):
    """Response for barcode/SKU scanner lookup endpoint.

    Returns the matched product and its current stock at every warehouse
    where stock positions exist.
    """

    product_id: str
    product_code: str
    product_name: str
    product_type: str
    status: str
    base_uom_id: str
    barcode_value: str | None = None
    stock_positions: list[dict] = []


class LabelData(InventoryBaseSchema):
    """Minimal product data needed by a client-side label renderer.

    Returned by GET /products/{id}/label-data.  Intentionally small —
    only the fields required to print a barcode label without loading
    the full product response.
    """

    product_id: str
    product_code: str
    product_name: str
    barcode_value: str | None = None
    barcode_type: str | None = None
    uom_code: str
    uom_name: str

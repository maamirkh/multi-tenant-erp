"""Pydantic request/response schemas for Phase 3 product enrichment.

Covers: ProductTag, ProductCustomFieldValue, ProductInternalNote,
        ProductImage, ImportJob, BulkImport/Export.

Spec ref: specs/005-inventory-management/spec.md §14, §35
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from modules.inventory.schemas.base import InventoryBaseSchema

# =============================================================================
# ProductTag schemas
# =============================================================================


class TagAssignRequest(InventoryBaseSchema):
    """Request to assign a tag to a product."""

    tag_id: uuid.UUID = Field(description="UUID of the tag to assign")


class ProductTagResponse(InventoryBaseSchema):
    """Response for a product tag assignment."""

    id: uuid.UUID
    product_id: str
    tag_id: str
    created_at: datetime | None = None


# =============================================================================
# CustomFieldValue schemas
# =============================================================================


class CustomFieldValueSetRequest(InventoryBaseSchema):
    """Request to set (upsert) a custom field value on a product."""

    field_key: str = Field(min_length=1, max_length=100)
    value_text: str | None = Field(default=None, description="String/text/date value")
    value_number: str | None = Field(
        default=None,
        description="Numeric value (stored as string to preserve precision)",
    )
    value_bool: bool | None = Field(default=None, description="Boolean value")
    value_json: dict[str, Any] | None = Field(
        default=None, description="JSON value for list/multi-select fields"
    )


class CustomFieldValueResponse(InventoryBaseSchema):
    """Response for a product custom field value."""

    id: uuid.UUID
    product_id: str
    field_key: str
    value_text: str | None = None
    value_number: str | None = None
    value_bool: bool | None = None
    value_json: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# =============================================================================
# InternalNote schemas
# =============================================================================


class NoteAddRequest(InventoryBaseSchema):
    """Request to append an internal note to a product."""

    note_text: str = Field(min_length=1, max_length=10000)


class InternalNoteResponse(InventoryBaseSchema):
    """Response for a single internal note."""

    id: uuid.UUID
    product_id: str
    note_text: str
    author_id: str | None = None
    created_at: datetime | None = None


# =============================================================================
# ProductImage schemas
# =============================================================================


class ProductImageResponse(InventoryBaseSchema):
    """Response schema for a product image record."""

    id: uuid.UUID
    product_id: str
    variant_id: str | None = None
    s3_key: str
    url: str
    thumbnail_url: str | None = None
    is_primary: bool
    sort_order: int
    created_at: datetime | None = None


# =============================================================================
# ImportJob schemas
# =============================================================================


class ImportJobResponse(InventoryBaseSchema):
    """Response for a bulk import job."""

    id: uuid.UUID
    company_id: uuid.UUID
    status: str
    file_name: str
    total_rows: int
    processed_rows: int
    failed_rows: int
    error_rows: list[dict[str, Any]] | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

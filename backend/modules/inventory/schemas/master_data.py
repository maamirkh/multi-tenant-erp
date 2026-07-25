"""Pydantic request/response schemas for all Phase 1 master data entities.

Covers: Category, Brand, UOM, UOMConversion, AttributeDefinition, AttributeSet,
        AttributeSetMembership, Tag, ReasonCode, CustomFieldDefinition.

Spec ref: specs/005-inventory-management/spec.md §14
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from pydantic import Field, field_validator, model_validator

from modules.inventory.schemas.base import InventoryBaseSchema

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_STATUS_VALUES = {"active", "inactive"}
_UOM_TYPES = {"UNIT", "WEIGHT", "VOLUME", "LENGTH", "AREA"}
_APPLIES_TO_VALUES = {"ADJUSTMENT", "DAMAGE", "RETURN"}
_ENTITY_TYPES = {"PRODUCT", "WAREHOUSE", "CATEGORY", "BRAND"}
_DATA_TYPES = {"TEXT", "NUMBER", "BOOLEAN", "DATE", "DROPDOWN", "MULTISELECT"}
_SCOPES = {"PRODUCT_TYPE", "CATEGORY"}
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


# =============================================================================
# Category schemas
# =============================================================================


class CategoryCreateRequest(InventoryBaseSchema):
    """Request body to create a new category."""

    code: str = Field(
        min_length=1, max_length=50, description="Unique code within the company"
    )
    name: str = Field(min_length=1, max_length=255, description="Display name")
    description: str | None = Field(default=None, max_length=1000)
    parent_id: uuid.UUID | None = Field(
        default=None, description="Parent category UUID (null for root)"
    )
    sort_order: int = Field(default=0, ge=0, description="Display sort order")

    @field_validator("code")
    @classmethod
    def code_no_spaces(cls, v: str) -> str:
        if " " in v.strip():
            raise ValueError("Code must not contain spaces.")
        return v.strip().upper()


class CategoryUpdateRequest(InventoryBaseSchema):
    """Request body to update a category (all fields optional)."""

    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    parent_id: uuid.UUID | None = Field(default=None)
    sort_order: int | None = Field(default=None, ge=0)


class CategoryResponse(InventoryBaseSchema):
    """Response schema for a single category."""

    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    parent_id: str | None = None
    sort_order: int
    status: str
    created_by: uuid.UUID | None = None


# =============================================================================
# Brand schemas
# =============================================================================


class BrandCreateRequest(InventoryBaseSchema):
    """Request body to create a new brand."""

    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    country_of_origin: str | None = Field(default=None, max_length=100)
    logo_url: str | None = Field(default=None, max_length=2000)
    website: str | None = Field(default=None, max_length=2000)

    @field_validator("code")
    @classmethod
    def code_upper(cls, v: str) -> str:
        return v.strip().upper()


class BrandUpdateRequest(InventoryBaseSchema):
    """Request body to update a brand."""

    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    country_of_origin: str | None = Field(default=None, max_length=100)
    logo_url: str | None = Field(default=None, max_length=2000)
    website: str | None = Field(default=None, max_length=2000)


class BrandResponse(InventoryBaseSchema):
    """Response schema for a single brand."""

    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    name: str
    country_of_origin: str | None = None
    logo_url: str | None = None
    website: str | None = None
    status: str
    created_by: uuid.UUID | None = None


# =============================================================================
# UOM schemas
# =============================================================================


class UOMCreateRequest(InventoryBaseSchema):
    """Request body to create a new unit of measure."""

    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    uom_type: str = Field(description="One of: UNIT, WEIGHT, VOLUME, LENGTH, AREA")
    symbol: str | None = Field(default=None, max_length=20)

    @field_validator("uom_type")
    @classmethod
    def validate_uom_type(cls, v: str) -> str:
        v = v.upper()
        if v not in _UOM_TYPES:
            raise ValueError(f"uom_type must be one of: {sorted(_UOM_TYPES)}")
        return v

    @field_validator("code")
    @classmethod
    def code_upper(cls, v: str) -> str:
        return v.strip().upper()


class UOMUpdateRequest(InventoryBaseSchema):
    """Request body to update a UOM."""

    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    symbol: str | None = Field(default=None, max_length=20)


class UOMResponse(InventoryBaseSchema):
    """Response schema for a single unit of measure."""

    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    name: str
    uom_type: str
    symbol: str | None = None
    status: str
    created_by: uuid.UUID | None = None


class UOMConversionCreateRequest(InventoryBaseSchema):
    """Request body to create a UOM conversion."""

    source_uom_id: uuid.UUID
    target_uom_id: uuid.UUID
    conversion_factor: float = Field(
        gt=0, description="Conversion factor (must be > 0)"
    )
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def source_differs_from_target(self) -> UOMConversionCreateRequest:
        if self.source_uom_id == self.target_uom_id:
            raise ValueError("source_uom_id and target_uom_id must differ.")
        return self


class UOMConversionResponse(InventoryBaseSchema):
    """Response schema for a UOM conversion."""

    id: uuid.UUID
    company_id: uuid.UUID
    source_uom_id: str
    target_uom_id: str
    conversion_factor: float
    notes: str | None = None


# =============================================================================
# AttributeDefinition schemas
# =============================================================================


class AttributeDefinitionCreateRequest(InventoryBaseSchema):
    """Request body to create an attribute definition."""

    name: str = Field(min_length=1, max_length=255)
    data_type: str = Field(
        description="One of: TEXT, NUMBER, BOOLEAN, DATE, DROPDOWN, MULTISELECT"
    )
    options: list[Any] | dict[str, Any] | None = Field(
        default=None,
        description="Allowed values for DROPDOWN/MULTISELECT types",
    )
    is_required: bool = Field(default=False)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("data_type")
    @classmethod
    def validate_data_type(cls, v: str) -> str:
        v = v.upper()
        if v not in _DATA_TYPES:
            raise ValueError(f"data_type must be one of: {sorted(_DATA_TYPES)}")
        return v


class AttributeDefinitionUpdateRequest(InventoryBaseSchema):
    """Request body to update an attribute definition."""

    description: str | None = Field(default=None, max_length=1000)
    is_required: bool | None = Field(default=None)
    options: list[Any] | dict[str, Any] | None = Field(default=None)


class AttributeDefinitionResponse(InventoryBaseSchema):
    """Response schema for an attribute definition."""

    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    data_type: str
    options: list[Any] | dict[str, Any] | None = None
    is_required: bool
    description: str | None = None
    created_by: uuid.UUID | None = None


# =============================================================================
# AttributeSet schemas
# =============================================================================


class AttributeSetCreateRequest(InventoryBaseSchema):
    """Request body to create an attribute set."""

    name: str = Field(min_length=1, max_length=255)
    scope: str = Field(description="One of: PRODUCT_TYPE, CATEGORY")
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, v: str) -> str:
        v = v.upper()
        if v not in _SCOPES:
            raise ValueError(f"scope must be one of: {sorted(_SCOPES)}")
        return v


class AttributeSetResponse(InventoryBaseSchema):
    """Response schema for an attribute set."""

    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    scope: str
    description: str | None = None
    created_by: uuid.UUID | None = None


class AttributeSetMembershipAddRequest(InventoryBaseSchema):
    """Request body to add an attribute to an attribute set."""

    attribute_definition_id: uuid.UUID
    sort_order: int = Field(default=0, ge=0)


class AttributeSetMembershipResponse(InventoryBaseSchema):
    """Response schema for an attribute set membership."""

    id: uuid.UUID
    company_id: uuid.UUID
    attribute_set_id: str
    attribute_definition_id: str
    sort_order: int


# =============================================================================
# Tag schemas
# =============================================================================


class TagCreateRequest(InventoryBaseSchema):
    """Request body to create a tag."""

    name: str = Field(min_length=1, max_length=100)
    color: str | None = Field(
        default=None,
        max_length=7,
        description="Hex color string e.g. '#FF5733'",
    )

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _HEX_COLOR_RE.match(v):
            raise ValueError("color must be a 7-character hex string like '#FF5733'.")
        return v


class TagUpdateRequest(InventoryBaseSchema):
    """Request body to update a tag."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = Field(default=None, max_length=7)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _HEX_COLOR_RE.match(v):
            raise ValueError("color must be a 7-character hex string like '#FF5733'.")
        return v


class TagResponse(InventoryBaseSchema):
    """Response schema for a tag."""

    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    color: str | None = None
    usage_count: int


# =============================================================================
# ReasonCode schemas
# =============================================================================


class ReasonCodeCreateRequest(InventoryBaseSchema):
    """Request body to create a reason code."""

    code: str = Field(min_length=1, max_length=50)
    label: str = Field(min_length=1, max_length=255)
    applies_to: str = Field(description="One of: ADJUSTMENT, DAMAGE, RETURN")
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("applies_to")
    @classmethod
    def validate_applies_to(cls, v: str) -> str:
        v = v.upper()
        if v not in _APPLIES_TO_VALUES:
            raise ValueError(f"applies_to must be one of: {sorted(_APPLIES_TO_VALUES)}")
        return v

    @field_validator("code")
    @classmethod
    def code_upper(cls, v: str) -> str:
        return v.strip().upper()


class ReasonCodeUpdateRequest(InventoryBaseSchema):
    """Request body to update a reason code."""

    label: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class ReasonCodeResponse(InventoryBaseSchema):
    """Response schema for a reason code."""

    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    label: str
    applies_to: str
    description: str | None = None
    is_active: bool
    created_by: uuid.UUID | None = None


# =============================================================================
# CustomFieldDefinition schemas
# =============================================================================


class CustomFieldCreateRequest(InventoryBaseSchema):
    """Request body to create a custom field definition."""

    entity_type: str = Field(description="One of: PRODUCT, WAREHOUSE, CATEGORY, BRAND")
    field_key: str = Field(
        min_length=1, max_length=100, description="Unique key per entity_type"
    )
    field_label: str = Field(min_length=1, max_length=255)
    data_type: str = Field(description="One of: TEXT, NUMBER, BOOLEAN, DATE, DROPDOWN")
    options: list[Any] | dict[str, Any] | None = Field(default=None)
    is_required: bool = Field(default=False)
    sort_order: int = Field(default=0, ge=0)
    placeholder: str | None = Field(default=None, max_length=255)

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        v = v.upper()
        if v not in _ENTITY_TYPES:
            raise ValueError(f"entity_type must be one of: {sorted(_ENTITY_TYPES)}")
        return v

    @field_validator("data_type")
    @classmethod
    def validate_data_type(cls, v: str) -> str:
        v = v.upper()
        allowed = {"TEXT", "NUMBER", "BOOLEAN", "DATE", "DROPDOWN"}
        if v not in allowed:
            raise ValueError(f"data_type must be one of: {sorted(allowed)}")
        return v

    @field_validator("field_key")
    @classmethod
    def field_key_snake_case(cls, v: str) -> str:
        v = v.strip().lower().replace(" ", "_")
        return v


class CustomFieldUpdateRequest(InventoryBaseSchema):
    """Request body to update a custom field definition."""

    field_label: str | None = Field(default=None, min_length=1, max_length=255)
    placeholder: str | None = Field(default=None, max_length=255)
    is_required: bool | None = Field(default=None)
    sort_order: int | None = Field(default=None, ge=0)


class CustomFieldResponse(InventoryBaseSchema):
    """Response schema for a custom field definition."""

    id: uuid.UUID
    company_id: uuid.UUID
    entity_type: str
    field_key: str
    field_label: str
    data_type: str
    options: list[Any] | dict[str, Any] | None = None
    is_required: bool
    sort_order: int
    placeholder: str | None = None
    created_by: uuid.UUID | None = None

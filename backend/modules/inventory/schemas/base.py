"""Base Pydantic schemas for the Inventory module.

Provides:
  - ``InventoryBaseSchema``  — common config for all inventory schemas
  - ``PaginatedResponse``    — generic paginated list wrapper
  - ``FeatureFlagResponse``  — flag state response schema
  - ``FeatureFlagUpdateRequest`` — flag enable/disable request

Spec ref: specs/005-inventory-management/spec.md
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class InventoryBaseSchema(BaseModel):
    """Common Pydantic configuration for all Inventory module schemas.

    Uses ``from_attributes=True`` so SQLAlchemy ORM instances can be
    passed directly to ``model_validate()``.
    """

    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse(InventoryBaseSchema, Generic[T]):  # noqa: UP046
    """Generic paginated list response.

    Wraps a list of items with pagination metadata consistent with
    the platform ``StandardResponse`` convention.
    """

    items: list[T] = Field(description="Page of results")
    total: int = Field(description="Total number of records across all pages")
    page: int = Field(ge=1, description="Current page number (1-based)")
    page_size: int = Field(ge=1, le=200, description="Number of items per page")
    pages: int = Field(ge=0, description="Total number of pages")

    @classmethod
    def from_paginated(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> PaginatedResponse[T]:
        """Construct a ``PaginatedResponse`` from raw pagination parameters."""
        pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )


class FeatureFlagResponse(InventoryBaseSchema):
    """Response schema for a single feature flag state."""

    flag_key: str = Field(description="Feature flag key")
    label: str = Field(description="Human-readable label")
    description: str = Field(description="Feature description")
    is_enabled: bool = Field(description="Effective enabled state for this company")
    is_overridden: bool = Field(
        description="True if a company-specific override exists"
    )
    default_enabled: bool = Field(description="System default enabled state")


class FeatureFlagUpdateRequest(InventoryBaseSchema):
    """Request schema to enable or disable a feature flag."""

    is_enabled: bool = Field(description="New enabled state")
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Optional reason for this override",
    )

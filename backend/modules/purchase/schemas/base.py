"""Shared base schemas for the purchase module.

Provides:
  - ``PurchaseBaseSchema``  — base config with ORM mode enabled
  - ``PaginatedResponse``   — generic paginated list wrapper
  - ``PurchaseErrorDetail`` — standard error detail structure

Spec ref: specs/006-purchase-management/plan.md — Schema Layer
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

DataT = TypeVar("DataT")


class PurchaseBaseSchema(BaseModel):
    """Base schema for all purchase module request/response models.

    Enables ORM mode (``from_attributes=True``) so SQLAlchemy models
    can be serialised directly into response schemas.
    """

    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse(BaseModel, Generic[DataT]):
    """Generic paginated list response wrapper.

    Used consistently across all purchase list endpoints.
    """

    items: list[DataT]
    total: int
    skip: int
    limit: int

    model_config = ConfigDict(from_attributes=True)


class PurchaseErrorDetail(BaseModel):
    """Standard error detail for purchase module error responses."""

    code: str
    message: str
    details: dict[str, object] | None = None

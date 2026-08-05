"""Shared base schemas for the sales module.

Provides:
  - ``SalesBaseSchema``   — base config with ORM mode enabled
  - ``PaginatedResponse`` — generic paginated list wrapper
  - ``SalesErrorDetail``  — standard error detail structure

Spec ref: specs/007-sales-management/plan.md — Schema Layer
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

DataT = TypeVar("DataT")


class SalesBaseSchema(BaseModel):
    """Base schema for all sales module request/response models.

    Enables ORM mode (``from_attributes=True``) so SQLAlchemy models
    can be serialised directly into response schemas.
    """

    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse(BaseModel, Generic[DataT]):  # noqa: UP046
    """Generic paginated list response wrapper.

    Used consistently across all sales list endpoints.
    """

    items: list[DataT]
    total: int
    skip: int
    limit: int

    model_config = ConfigDict(from_attributes=True)


class SalesErrorDetail(BaseModel):
    """Standard error detail for sales module error responses."""

    code: str
    message: str
    details: dict[str, object] | None = None

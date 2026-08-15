"""Shared base schemas for the accounting module.

Provides:
  - ``AccountingBaseSchema``   — base config with ORM mode enabled
  - ``PaginatedResponse``      — generic paginated list wrapper
  - ``AccountingErrorDetail``  — standard financial error response structure

Spec ref: specs/008-accounting-finance/plan.md — Schema Layer
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

DataT = TypeVar("DataT")


class AccountingBaseSchema(BaseModel):
    """Base schema for all accounting module request/response models.

    Enables ORM mode (``from_attributes=True``) so SQLAlchemy models
    can be serialised directly into response schemas.
    """

    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse(BaseModel, Generic[DataT]):  # noqa: UP046
    """Generic paginated list response wrapper.

    Used consistently across all accounting list endpoints.
    """

    items: list[DataT]
    total: int
    skip: int
    limit: int

    model_config = ConfigDict(from_attributes=True)


class AccountingErrorDetail(BaseModel):
    """Standard financial error detail for accounting module error responses.

    ``error_code`` follows a stable, documented taxonomy (e.g.
    ``JOURNAL_UNBALANCED``, ``PERIOD_LOCKED``, ``ACCOUNT_INACTIVE``) so
    client applications can branch on error type without parsing messages.
    """

    error_code: str
    message: str
    details: dict[str, object] | None = None

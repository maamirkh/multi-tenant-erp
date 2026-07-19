"""Pagination schemas and query-parameter model.

All list endpoints in DevSphere ERP return ``PaginatedResponse[T]`` so that
client code can handle any collection uniformly regardless of the resource
type.

Usage::

    from core.schemas.pagination import PaginatedResponse, PaginationParams
    from core.schemas.response import ResponseMeta

    # In a service:
    items, total = repo.list(company_id=..., skip=params.offset, limit=params.page_size)
    pages = calculate_pages(total, params.page_size)

    # In a router:
    return PaginatedResponse[ProductOut](
        data=PaginatedData(
            items=items, total=total,
            page=params.page, page_size=params.page_size, pages=pages,
        ),
        message="Products retrieved.",
        meta=ResponseMeta(request_id=..., timestamp=utcnow()),
    )
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from core.schemas.response import ResponseMeta

T = TypeVar("T")


class PaginatedData(BaseModel, Generic[T]):
    """Paginated payload wrapper.

    Fields:
        items:     Page contents — list of items of type ``T``.
        total:     Total number of matching records across all pages.
        page:      Current page number (1-indexed).
        page_size: Number of items per page.
        pages:     Total number of pages: ``ceil(total / page_size)`` or 0.
    """

    model_config = ConfigDict(from_attributes=True)

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    """Envelope for paginated list API responses.

    Example JSON::

        {
          "data": {
            "items": [...],
            "total": 42,
            "page": 1,
            "page_size": 20,
            "pages": 3
          },
          "message": "Products retrieved.",
          "meta": { "request_id": "...", "timestamp": "..." }
        }
    """

    model_config = ConfigDict(from_attributes=True)

    data: PaginatedData[T]
    message: str
    meta: ResponseMeta


class PaginationParams(BaseModel):
    """FastAPI dependency model for standard pagination query parameters.

    Use as a FastAPI dependency::

        from typing import Annotated
        from fastapi import Depends
        from core.schemas.pagination import PaginationParams

        def list_products(params: Annotated[PaginationParams, Depends()]) -> ...:
            skip = params.offset
            ...

    Constraints:
        page:      Minimum 1.  Default 1.
        page_size: Minimum 1, maximum 100.  Default 20.
    """

    model_config = ConfigDict(from_attributes=True)

    page: int = Field(default=1, ge=1, description="Page number (1-indexed).")
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of items per page. Maximum 100.",
    )

    @property
    def offset(self) -> int:
        """Calculate the SQL OFFSET value for this page."""
        return (self.page - 1) * self.page_size

"""Public API for the core schemas package.

Import schemas from here, not from the submodules directly::

    from core.schemas import StandardResponse, ErrorResponse, PaginatedResponse
"""

from core.schemas.pagination import (
    PaginatedData,
    PaginatedResponse,
    PaginationParams,
)
from core.schemas.response import (
    ErrorDetail,
    ErrorResponse,
    ResponseMeta,
    StandardResponse,
)

__all__ = [
    "ErrorDetail",
    "ErrorResponse",
    "PaginatedData",
    "PaginatedResponse",
    "PaginationParams",
    "ResponseMeta",
    "StandardResponse",
]

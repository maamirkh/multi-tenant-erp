"""Public API for the core exceptions package.

Import exceptions from here, not from the submodules directly::

    from core.exceptions import NotFoundException, ValidationException
"""

from core.exceptions.base import (
    ApplicationException,
    ConflictException,
    ForbiddenException,
    InfrastructureException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)

__all__ = [
    "ApplicationException",
    "ConflictException",
    "ForbiddenException",
    "InfrastructureException",
    "NotFoundException",
    "UnauthorizedException",
    "ValidationException",
]

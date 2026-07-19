"""Centralized authentication exception → HTTP status mapping.

This module provides an importable reference table that documents the canonical
mapping between auth-domain exceptions and their HTTP status codes.

The mapping is implemented via the ``http_status`` attribute on each
``ApplicationException`` subclass (consumed by the global handler in
``core/exceptions/handler.py``).  This module exposes it as an explicit
constant so other modules can reason about HTTP codes without instantiating
exceptions.

Error code taxonomy
-------------------
400  INVALID_TOKEN          — one-time token not found / already consumed
401  INVALID_CREDENTIALS    — wrong password, unknown email, invalid JWT
401  TOKEN_EXPIRED          — JWT or refresh token past expiry
401  TOKEN_REVOKED          — refresh token has been revoked (possible theft)
401  UNAUTHORIZED           — missing / malformed Authorization header
403  ACCOUNT_INACTIVE       — account status is INACTIVE or DELETED
403  FORBIDDEN              — generic permission denied
409  CONFLICT               — e.g. email already registered
422  VALIDATION_ERROR       — password complexity violation, schema error
423  ACCOUNT_LOCKED         — too many failed login attempts
"""

from __future__ import annotations

from core.auth.exceptions import (
    AccountInactiveException,
    AccountLockedException,
    AuthenticationException,
    InvalidTokenException,
    TokenExpiredException,
    TokenRevokedException,
)
from core.exceptions.base import (
    ConflictException,
    ForbiddenException,
    UnauthorizedException,
    ValidationException,
)

AUTH_EXCEPTION_HTTP_STATUS: dict[type[Exception], int] = {
    # 400
    InvalidTokenException: 400,
    # 401
    AuthenticationException: 401,
    TokenExpiredException: 401,
    TokenRevokedException: 401,
    UnauthorizedException: 401,
    # 403
    AccountInactiveException: 403,
    ForbiddenException: 403,
    # 409
    ConflictException: 409,
    # 422
    ValidationException: 422,
    # 423
    AccountLockedException: 423,
}

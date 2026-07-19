"""Authentication-specific exception hierarchy.

All exceptions in this module extend ``ApplicationException`` from
``core.exceptions.base`` so they are handled uniformly by the global
exception handler and serialised into the standard ``ErrorResponse`` shape.

HTTP status codes follow RFC 9110 and the spec.md §13 security requirements:
- 400  Bad Request      — malformed or consumed one-time tokens
- 401  Unauthorized     — missing/invalid/expired credentials or tokens
- 403  Forbidden        — account exists but access is denied (inactive)
- 423  Locked           — account temporarily locked after failed attempts
"""

from __future__ import annotations

from core.exceptions.base import ApplicationException


class AuthenticationException(ApplicationException):
    """Raised when authentication fails due to invalid or missing credentials.

    Used for: wrong password, unknown email (anti-enumeration), missing
    Authorization header, invalid JWT signature, unrecognised token format.

    Always maps to HTTP 401 to avoid disclosing account existence.
    """

    def __init__(
        self,
        message: str = "Invalid credentials.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="INVALID_CREDENTIALS",
            details=details,
            http_status=401,
        )


class AccountLockedException(ApplicationException):
    """Raised when a login attempt is made against a temporarily locked account.

    The ``details`` dict SHOULD include ``unlocks_at`` (ISO-8601 UTC string)
    so that clients can display an accurate unlock countdown.

    Maps to HTTP 423 Locked (RFC 4918).
    """

    def __init__(
        self,
        message: str = "Account is temporarily locked due to too many failed login attempts.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="ACCOUNT_LOCKED",
            details=details,
            http_status=423,
        )


class AccountInactiveException(ApplicationException):
    """Raised when a login attempt is made against an inactive or deleted account.

    Inactive accounts have been administratively deactivated (status INACTIVE).
    Deleted accounts use the same exception to avoid disclosing deletion status
    (anti-enumeration: deleted accounts respond identically to unknown emails).

    Maps to HTTP 403 Forbidden.
    """

    def __init__(
        self,
        message: str = "Account is not active.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="ACCOUNT_INACTIVE",
            details=details,
            http_status=403,
        )


class TokenExpiredException(ApplicationException):
    """Raised when a JWT access token or refresh token has passed its expiry time.

    Clients receiving this exception on a protected endpoint MUST attempt
    token refresh before retrying the original request.

    Maps to HTTP 401 Unauthorized.
    """

    def __init__(
        self,
        message: str = "Token has expired.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="TOKEN_EXPIRED",
            details=details,
            http_status=401,
        )


class TokenRevokedException(ApplicationException):
    """Raised when a refresh token is presented that has already been revoked.

    A revoked token presented for refresh may indicate token theft. The system
    SHOULD revoke all active tokens for the affected user and emit an audit event.

    Maps to HTTP 401 Unauthorized.
    """

    def __init__(
        self,
        message: str = "Token has been revoked.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="TOKEN_REVOKED",
            details=details,
            http_status=401,
        )


class InvalidTokenException(ApplicationException):
    """Raised when a one-time token (password reset, email verification) is invalid.

    Covers: token not found, token already consumed, token for a different user.
    Expired tokens raise ``TokenExpiredException`` instead.

    Maps to HTTP 400 Bad Request.
    """

    def __init__(
        self,
        message: str = "Token is invalid or has already been used.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="INVALID_TOKEN",
            details=details,
            http_status=400,
        )

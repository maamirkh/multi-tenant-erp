"""PlatformJwtService — stateless Platform JWT creation and validation.

Mirrors `modules.auth.services.jwt_service.JWTService` exactly, reusing
the same `PyJWT`/HS256 settings (`JWT_SECRET_KEY`, `JWT_ALGORITHM`,
`JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_CLOCK_SKEW_SECONDS`) — no new crypto,
no new secret management (T048's acceptance). The structural guarantee
that distinguishes a Platform token from a tenant token is the `typ`
claim: `"platform_access"`/`"platform_refresh"` here, vs. `"access"`/
`"refresh"` for tenant tokens (plan.md §6, ADR-1).

Claim semantics differ deliberately from the tenant token: `sub` is the
`PlatformAdministrator.id` (not `User.id`), and `sid` is the
`PlatformSession.id`. This is what makes a Platform token structurally
unusable by `get_current_user()` without any change to that function —
a `PlatformAdministrator.id` does not correspond to any `users.id` row,
so `UserRepository.get_by_id_or_none()` naturally returns `None` and the
request is rejected (T056). `get_current_user()` is untouched.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import Any
from uuid import UUID

import jwt
from jwt.exceptions import ExpiredSignatureError, PyJWTError

from core.auth.exceptions import AuthenticationException, TokenExpiredException
from core.config.settings import Settings
from core.utils.datetime import utcnow

logger = logging.getLogger(__name__)


class PlatformJwtService:
    """Stateless Platform JWT service — no database dependency."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create_access_token(
        self, platform_administrator_id: UUID, session_id: UUID
    ) -> str:
        """Create a signed Platform access token, `typ="platform_access"`."""
        now = utcnow()
        expire = now + timedelta(minutes=self._settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

        payload: dict[str, object] = {
            "sub": str(platform_administrator_id),
            "sid": str(session_id),
            "iat": now,
            "exp": expire,
            "nbf": now,
            "jti": str(uuid.uuid4()),
            "iss": self._settings.JWT_ISSUER,
            "aud": self._settings.JWT_AUDIENCE,
            "typ": "platform_access",
        }
        return jwt.encode(
            payload,
            self._settings.JWT_SECRET_KEY,
            algorithm=self._settings.JWT_ALGORITHM,
        )

    def create_refresh_token(
        self, platform_administrator_id: UUID, session_id: UUID
    ) -> str:
        """Create a signed Platform refresh token, `typ="platform_refresh"`.

        Unlike the tenant refresh token (an opaque `secrets.token_urlsafe()`
        string), the Platform refresh token is itself a signed JWT — T048's
        acceptance explicitly requires a `typ` claim on both the access and
        refresh token, which only a JWT can carry. Its SHA-256 hash is
        still the only thing persisted (`PlatformRefreshToken.token_hash`,
        data-model.md), exactly mirroring the tenant table's storage
        contract — only the *format* of the raw credential differs.
        """
        now = utcnow()
        expire = now + timedelta(days=self._settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        payload: dict[str, object] = {
            "sub": str(platform_administrator_id),
            "sid": str(session_id),
            "iat": now,
            "exp": expire,
            "nbf": now,
            "jti": str(uuid.uuid4()),
            "iss": self._settings.JWT_ISSUER,
            "aud": self._settings.JWT_AUDIENCE,
            "typ": "platform_refresh",
        }
        return jwt.encode(
            payload,
            self._settings.JWT_SECRET_KEY,
            algorithm=self._settings.JWT_ALGORITHM,
        )

    def decode_token(self, token: str) -> dict[str, Any]:
        """Decode and validate a Platform JWT (access or refresh).

        Validates signature, expiry, issuer, audience, and algorithm —
        identical mechanics to the tenant `JWTService.decode_access_token()`.
        Callers must separately check the `typ` claim for the operation
        they're performing.

        Raises:
            TokenExpiredException: When the token's `exp` claim is in the past.
            AuthenticationException: For all other JWT validation failures.
        """
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                self._settings.JWT_SECRET_KEY,
                algorithms=[self._settings.JWT_ALGORITHM],
                issuer=self._settings.JWT_ISSUER,
                audience=self._settings.JWT_AUDIENCE,
                leeway=timedelta(seconds=self._settings.JWT_CLOCK_SKEW_SECONDS),
            )
            return claims
        except ExpiredSignatureError:
            raise TokenExpiredException()
        except PyJWTError as exc:
            logger.debug("Platform JWT validation failed: %s", exc)
            raise AuthenticationException(
                message="Invalid or malformed Platform authentication token."
            )

    def extract_platform_administrator_id(self, claims: dict[str, Any]) -> UUID:
        """Parse and return the `sub` claim as a UUID."""
        sub = claims.get("sub")
        if not sub:
            raise AuthenticationException(message="Token missing 'sub' claim.")
        try:
            return UUID(str(sub))
        except ValueError:
            raise AuthenticationException(
                message="Token 'sub' claim is not a valid UUID."
            )

    def extract_session_id(self, claims: dict[str, Any]) -> UUID:
        """Parse and return the `sid` claim as a UUID."""
        sid = claims.get("sid")
        if not sid:
            raise AuthenticationException(message="Token missing 'sid' claim.")
        try:
            return UUID(str(sid))
        except ValueError:
            raise AuthenticationException(
                message="Token 'sid' claim is not a valid UUID."
            )

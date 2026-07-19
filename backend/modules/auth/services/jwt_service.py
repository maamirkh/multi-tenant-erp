"""JWTService — stateless JWT access token creation and validation.

Access tokens are short-lived (default 15 minutes) and carry the minimum
claims needed for stateless authentication.  They are signed with HMAC-SHA256
(HS256) by default; the algorithm is configurable via ``JWT_ALGORITHM``.

JWT claim set (RFC 7519):
  - sub   : user UUID (string)
  - email : user email
  - sid   : session UUID (string) — links token to a DB session
  - iat   : issued-at (UTC epoch)
  - exp   : expiry (UTC epoch)
  - nbf   : not-before (UTC epoch, same as iat)
  - jti   : unique token ID (UUID4)
  - iss   : issuer (from settings)
  - aud   : audience (from settings)
  - typ   : "access"

Security notes:
  - Tokens are validated against issuer, audience, expiry, and signature.
  - A configurable clock-skew tolerance prevents failures from minor time drift.
  - ``alg=none`` and algorithm switching attacks are prevented by passing the
    exact expected algorithm to ``jwt.decode()``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from uuid import UUID

import jwt
from jwt.exceptions import ExpiredSignatureError, PyJWTError

from core.auth.exceptions import AuthenticationException, TokenExpiredException
from core.config.settings import Settings
from core.utils.datetime import utcnow

logger = logging.getLogger(__name__)


class JWTService:
    """Stateless JWT service — no database dependency.

    Args:
        settings: Application settings (JWT_SECRET_KEY, algorithm, expiry, …).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create_access_token(self, user_id: UUID, email: str, session_id: UUID) -> str:
        """Create a signed JWT access token for the given identity.

        Args:
            user_id:    The authenticated user's UUID.
            email:      The user's email address (embedded for client convenience).
            session_id: The active session UUID linking this token to a DB session.

        Returns:
            Encoded JWT string ready to return to the client.
        """
        now = utcnow()
        expire = now + timedelta(minutes=self._settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

        payload: dict[str, object] = {
            "sub": str(user_id),
            "email": email,
            "sid": str(session_id),
            "iat": now,
            "exp": expire,
            "nbf": now,
            "jti": str(uuid.uuid4()),
            "iss": self._settings.JWT_ISSUER,
            "aud": self._settings.JWT_AUDIENCE,
            "typ": "access",
        }

        token: str = jwt.encode(
            payload,
            self._settings.JWT_SECRET_KEY,
            algorithm=self._settings.JWT_ALGORITHM,
        )
        return token

    def decode_access_token(self, token: str) -> dict:
        """Decode and validate a JWT access token.

        Validates signature, expiry, issuer, audience, and algorithm.

        Args:
            token: Encoded JWT string from the Authorization header.

        Returns:
            Decoded claims dictionary.

        Raises:
            TokenExpiredException: When the token's ``exp`` claim is in the past.
            AuthenticationException: For all other JWT validation failures.
        """
        try:
            claims: dict = jwt.decode(
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
            logger.debug("JWT validation failed: %s", exc)
            raise AuthenticationException(
                message="Invalid or malformed authentication token."
            )

    def extract_user_id(self, claims: dict) -> UUID:
        """Parse and return the ``sub`` claim as a UUID.

        Raises:
            AuthenticationException: If ``sub`` is missing or not a valid UUID.
        """
        sub = claims.get("sub")
        if not sub:
            raise AuthenticationException(message="Token missing 'sub' claim.")
        try:
            return UUID(str(sub))
        except ValueError:
            raise AuthenticationException(
                message="Token 'sub' claim is not a valid UUID."
            )

    def extract_session_id(self, claims: dict) -> UUID:
        """Parse and return the ``sid`` claim as a UUID.

        Raises:
            AuthenticationException: If ``sid`` is missing or not a valid UUID.
        """
        sid = claims.get("sid")
        if not sid:
            raise AuthenticationException(message="Token missing 'sid' claim.")
        try:
            return UUID(str(sid))
        except ValueError:
            raise AuthenticationException(
                message="Token 'sid' claim is not a valid UUID."
            )

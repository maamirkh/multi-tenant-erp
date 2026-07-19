"""TokenService — refresh token, password reset token, and email verification token lifecycle.

All raw token values are generated via ``secrets.token_urlsafe()`` and only
their SHA-256 hex digest is persisted.  The raw value is returned once to
the caller and must never be stored.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from core.auth.exceptions import InvalidTokenException, TokenExpiredException
from core.config.settings import Settings
from core.utils.datetime import ensure_utc, utcnow
from modules.auth.models.email_verification_token import EmailVerificationToken
from modules.auth.models.password_reset_token import PasswordResetToken
from modules.auth.models.refresh_token import RefreshToken
from modules.auth.repositories.email_verification_token_repository import (
    EmailVerificationTokenRepository,
)
from modules.auth.repositories.password_reset_token_repository import (
    PasswordResetTokenRepository,
)
from modules.auth.repositories.refresh_token_repository import RefreshTokenRepository

logger = logging.getLogger(__name__)

_REFRESH_TOKEN_BYTES = 64
_RESET_TOKEN_BYTES = 32
_VERIFY_TOKEN_BYTES = 32


def _sha256(value: str) -> str:
    """Return the SHA-256 hex digest of *value* (UTF-8 encoded)."""
    return hashlib.sha256(value.encode()).hexdigest()


class TokenService:
    """Manages opaque refresh tokens and one-time tokens.

    Args:
        db:       SQLAlchemy session (shared with other services in the request).
        settings: Application settings for expiry durations.
    """

    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._refresh_repo = RefreshTokenRepository(db)
        self._reset_repo = PasswordResetTokenRepository(db)
        self._verify_repo = EmailVerificationTokenRepository(db)

    # ------------------------------------------------------------------
    # Refresh tokens
    # ------------------------------------------------------------------

    def create_refresh_token(
        self,
        user_id: UUID,
        session_id: UUID,
        remember_me: bool,
        ip: str | None,
        user_agent: str | None,
    ) -> tuple[str, RefreshToken]:
        """Generate and persist a new refresh token.

        Args:
            user_id:    Token owner.
            session_id: Active session.
            remember_me: If ``True`` use the extended expiry duration.
            ip:         Client IP address.
            user_agent: Raw User-Agent header.

        Returns:
            Tuple of (raw_token, RefreshToken record).
        """
        raw_token = secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)
        token_hash = _sha256(raw_token)

        expire_days = (
            self._settings.JWT_REMEMBER_ME_EXPIRE_DAYS
            if remember_me
            else self._settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        expires_at = utcnow() + timedelta(days=expire_days)

        record = self._refresh_repo.create(
            user_id=user_id,
            session_id=session_id,
            token_hash=token_hash,
            expires_at=expires_at,
            remember_me=remember_me,
            ip_address=ip,
            user_agent=user_agent,
        )
        return raw_token, record

    def rotate_refresh_token(
        self,
        old_raw_token: str,
        ip: str | None,
        user_agent: str | None,
    ) -> tuple[str, RefreshToken]:
        """Atomically revoke the old token and issue a new one.

        The old token is looked up and immediately revoked.  A new token
        inheriting the ``remember_me`` flag and ``session_id`` is then created
        in the same call scope.

        Args:
            old_raw_token: Raw refresh token presented by the client.
            ip:            Client IP address for the new token record.
            user_agent:    Raw User-Agent header for the new token record.

        Returns:
            Tuple of (new_raw_token, new RefreshToken record).

        Raises:
            TokenExpiredException:  If the old token is expired.
            InvalidTokenException:  If the old token is not found or already revoked.
        """
        old_hash = _sha256(old_raw_token)
        old_token = self._refresh_repo.find_by_token_hash(old_hash)

        if old_token is None:
            raise InvalidTokenException(message="Refresh token not found.")

        now = utcnow()
        if ensure_utc(old_token.expires_at) <= now:
            raise TokenExpiredException(message="Refresh token has expired.")

        if old_token.is_revoked:
            # Possible token theft — revoke all tokens for the user.
            logger.warning(
                "Revoked refresh token presented — possible replay attack; "
                "revoking all tokens for user",
                extra={"user_id": str(old_token.user_id)},
            )
            self._refresh_repo.revoke_all_by_user(old_token.user_id)
            from core.auth.exceptions import TokenRevokedException

            raise TokenRevokedException(
                message="Refresh token has been revoked. Please log in again."
            )

        # Revoke the old token.
        self._refresh_repo.revoke(old_token.id)

        # Issue a new token.
        new_raw_token, new_record = self.create_refresh_token(
            user_id=old_token.user_id,
            session_id=old_token.session_id,
            remember_me=old_token.remember_me,
            ip=ip,
            user_agent=user_agent,
        )
        return new_raw_token, new_record

    # ------------------------------------------------------------------
    # Password reset tokens
    # ------------------------------------------------------------------

    def create_password_reset_token(self, user_id: UUID, ip: str | None) -> str:
        """Invalidate existing reset tokens and generate a new one (1-hour expiry).

        Args:
            user_id: The user requesting the reset.
            ip:      Client IP address.

        Returns:
            Raw reset token (to be embedded in the reset URL).
        """
        self._reset_repo.invalidate_active_by_user(user_id)

        raw_token = secrets.token_urlsafe(_RESET_TOKEN_BYTES)
        token_hash = _sha256(raw_token)
        expires_at = utcnow() + timedelta(hours=1)

        self._reset_repo.create(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip,
        )
        return raw_token

    def consume_password_reset_token(self, raw_token: str) -> PasswordResetToken:
        """Validate and mark a password reset token as consumed.

        Args:
            raw_token: The raw token value from the reset URL.

        Returns:
            The consumed ``PasswordResetToken`` record (provides ``user_id``).

        Raises:
            TokenExpiredException:  If the token has passed its expiry.
            InvalidTokenException:  If the token is not found or already consumed.
        """
        token_hash = _sha256(raw_token)

        # Check for any record (consumed or not) first to distinguish errors.
        record = self._reset_repo.find_by_token_hash(token_hash)
        if record is None:
            raise InvalidTokenException(message="Password reset token is invalid.")

        if record.is_consumed:
            raise InvalidTokenException(
                message="Password reset token has already been used."
            )

        now = utcnow()
        if ensure_utc(record.expires_at) <= now:
            raise TokenExpiredException(message="Password reset token has expired.")

        self._reset_repo.mark_consumed(record.id)
        return record

    # ------------------------------------------------------------------
    # Email verification tokens
    # ------------------------------------------------------------------

    def create_email_verification_token(self, user_id: UUID) -> str:
        """Generate and persist an email verification token (24-hour expiry).

        Args:
            user_id: The user whose email is being verified.

        Returns:
            Raw verification token (to be embedded in the verification URL).
        """
        raw_token = secrets.token_urlsafe(_VERIFY_TOKEN_BYTES)
        token_hash = _sha256(raw_token)
        expires_at = utcnow() + timedelta(hours=24)

        self._verify_repo.create(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        return raw_token

    def consume_email_verification_token(
        self, raw_token: str
    ) -> EmailVerificationToken:
        """Validate and mark an email verification token as consumed.

        Args:
            raw_token: The raw token value from the verification URL.

        Returns:
            The consumed ``EmailVerificationToken`` record (provides ``user_id``).

        Raises:
            TokenExpiredException:  If the token has passed its expiry.
            InvalidTokenException:  If the token is not found or already consumed.
        """
        token_hash = _sha256(raw_token)

        record = self._verify_repo.find_active_by_token_hash(token_hash)
        if record is None:
            raise InvalidTokenException(
                message="Email verification token is invalid or has already been used."
            )

        self._verify_repo.mark_consumed(record.id)
        return record

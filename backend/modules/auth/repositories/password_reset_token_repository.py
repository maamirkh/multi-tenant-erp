"""PasswordResetTokenRepository — data access for one-time password reset tokens."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.auth.models.password_reset_token import PasswordResetToken

logger = logging.getLogger(__name__)


class PasswordResetTokenRepository:
    """Data access for the ``password_reset_tokens`` table.

    Args:
        db: SQLAlchemy ``Session`` injected by the FastAPI ``get_db`` dependency.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
        ip_address: str | None,
    ) -> PasswordResetToken:
        """Persist a new password reset token.

        Args:
            user_id:    The user requesting the reset.
            token_hash: SHA-256 hex digest of the raw token.
            expires_at: UTC expiry time.
            ip_address: Client IP of the request (supports IPv6).

        Returns:
            The persisted ``PasswordResetToken`` record.
        """
        token = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
        )
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        logger.debug("Password reset token created", extra={"user_id": str(user_id)})
        return token

    def find_active_by_token_hash(self, token_hash: str) -> PasswordResetToken | None:
        """Return an active (not consumed, not expired) token by its hash.

        Returns ``None`` if no matching active token is found.
        """
        now = utcnow()
        stmt = (
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == token_hash)
            .where(PasswordResetToken.is_consumed == False)  # noqa: E712
            .where(PasswordResetToken.expires_at > now)
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def find_by_token_hash(self, token_hash: str) -> PasswordResetToken | None:
        """Return a token record by its hash regardless of status, or ``None``."""
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def mark_consumed(self, token_id: UUID) -> None:
        """Mark a reset token as consumed so it cannot be reused."""
        self.db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.id == token_id)
            .values(is_consumed=True, consumed_at=utcnow(), updated_at=utcnow())
        )
        self.db.commit()
        logger.debug("Password reset token consumed", extra={"token_id": str(token_id)})

    def invalidate_active_by_user(self, user_id: UUID) -> None:
        """Consume all active reset tokens for *user_id* (invalidate old requests)."""
        now = utcnow()
        self.db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id)
            .where(PasswordResetToken.is_consumed == False)  # noqa: E712
            .where(PasswordResetToken.expires_at > now)
            .values(is_consumed=True, consumed_at=now, updated_at=now)
        )
        self.db.commit()

    def delete_expired(self) -> int:
        """Delete all expired password reset tokens. Intended for scheduled cleanup."""
        now = utcnow()
        result = self.db.execute(
            delete(PasswordResetToken).where(PasswordResetToken.expires_at <= now)
        )
        self.db.commit()
        count: int = result.rowcount
        logger.info("Expired password reset tokens deleted", extra={"count": count})
        return count

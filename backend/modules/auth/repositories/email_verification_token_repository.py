"""EmailVerificationTokenRepository — data access for email verification tokens."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.auth.models.email_verification_token import EmailVerificationToken

logger = logging.getLogger(__name__)


class EmailVerificationTokenRepository:
    """Data access for the ``email_verification_tokens`` table.

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
    ) -> EmailVerificationToken:
        """Persist a new email verification token.

        Args:
            user_id:    The user whose email is being verified.
            token_hash: SHA-256 hex digest of the raw token.
            expires_at: UTC expiry time.

        Returns:
            The persisted ``EmailVerificationToken`` record.
        """
        token = EmailVerificationToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        logger.debug(
            "Email verification token created", extra={"user_id": str(user_id)}
        )
        return token

    def find_active_by_token_hash(
        self, token_hash: str
    ) -> EmailVerificationToken | None:
        """Return an active (not consumed, not expired) token by its hash.

        Returns ``None`` if no matching active token is found.
        """
        now = utcnow()
        stmt = (
            select(EmailVerificationToken)
            .where(EmailVerificationToken.token_hash == token_hash)
            .where(EmailVerificationToken.is_consumed == False)  # noqa: E712
            .where(EmailVerificationToken.expires_at > now)
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def mark_consumed(self, token_id: UUID) -> None:
        """Mark an email verification token as consumed."""
        self.db.execute(
            update(EmailVerificationToken)
            .where(EmailVerificationToken.id == token_id)
            .values(is_consumed=True, consumed_at=utcnow(), updated_at=utcnow())
        )
        self.db.commit()
        logger.debug(
            "Email verification token consumed", extra={"token_id": str(token_id)}
        )

    def delete_expired(self) -> int:
        """Delete all expired email verification tokens. Intended for scheduled cleanup."""
        now = utcnow()
        result = self.db.execute(
            delete(EmailVerificationToken).where(
                EmailVerificationToken.expires_at <= now
            )
        )
        self.db.commit()
        count: int = result.rowcount
        logger.info("Expired email verification tokens deleted", extra={"count": count})
        return count

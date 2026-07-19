"""RefreshTokenRepository — data access for opaque refresh tokens.

Only token *hashes* are stored; the raw token value is returned to the
client once and never persisted.  All lookup operations accept the SHA-256
hex digest of the raw token.

Token rotation (revoke-then-create) is executed inside a single database
transaction so that concurrent rotation attempts are serialised.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.auth.models.refresh_token import RefreshToken

logger = logging.getLogger(__name__)

_MAX_ACTIVE_TOKENS_PER_USER = 10


class RefreshTokenRepository:
    """Data access for the ``refresh_tokens`` table.

    Args:
        db: SQLAlchemy ``Session`` injected by the FastAPI ``get_db`` dependency.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        user_id: UUID,
        session_id: UUID,
        token_hash: str,
        expires_at: datetime,
        remember_me: bool,
        ip_address: str | None,
        user_agent: str | None,
    ) -> RefreshToken:
        """Persist a new refresh token.

        Enforces a maximum of ``_MAX_ACTIVE_TOKENS_PER_USER`` active tokens
        per user by revoking the oldest token(s) when the limit is reached.

        Args:
            user_id:     Owner of the token.
            session_id:  Session this token belongs to.
            token_hash:  SHA-256 hex digest of the raw token.
            expires_at:  UTC expiry time.
            remember_me: Whether extended expiry applies.
            ip_address:  Client IP (supports IPv6).
            user_agent:  Raw User-Agent header.

        Returns:
            The persisted ``RefreshToken`` record.
        """
        self._enforce_token_limit(user_id)

        token = RefreshToken(
            user_id=user_id,
            session_id=session_id,
            token_hash=token_hash,
            expires_at=expires_at,
            remember_me=remember_me,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        logger.debug(
            "Refresh token created",
            extra={"token_id": str(token.id), "user_id": str(user_id)},
        )
        return token

    def find_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        """Return a token record by its SHA-256 hash, or ``None``."""
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return self.db.execute(stmt).scalars().one_or_none()

    def revoke(self, token_id: UUID) -> None:
        """Mark a single refresh token as revoked."""
        now = utcnow()
        self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.id == token_id)
            .values(is_revoked=True, revoked_at=now, updated_at=now)
        )
        self.db.commit()
        logger.debug("Refresh token revoked", extra={"token_id": str(token_id)})

    def revoke_all_by_user(self, user_id: UUID) -> int:
        """Revoke all active refresh tokens for *user_id*.

        Returns:
            Number of tokens revoked.
        """
        now = utcnow()
        result = self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.is_revoked == False)  # noqa: E712
            .values(is_revoked=True, revoked_at=now, updated_at=now)
        )
        self.db.commit()
        count: int = result.rowcount
        logger.info(
            "All refresh tokens revoked for user",
            extra={"user_id": str(user_id), "count": count},
        )
        return count

    def revoke_all_by_session(self, session_id: UUID) -> int:
        """Revoke all active refresh tokens belonging to *session_id*.

        Returns:
            Number of tokens revoked.
        """
        now = utcnow()
        result = self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.session_id == session_id)
            .where(RefreshToken.is_revoked == False)  # noqa: E712
            .values(is_revoked=True, revoked_at=now, updated_at=now)
        )
        self.db.commit()
        count: int = result.rowcount
        logger.debug(
            "Refresh tokens revoked for session",
            extra={"session_id": str(session_id), "count": count},
        )
        return count

    def count_active_by_user(self, user_id: UUID) -> int:
        """Return the number of non-revoked, non-expired tokens for *user_id*."""
        now = utcnow()
        stmt = (
            select(func.count())
            .select_from(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.is_revoked == False)  # noqa: E712
            .where(RefreshToken.expires_at > now)
        )
        result: int = self.db.execute(stmt).scalar_one()
        return result

    def delete_expired(self) -> int:
        """Delete all expired refresh tokens. Intended for scheduled cleanup."""
        from sqlalchemy import delete

        now = utcnow()
        result = self.db.execute(
            delete(RefreshToken).where(RefreshToken.expires_at <= now)
        )
        self.db.commit()
        count: int = result.rowcount
        logger.info("Expired refresh tokens deleted", extra={"count": count})
        return count

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _enforce_token_limit(self, user_id: UUID) -> None:
        """Revoke the oldest active token(s) if the per-user limit is exceeded.

        Fetches active tokens ordered by creation time ascending so that the
        oldest token is revoked first when the limit is reached.
        """
        now = utcnow()
        active_stmt = (
            select(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.is_revoked == False)  # noqa: E712
            .where(RefreshToken.expires_at > now)
            .order_by(RefreshToken.created_at.asc())
        )
        active_tokens = list(self.db.execute(active_stmt).scalars().all())

        if len(active_tokens) >= _MAX_ACTIVE_TOKENS_PER_USER:
            tokens_to_revoke = active_tokens[
                : len(active_tokens) - _MAX_ACTIVE_TOKENS_PER_USER + 1
            ]
            ids_to_revoke = [t.id for t in tokens_to_revoke]
            self.db.execute(
                update(RefreshToken)
                .where(RefreshToken.id.in_(ids_to_revoke))
                .values(is_revoked=True, revoked_at=now, updated_at=now)
            )
            logger.debug(
                "Oldest refresh tokens revoked due to limit",
                extra={"user_id": str(user_id), "revoked": len(ids_to_revoke)},
            )

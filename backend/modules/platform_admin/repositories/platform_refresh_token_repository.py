"""PlatformRefreshTokenRepository — data access for `platform_refresh_tokens`.

Created as part of T049's scope (login needs to persist a
`PlatformRefreshToken`; no separate task exists for this repository — it
is the natural, minimal implementation T049/T050's own acceptance
criteria require). Mirrors `RefreshTokenRepository`'s data-access shape.
All methods `flush()` only, never `commit()` (ADR-5) — `PlatformAuthService`
owns the transaction boundary.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.platform_admin.models.platform_refresh_token import PlatformRefreshToken


class PlatformRefreshTokenRepository:
    """Data access for the ``platform_refresh_tokens`` table."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        session_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> PlatformRefreshToken:
        """Stage a new refresh-token row for insert. Caller commits."""
        token = PlatformRefreshToken(
            session_id=session_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(token)
        self.db.flush()
        return token

    def find_by_token_hash(self, token_hash: str) -> PlatformRefreshToken | None:
        stmt = select(PlatformRefreshToken).where(
            PlatformRefreshToken.token_hash == token_hash
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def revoke(self, token_id: UUID) -> None:
        """Stage a single refresh token as revoked. Caller commits."""
        token = self.db.get(PlatformRefreshToken, token_id)
        if token is not None:
            token.is_revoked = True
            token.revoked_at = utcnow()
        self.db.flush()

    def revoke_all_for_session(self, session_id: UUID) -> None:
        """Stage every refresh token for *session_id* as revoked. Caller
        commits — used by logout (T051)."""
        now = utcnow()
        self.db.execute(
            update(PlatformRefreshToken)
            .where(PlatformRefreshToken.session_id == session_id)
            .where(PlatformRefreshToken.is_revoked == False)  # noqa: E712
            .values(is_revoked=True, revoked_at=now, updated_at=now)
        )
        self.db.flush()

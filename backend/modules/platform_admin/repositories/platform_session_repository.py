"""PlatformSessionRepository — data access for `platform_sessions`.

Ordered before every consumer (Revision 2 fix — previously created after
the service that needed it). Deliberately does not inherit
`BaseRepository` (mandates `company_id` filtering — wrong for a
platform-scoped table). All methods `flush()` only, never `commit()` —
matching every other Platform repository in this module (ADR-5) so the
calling service (login/refresh/logout in `PlatformAuthService`, or the
session-revoking deactivation in `PlatformAdministratorService`, T054)
always owns the transaction boundary.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.platform_admin.models.platform_session import PlatformSession


class PlatformSessionRepository:
    """Data access for the ``platform_sessions`` table."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        platform_administrator_id: UUID,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> PlatformSession:
        """Stage a new session row for insert. Caller commits."""
        session = PlatformSession(
            platform_administrator_id=platform_administrator_id,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def get_by_id(self, session_id: UUID) -> PlatformSession | None:
        return self.db.get(PlatformSession, session_id)

    def revoke(self, session_id: UUID) -> None:
        """Stage a single session as revoked. Caller commits."""
        self.db.execute(
            update(PlatformSession)
            .where(PlatformSession.id == session_id)
            .values(is_revoked=True, revoked_at=utcnow(), updated_at=utcnow())
        )
        self.db.flush()

    def revoke_all_for_administrator(self, platform_administrator_id: UUID) -> None:
        """Stage every active session for *platform_administrator_id* as
        revoked. Caller commits — used by T054's session-revoking
        deactivation, which commits this together with the account-state
        change and its audit row in one transaction."""
        now = utcnow()
        self.db.execute(
            update(PlatformSession)
            .where(
                PlatformSession.platform_administrator_id == platform_administrator_id
            )
            .where(PlatformSession.is_revoked == False)  # noqa: E712
            .values(is_revoked=True, revoked_at=now, updated_at=now)
        )
        self.db.flush()

    def get_active_by_administrator(
        self, platform_administrator_id: UUID
    ) -> list[PlatformSession]:
        stmt = (
            select(PlatformSession)
            .where(
                PlatformSession.platform_administrator_id == platform_administrator_id
            )
            .where(PlatformSession.is_revoked == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())

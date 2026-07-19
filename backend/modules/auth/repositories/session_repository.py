"""SessionRepository — data access for authenticated sessions."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session as DbSession

from core.utils.datetime import utcnow
from modules.auth.models.session import Session

logger = logging.getLogger(__name__)


class SessionRepository:
    """Data access for the ``sessions`` table.

    Args:
        db: SQLAlchemy ``Session`` injected by the FastAPI ``get_db`` dependency.
    """

    def __init__(self, db: DbSession) -> None:
        self.db = db

    def create_session(
        self,
        user_id: UUID,
        ip_address: str | None,
        user_agent: str | None,
        device_info: dict | None = None,
    ) -> Session:
        """Create and persist a new authenticated session.

        Args:
            user_id:     Owner of the session.
            ip_address:  Client IP at login time (supports IPv6).
            user_agent:  Raw User-Agent header from the login request.
            device_info: Optional parsed device metadata.

        Returns:
            The persisted ``Session`` record with server-generated ``id``.
        """
        session = Session(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=device_info,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        logger.debug(
            "Session created",
            extra={"session_id": str(session.id), "user_id": str(user_id)},
        )
        return session

    def get_by_id(self, session_id: UUID) -> Session | None:
        """Return a session by its primary key, or ``None``."""
        stmt = select(Session).where(Session.id == session_id)
        return self.db.execute(stmt).scalars().one_or_none()

    def get_active_sessions_by_user(self, user_id: UUID) -> list[Session]:
        """Return all non-revoked sessions for *user_id*."""
        stmt = (
            select(Session)
            .where(Session.user_id == user_id)
            .where(Session.is_revoked == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())

    def revoke_session(self, session_id: UUID) -> None:
        """Mark a single session as revoked."""
        self.db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(is_revoked=True, revoked_at=utcnow(), updated_at=utcnow())
        )
        self.db.commit()
        logger.debug("Session revoked", extra={"session_id": str(session_id)})

    def revoke_all_by_user(self, user_id: UUID) -> None:
        """Revoke all active sessions for *user_id* (logout all devices)."""
        now = utcnow()
        self.db.execute(
            update(Session)
            .where(Session.user_id == user_id)
            .where(Session.is_revoked == False)  # noqa: E712
            .values(is_revoked=True, revoked_at=now, updated_at=now)
        )
        self.db.commit()
        logger.info("All sessions revoked for user", extra={"user_id": str(user_id)})

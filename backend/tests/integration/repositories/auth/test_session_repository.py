"""T103 — Integration tests for SessionRepository.

Verifies session creation, bulk revocation, and active-session filtering.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session as DbSession

from modules.auth.models.enums import AccountStatus
from modules.auth.models.user import User
from modules.auth.repositories.session_repository import SessionRepository


def _seed_user(db: DbSession) -> uuid.UUID:
    user = User(
        email=f"sess_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Session Test",
        account_status=AccountStatus.ACTIVE,
        is_email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user.id


class TestCreateSession:
    def test_returns_session_with_id(self, db_session: DbSession) -> None:
        user_id = _seed_user(db_session)
        repo = SessionRepository(db_session)
        session = repo.create_session(
            user_id=user_id,
            ip_address="10.0.0.1",
            user_agent="Mozilla/5.0",
        )
        assert session.id is not None
        assert session.user_id == user_id
        assert session.is_revoked is False


class TestRevokeAllByUser:
    def test_marks_all_sessions_revoked(self, db_session: DbSession) -> None:
        user_id = _seed_user(db_session)
        repo = SessionRepository(db_session)
        repo.create_session(user_id=user_id, ip_address=None, user_agent=None)
        repo.create_session(user_id=user_id, ip_address=None, user_agent=None)

        repo.revoke_all_by_user(user_id)

        active = repo.get_active_sessions_by_user(user_id)
        assert active == []


class TestGetActiveSessionsByUser:
    def test_excludes_revoked_sessions(self, db_session: DbSession) -> None:
        user_id = _seed_user(db_session)
        repo = SessionRepository(db_session)
        session = repo.create_session(user_id=user_id, ip_address=None, user_agent=None)
        repo.revoke_session(session.id)

        active = repo.get_active_sessions_by_user(user_id)
        assert all(not s.is_revoked for s in active)

    def test_returns_active_sessions(self, db_session: DbSession) -> None:
        user_id = _seed_user(db_session)
        repo = SessionRepository(db_session)
        repo.create_session(user_id=user_id, ip_address="127.0.0.1", user_agent=None)

        active = repo.get_active_sessions_by_user(user_id)
        assert len(active) >= 1

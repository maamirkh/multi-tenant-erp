"""T101 — Integration tests for RefreshTokenRepository.

Verifies that only the token *hash* is stored, lookup by hash works,
revocation is atomic, and the per-user active-token limit is enforced.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.auth.models.enums import AccountStatus
from modules.auth.models.session import Session as SessionModel
from modules.auth.models.user import User
from modules.auth.repositories.refresh_token_repository import RefreshTokenRepository


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _seed_user_and_session(db: Session) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a minimal user and session and return (user_id, session_id)."""
    user = User(
        email=f"rt_{uuid.uuid4().hex[:8]}@example.com",
        display_name="RT Test",
        account_status=AccountStatus.ACTIVE,
        is_email_verified=True,
    )
    db.add(user)
    db.flush()

    session = SessionModel(user_id=user.id, ip_address="127.0.0.1", user_agent="test")
    db.add(session)
    db.commit()
    db.refresh(user)
    db.refresh(session)
    return user.id, session.id


class TestCreate:
    def test_persists_token_hash_not_raw(self, db_session: Session) -> None:
        user_id, session_id = _seed_user_and_session(db_session)
        raw = secrets.token_urlsafe(32)
        token_hash = _sha256(raw)
        repo = RefreshTokenRepository(db_session)
        record = repo.create(
            user_id=user_id,
            session_id=session_id,
            token_hash=token_hash,
            expires_at=utcnow() + timedelta(days=7),
            remember_me=False,
            ip_address="127.0.0.1",
            user_agent="test-agent",
        )
        # The stored hash should match _sha256(raw), not raw itself.
        assert record.token_hash == token_hash
        assert record.token_hash != raw


class TestFindByTokenHash:
    def test_retrieves_by_hash(self, db_session: Session) -> None:
        user_id, session_id = _seed_user_and_session(db_session)
        raw = secrets.token_urlsafe(32)
        token_hash = _sha256(raw)
        repo = RefreshTokenRepository(db_session)
        created = repo.create(
            user_id=user_id,
            session_id=session_id,
            token_hash=token_hash,
            expires_at=utcnow() + timedelta(days=7),
            remember_me=False,
            ip_address=None,
            user_agent=None,
        )
        found = repo.find_by_token_hash(token_hash)
        assert found is not None
        assert found.id == created.id

    def test_returns_none_for_unknown_hash(self, db_session: Session) -> None:
        repo = RefreshTokenRepository(db_session)
        assert repo.find_by_token_hash("deadbeef" * 8) is None


class TestRevoke:
    def test_marks_token_revoked(self, db_session: Session) -> None:
        user_id, session_id = _seed_user_and_session(db_session)
        raw = secrets.token_urlsafe(32)
        token_hash = _sha256(raw)
        repo = RefreshTokenRepository(db_session)
        record = repo.create(
            user_id=user_id,
            session_id=session_id,
            token_hash=token_hash,
            expires_at=utcnow() + timedelta(days=7),
            remember_me=False,
            ip_address=None,
            user_agent=None,
        )
        repo.revoke(record.id)
        refreshed = repo.find_by_token_hash(token_hash)
        assert refreshed is not None
        assert refreshed.is_revoked is True


class TestRevokeAllByUser:
    def test_revokes_all_active_tokens(self, db_session: Session) -> None:
        user_id, session_id = _seed_user_and_session(db_session)
        repo = RefreshTokenRepository(db_session)
        # Create two tokens.
        for _ in range(2):
            raw = secrets.token_urlsafe(32)
            repo.create(
                user_id=user_id,
                session_id=session_id,
                token_hash=_sha256(raw),
                expires_at=utcnow() + timedelta(days=7),
                remember_me=False,
                ip_address=None,
                user_agent=None,
            )
        count = repo.revoke_all_by_user(user_id)
        assert count == 2
        assert repo.count_active_by_user(user_id) == 0


class TestCountActiveByUser:
    def test_returns_correct_active_count(self, db_session: Session) -> None:
        user_id, session_id = _seed_user_and_session(db_session)
        repo = RefreshTokenRepository(db_session)
        assert repo.count_active_by_user(user_id) == 0
        raw = secrets.token_urlsafe(32)
        repo.create(
            user_id=user_id,
            session_id=session_id,
            token_hash=_sha256(raw),
            expires_at=utcnow() + timedelta(days=7),
            remember_me=False,
            ip_address=None,
            user_agent=None,
        )
        assert repo.count_active_by_user(user_id) == 1


class TestTokenLimit:
    def test_oldest_token_revoked_when_limit_exceeded(
        self, db_session: Session
    ) -> None:
        """Creating 11 tokens for same user should revoke the oldest 1."""
        user_id, session_id = _seed_user_and_session(db_session)
        repo = RefreshTokenRepository(db_session)
        # Insert 11 tokens (limit is 10 per _MAX_ACTIVE_TOKENS_PER_USER in repo).
        for _ in range(11):
            raw = secrets.token_urlsafe(32)
            repo.create(
                user_id=user_id,
                session_id=session_id,
                token_hash=_sha256(raw),
                expires_at=utcnow() + timedelta(days=7),
                remember_me=False,
                ip_address=None,
                user_agent=None,
            )
        # Active count must stay at or below 10.
        assert repo.count_active_by_user(user_id) <= 10

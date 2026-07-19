"""T100 — Integration tests for UserRepository.

Uses the shared SQLite in-memory session fixture.  Each test runs inside
a transaction that is rolled back at teardown to prevent data leakage.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.auth.models.enums import AccountStatus
from modules.auth.models.user import User
from modules.auth.repositories.user_repository import UserRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(db: Session, email: str = "repo_user@example.com") -> User:
    user = User(
        email=email.lower(),
        display_name="Repo Test User",
        account_status=AccountStatus.ACTIVE,
        is_email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFindByEmail:
    def test_returns_user_when_found(self, db_session: Session) -> None:
        user = _make_user(db_session, email="find_me@example.com")
        repo = UserRepository(db_session)
        result = repo.find_by_email("find_me@example.com")
        assert result is not None
        assert result.id == user.id

    def test_returns_none_for_unknown_email(self, db_session: Session) -> None:
        repo = UserRepository(db_session)
        result = repo.find_by_email("nobody@unknown.example.com")
        assert result is None

    def test_lookup_is_case_insensitive(self, db_session: Session) -> None:
        _user = _make_user(db_session, email="casetest@example.com")
        repo = UserRepository(db_session)
        assert repo.find_by_email("CASETEST@EXAMPLE.COM") is not None
        assert repo.find_by_email("CaseTest@Example.Com") is not None


class TestLockAccount:
    def test_lock_account_sets_status_and_locked_until(
        self, db_session: Session
    ) -> None:
        user = _make_user(db_session, email="lockme@example.com")
        repo = UserRepository(db_session)
        until = utcnow() + timedelta(minutes=30)
        repo.lock_account(user.id, until)

        refreshed = repo.get_by_id(user.id)
        assert refreshed.account_status == AccountStatus.LOCKED
        assert refreshed.locked_until is not None


class TestUnlockAccount:
    def test_unlock_resets_status_and_counter(self, db_session: Session) -> None:
        user = _make_user(db_session, email="unlockme@example.com")
        repo = UserRepository(db_session)
        # Lock first.
        repo.lock_account(user.id, utcnow() + timedelta(minutes=10))
        repo.update_failed_login_count(user.id, 5)
        # Now unlock.
        repo.unlock_account(user.id)

        refreshed = repo.get_by_id(user.id)
        assert refreshed.account_status == AccountStatus.ACTIVE
        assert refreshed.locked_until is None
        assert refreshed.failed_login_count == 0


class TestUpdateFailedLoginCount:
    def test_updates_counter(self, db_session: Session) -> None:
        user = _make_user(db_session, email="failcount@example.com")
        repo = UserRepository(db_session)
        repo.update_failed_login_count(user.id, 3)
        refreshed = repo.get_by_id(user.id)
        assert refreshed.failed_login_count == 3

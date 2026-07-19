"""Unit tests for AuthService.login.

All repository/service dependencies are mocked so no real database is needed.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from core.auth.exceptions import (
    AccountInactiveException,
    AccountLockedException,
    AuthenticationException,
)
from core.config.settings import Settings
from core.utils.datetime import utcnow
from modules.auth.models.enums import AccountStatus, AuditEventType
from modules.auth.models.session import Session as SessionModel
from modules.auth.models.user import User
from modules.auth.models.user_credential import UserCredentials
from modules.auth.services.auth_service import AuthService

_SETTINGS = Settings(
    DATABASE_URL="postgresql://x:x@localhost/x",
    SECRET_KEY="test-secret-key-minimum-32-chars-ok",
    JWT_SECRET_KEY="test-jwt-secret-key-min-32-chars-ok!",
    AUTH_LOCKOUT_THRESHOLD=5,
    AUTH_LOCKOUT_DURATION_MINUTES=30,
    PASSWORD_MIN_LENGTH=12,
)


def _make_user(
    status: AccountStatus = AccountStatus.ACTIVE,
    failed_count: int = 0,
    locked_until=None,
    email_verified: bool = True,
) -> User:
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = "test@example.com"
    u.display_name = "Test User"
    u.account_status = status
    u.failed_login_count = failed_count
    u.locked_until = locked_until
    u.is_email_verified = email_verified
    return u


def _make_credentials(password_hash: str) -> UserCredentials:
    c = MagicMock(spec=UserCredentials)
    c.password_hash = password_hash
    c.password_history = []
    return c


def _make_session() -> SessionModel:
    s = MagicMock(spec=SessionModel)
    s.id = uuid.uuid4()
    s.user_id = uuid.uuid4()
    return s


def _make_request() -> MagicMock:
    req = MagicMock()
    req.headers = {"user-agent": "test-agent"}
    req.client = MagicMock()
    req.client.host = "127.0.0.1"
    return req


@pytest.fixture
def svc() -> AuthService:
    db = MagicMock()
    return AuthService(db=db, settings=_SETTINGS)


class TestLoginSuccess:
    def test_valid_credentials_return_login_result(self, svc: AuthService) -> None:
        from modules.auth.services.password_service import PasswordService

        password_svc = PasswordService(_SETTINGS)
        plain = "ValidPass@1234567"
        hashed = password_svc.hash_password(plain)

        user = _make_user()
        creds = _make_credentials(hashed)
        session = _make_session()

        svc._user_repo.find_by_email = MagicMock(return_value=user)
        svc._cred_repo.get_by_user_id = MagicMock(return_value=creds)
        svc._session_repo.create_session = MagicMock(return_value=session)
        svc._user_repo.update_failed_login_count = MagicMock()
        svc._token_svc.create_refresh_token = MagicMock(
            return_value=("raw_token_xyz", MagicMock())
        )
        svc._audit_svc.emit = MagicMock()

        result = svc.login("test@example.com", plain, False, _make_request())

        assert result.access_token
        assert result.refresh_token == "raw_token_xyz"
        assert result.token_type == "bearer"
        assert result.expires_in > 0

    def test_login_emits_success_audit_event(self, svc: AuthService) -> None:
        from modules.auth.services.password_service import PasswordService

        password_svc = PasswordService(_SETTINGS)
        plain = "ValidPass@1234567"
        hashed = password_svc.hash_password(plain)

        user = _make_user()
        creds = _make_credentials(hashed)
        session = _make_session()

        svc._user_repo.find_by_email = MagicMock(return_value=user)
        svc._cred_repo.get_by_user_id = MagicMock(return_value=creds)
        svc._session_repo.create_session = MagicMock(return_value=session)
        svc._user_repo.update_failed_login_count = MagicMock()
        svc._token_svc.create_refresh_token = MagicMock(
            return_value=("raw_token", MagicMock())
        )
        svc._audit_svc.emit = MagicMock()

        svc.login("test@example.com", plain, False, _make_request())

        calls = [c.args[0] for c in svc._audit_svc.emit.call_args_list]
        assert AuditEventType.LOGIN_SUCCESS in calls


class TestLoginFailure:
    def test_unknown_email_raises_auth_exception(self, svc: AuthService) -> None:
        svc._user_repo.find_by_email = MagicMock(return_value=None)
        svc._audit_svc.emit = MagicMock()

        with pytest.raises(AuthenticationException):
            svc.login("unknown@example.com", "AnyPass@1234567", False, _make_request())

    def test_wrong_password_raises_auth_exception(self, svc: AuthService) -> None:
        from modules.auth.services.password_service import PasswordService

        password_svc = PasswordService(_SETTINGS)
        hashed = password_svc.hash_password("CorrectPass@1234")

        user = _make_user()
        creds = _make_credentials(hashed)

        svc._user_repo.find_by_email = MagicMock(return_value=user)
        svc._cred_repo.get_by_user_id = MagicMock(return_value=creds)
        svc._user_repo.update_failed_login_count = MagicMock()
        svc._audit_svc.emit = MagicMock()

        with pytest.raises(AuthenticationException):
            svc.login("test@example.com", "WrongPass@1234", False, _make_request())

    def test_wrong_password_increments_failed_count(self, svc: AuthService) -> None:
        from modules.auth.services.password_service import PasswordService

        password_svc = PasswordService(_SETTINGS)
        hashed = password_svc.hash_password("CorrectPass@1234")

        user = _make_user(failed_count=2)
        creds = _make_credentials(hashed)

        svc._user_repo.find_by_email = MagicMock(return_value=user)
        svc._cred_repo.get_by_user_id = MagicMock(return_value=creds)
        svc._user_repo.update_failed_login_count = MagicMock()
        svc._user_repo.lock_account = MagicMock()
        svc._audit_svc.emit = MagicMock()

        with pytest.raises(AuthenticationException):
            svc.login("test@example.com", "WrongPass@1234", False, _make_request())

        svc._user_repo.update_failed_login_count.assert_called_once_with(user.id, 3)

    def test_fifth_failure_locks_account(self, svc: AuthService) -> None:
        from modules.auth.services.password_service import PasswordService

        password_svc = PasswordService(_SETTINGS)
        hashed = password_svc.hash_password("CorrectPass@1234")

        user = _make_user(failed_count=4)
        creds = _make_credentials(hashed)

        svc._user_repo.find_by_email = MagicMock(return_value=user)
        svc._cred_repo.get_by_user_id = MagicMock(return_value=creds)
        svc._user_repo.update_failed_login_count = MagicMock()
        svc._user_repo.lock_account = MagicMock()
        svc._audit_svc.emit = MagicMock()

        with pytest.raises(AuthenticationException):
            svc.login("test@example.com", "WrongPass@1234", False, _make_request())

        svc._user_repo.lock_account.assert_called_once()

    def test_fifth_failure_emits_account_locked_event(self, svc: AuthService) -> None:
        from modules.auth.services.password_service import PasswordService

        password_svc = PasswordService(_SETTINGS)
        hashed = password_svc.hash_password("CorrectPass@1234")

        user = _make_user(failed_count=4)
        creds = _make_credentials(hashed)

        svc._user_repo.find_by_email = MagicMock(return_value=user)
        svc._cred_repo.get_by_user_id = MagicMock(return_value=creds)
        svc._user_repo.update_failed_login_count = MagicMock()
        svc._user_repo.lock_account = MagicMock()
        svc._audit_svc.emit = MagicMock()

        with pytest.raises(AuthenticationException):
            svc.login("test@example.com", "WrongPass@1234", False, _make_request())

        event_types = [c.args[0] for c in svc._audit_svc.emit.call_args_list]
        assert AuditEventType.ACCOUNT_LOCKED in event_types

    def test_locked_account_raises_account_locked(self, svc: AuthService) -> None:
        user = _make_user(
            status=AccountStatus.LOCKED,
            locked_until=utcnow() + timedelta(minutes=25),
        )

        svc._user_repo.find_by_email = MagicMock(return_value=user)
        svc._audit_svc.emit = MagicMock()

        with pytest.raises(AccountLockedException):
            svc.login("test@example.com", "AnyPass@1234", False, _make_request())

    def test_locked_account_past_expiry_auto_unlocks(self, svc: AuthService) -> None:
        from modules.auth.services.password_service import PasswordService

        password_svc = PasswordService(_SETTINGS)
        plain = "ValidPass@1234567"
        hashed = password_svc.hash_password(plain)

        user = _make_user(
            status=AccountStatus.LOCKED,
            locked_until=utcnow() - timedelta(minutes=5),
        )
        creds = _make_credentials(hashed)
        session = _make_session()

        svc._user_repo.find_by_email = MagicMock(return_value=user)
        svc._cred_repo.get_by_user_id = MagicMock(return_value=creds)
        svc._user_repo.unlock_account = MagicMock()
        svc._session_repo.create_session = MagicMock(return_value=session)
        svc._user_repo.update_failed_login_count = MagicMock()
        svc._token_svc.create_refresh_token = MagicMock(
            return_value=("raw_token", MagicMock())
        )
        svc._audit_svc.emit = MagicMock()

        result = svc.login("test@example.com", plain, False, _make_request())
        svc._user_repo.unlock_account.assert_called_once_with(user.id)
        assert result.access_token

    def test_inactive_account_raises_inactive_exception(self, svc: AuthService) -> None:
        user = _make_user(status=AccountStatus.INACTIVE)
        svc._user_repo.find_by_email = MagicMock(return_value=user)
        svc._audit_svc.emit = MagicMock()

        with pytest.raises(AccountInactiveException):
            svc.login("test@example.com", "AnyPass@1234", False, _make_request())

    def test_deleted_account_raises_auth_exception(self, svc: AuthService) -> None:
        user = _make_user(status=AccountStatus.DELETED)
        svc._user_repo.find_by_email = MagicMock(return_value=user)
        svc._audit_svc.emit = MagicMock()

        with pytest.raises(AuthenticationException):
            svc.login("test@example.com", "AnyPass@1234", False, _make_request())

    def test_wrong_password_emits_login_failure_event(self, svc: AuthService) -> None:
        from modules.auth.services.password_service import PasswordService

        password_svc = PasswordService(_SETTINGS)
        hashed = password_svc.hash_password("CorrectPass@1234")

        user = _make_user()
        creds = _make_credentials(hashed)

        svc._user_repo.find_by_email = MagicMock(return_value=user)
        svc._cred_repo.get_by_user_id = MagicMock(return_value=creds)
        svc._user_repo.update_failed_login_count = MagicMock()
        svc._user_repo.lock_account = MagicMock()
        svc._audit_svc.emit = MagicMock()

        with pytest.raises(AuthenticationException):
            svc.login("test@example.com", "WrongPass@1234", False, _make_request())

        event_types = [c.args[0] for c in svc._audit_svc.emit.call_args_list]
        assert AuditEventType.LOGIN_FAILURE in event_types

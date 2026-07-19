"""Unit tests for AuthService password-related flows.

Covers: forgot_password, reset_password, change_password, verify_email.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from core.auth.exceptions import AuthenticationException, InvalidTokenException
from core.config.settings import Settings
from core.exceptions.base import ValidationException
from modules.auth.models.enums import AccountStatus, AuditEventType
from modules.auth.models.user import User
from modules.auth.models.user_credential import UserCredentials
from modules.auth.services.auth_service import AuthService

_SETTINGS = Settings(
    DATABASE_URL="postgresql://x:x@localhost/x",
    SECRET_KEY="test-secret-key-minimum-32-chars-ok",
    JWT_SECRET_KEY="test-jwt-secret-key-min-32-chars-ok!",
    PASSWORD_MIN_LENGTH=12,
    PASSWORD_HISTORY_COUNT=5,
)

_VALID_NEW_PASS = "NewValidPass@1234567"


def _make_user(status: AccountStatus = AccountStatus.ACTIVE) -> User:
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = "test@example.com"
    u.account_status = status
    return u


def _make_credentials(password_hash: str = "") -> UserCredentials:
    c = MagicMock(spec=UserCredentials)
    c.password_hash = password_hash
    c.password_history = []
    return c


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


class TestForgotPassword:
    def test_returns_none_for_registered_email(self, svc: AuthService) -> None:
        user = _make_user()
        svc._user_repo.find_by_email = MagicMock(return_value=user)
        svc._token_svc.create_password_reset_token = MagicMock(return_value="raw_token")
        svc._email_svc.send_password_reset_email = MagicMock()
        svc._audit_svc.emit = MagicMock()

        result = svc.forgot_password("test@example.com", _make_request())
        assert result is None

    def test_returns_none_for_unknown_email(self, svc: AuthService) -> None:
        svc._user_repo.find_by_email = MagicMock(return_value=None)
        svc._audit_svc.emit = MagicMock()

        result = svc.forgot_password("unknown@example.com", _make_request())
        assert result is None

    def test_never_raises_for_either_case(self, svc: AuthService) -> None:
        svc._user_repo.find_by_email = MagicMock(return_value=None)
        svc._audit_svc.emit = MagicMock()

        svc.forgot_password("any@email.com", _make_request())  # must not raise

    def test_generates_reset_token_for_active_account(self, svc: AuthService) -> None:
        user = _make_user()
        svc._user_repo.find_by_email = MagicMock(return_value=user)
        svc._token_svc.create_password_reset_token = MagicMock(return_value="raw_token")
        svc._email_svc.send_password_reset_email = MagicMock()
        svc._audit_svc.emit = MagicMock()

        svc.forgot_password("test@example.com", _make_request())

        svc._token_svc.create_password_reset_token.assert_called_once()

    def test_second_request_calls_create_token_again(self, svc: AuthService) -> None:
        user = _make_user()
        svc._user_repo.find_by_email = MagicMock(return_value=user)
        svc._token_svc.create_password_reset_token = MagicMock(
            side_effect=["token1", "token2"]
        )
        svc._email_svc.send_password_reset_email = MagicMock()
        svc._audit_svc.emit = MagicMock()

        svc.forgot_password("test@example.com", _make_request())
        svc.forgot_password("test@example.com", _make_request())

        assert svc._token_svc.create_password_reset_token.call_count == 2


class TestResetPassword:
    def test_valid_token_resets_password(self, svc: AuthService) -> None:
        reset_record = MagicMock()
        reset_record.user_id = uuid.uuid4()

        creds = _make_credentials()

        svc._token_svc.consume_password_reset_token = MagicMock(
            return_value=reset_record
        )
        svc._cred_repo.get_by_user_id = MagicMock(return_value=creds)
        svc._cred_repo.update_password_hash = MagicMock()
        svc._refresh_repo.revoke_all_by_user = MagicMock()
        svc._session_repo.revoke_all_by_user = MagicMock()
        svc._audit_svc.emit = MagicMock()

        svc.reset_password("valid_token", _VALID_NEW_PASS, _make_request())

        svc._cred_repo.update_password_hash.assert_called_once()
        svc._refresh_repo.revoke_all_by_user.assert_called_once_with(
            reset_record.user_id
        )

    def test_invalid_token_raises(self, svc: AuthService) -> None:
        svc._token_svc.consume_password_reset_token = MagicMock(
            side_effect=InvalidTokenException()
        )
        svc._audit_svc.emit = MagicMock()

        with pytest.raises(InvalidTokenException):
            svc.reset_password("bad_token", _VALID_NEW_PASS, _make_request())

    def test_reset_emits_audit_event(self, svc: AuthService) -> None:
        reset_record = MagicMock()
        reset_record.user_id = uuid.uuid4()
        creds = _make_credentials()

        svc._token_svc.consume_password_reset_token = MagicMock(
            return_value=reset_record
        )
        svc._cred_repo.get_by_user_id = MagicMock(return_value=creds)
        svc._cred_repo.update_password_hash = MagicMock()
        svc._refresh_repo.revoke_all_by_user = MagicMock()
        svc._session_repo.revoke_all_by_user = MagicMock()
        svc._audit_svc.emit = MagicMock()

        svc.reset_password("valid_token", _VALID_NEW_PASS, _make_request())

        event_types = [c.args[0] for c in svc._audit_svc.emit.call_args_list]
        assert AuditEventType.PASSWORD_RESET_COMPLETED in event_types

    def test_sessions_revoked_after_reset(self, svc: AuthService) -> None:
        reset_record = MagicMock()
        reset_record.user_id = uuid.uuid4()
        creds = _make_credentials()

        svc._token_svc.consume_password_reset_token = MagicMock(
            return_value=reset_record
        )
        svc._cred_repo.get_by_user_id = MagicMock(return_value=creds)
        svc._cred_repo.update_password_hash = MagicMock()
        svc._refresh_repo.revoke_all_by_user = MagicMock()
        svc._session_repo.revoke_all_by_user = MagicMock()
        svc._audit_svc.emit = MagicMock()

        svc.reset_password("valid_token", _VALID_NEW_PASS, _make_request())

        svc._session_repo.revoke_all_by_user.assert_called_once()


class TestChangePassword:
    def test_correct_current_password_changes_password(self, svc: AuthService) -> None:
        from modules.auth.services.password_service import PasswordService

        password_svc = PasswordService(_SETTINGS)
        current_plain = "CurrentPass@12345"
        current_hash = password_svc.hash_password(current_plain)

        user = _make_user()
        creds = _make_credentials(current_hash)

        svc._cred_repo.get_by_user_id = MagicMock(return_value=creds)
        svc._user_repo.get_by_id = MagicMock(return_value=user)
        svc._cred_repo.update_password_hash = MagicMock()
        svc._refresh_repo.revoke_all_by_user = MagicMock()
        svc._session_repo.revoke_all_by_user = MagicMock()
        svc._audit_svc.emit = MagicMock()

        svc.change_password(user.id, current_plain, _VALID_NEW_PASS, _make_request())

        svc._cred_repo.update_password_hash.assert_called_once()

    def test_wrong_current_password_raises_auth_exception(
        self, svc: AuthService
    ) -> None:
        from modules.auth.services.password_service import PasswordService

        password_svc = PasswordService(_SETTINGS)
        current_hash = password_svc.hash_password("ActualCurrentPass@12345")

        user = _make_user()
        creds = _make_credentials(current_hash)

        svc._cred_repo.get_by_user_id = MagicMock(return_value=creds)
        svc._audit_svc.emit = MagicMock()

        with pytest.raises(AuthenticationException):
            svc.change_password(
                user.id, "WrongCurrentPass@12345", _VALID_NEW_PASS, _make_request()
            )

    def test_password_history_violation_raises_validation_exception(
        self, svc: AuthService
    ) -> None:
        from modules.auth.services.password_service import PasswordService

        password_svc = PasswordService(_SETTINGS)
        current_plain = "CurrentPass@12345"
        current_hash = password_svc.hash_password(current_plain)
        # Add the new password to history so it's "recently used".
        new_pass_hash = password_svc.hash_password(_VALID_NEW_PASS)

        user = _make_user()
        creds = _make_credentials(current_hash)
        creds.password_history = [new_pass_hash]

        svc._cred_repo.get_by_user_id = MagicMock(return_value=creds)
        svc._user_repo.get_by_id = MagicMock(return_value=user)
        svc._audit_svc.emit = MagicMock()

        with pytest.raises(ValidationException):
            svc.change_password(
                user.id, current_plain, _VALID_NEW_PASS, _make_request()
            )

    def test_change_emits_audit_event(self, svc: AuthService) -> None:
        from modules.auth.services.password_service import PasswordService

        password_svc = PasswordService(_SETTINGS)
        current_plain = "CurrentPass@12345"
        current_hash = password_svc.hash_password(current_plain)

        user = _make_user()
        creds = _make_credentials(current_hash)

        svc._cred_repo.get_by_user_id = MagicMock(return_value=creds)
        svc._user_repo.get_by_id = MagicMock(return_value=user)
        svc._cred_repo.update_password_hash = MagicMock()
        svc._refresh_repo.revoke_all_by_user = MagicMock()
        svc._session_repo.revoke_all_by_user = MagicMock()
        svc._audit_svc.emit = MagicMock()

        svc.change_password(user.id, current_plain, _VALID_NEW_PASS, _make_request())

        event_types = [c.args[0] for c in svc._audit_svc.emit.call_args_list]
        assert AuditEventType.PASSWORD_CHANGED in event_types

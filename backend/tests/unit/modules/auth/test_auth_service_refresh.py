"""Unit tests for AuthService.refresh."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from core.auth.exceptions import (
    AccountInactiveException,
    TokenExpiredException,
    TokenRevokedException,
)
from core.config.settings import Settings
from modules.auth.models.enums import AccountStatus, AuditEventType
from modules.auth.models.user import User
from modules.auth.services.auth_service import AuthService

_SETTINGS = Settings(
    DATABASE_URL="postgresql://x:x@localhost/x",
    SECRET_KEY="test-secret-key-minimum-32-chars-ok",
    JWT_SECRET_KEY="test-jwt-secret-key-min-32-chars-ok!",
)


def _make_user(status: AccountStatus = AccountStatus.ACTIVE) -> User:
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = "test@example.com"
    u.account_status = status
    return u


def _make_refresh_record(user_id: uuid.UUID, session_id: uuid.UUID) -> MagicMock:
    r = MagicMock()
    r.user_id = user_id
    r.session_id = session_id
    return r


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


class TestTokenRefresh:
    def test_valid_refresh_returns_new_tokens(self, svc: AuthService) -> None:
        user_id = uuid.uuid4()
        session_id = uuid.uuid4()
        user = _make_user()
        user.id = user_id

        new_refresh_record = _make_refresh_record(user_id, session_id)

        svc._token_svc.rotate_refresh_token = MagicMock(
            return_value=("new_raw_token", new_refresh_record)
        )
        svc._user_repo.get_by_id = MagicMock(return_value=user)
        svc._audit_svc.emit = MagicMock()

        result = svc.refresh("old_raw_token", _make_request())

        assert result.access_token
        assert result.refresh_token == "new_raw_token"
        assert result.expires_in > 0

    def test_expired_refresh_token_raises(self, svc: AuthService) -> None:
        svc._token_svc.rotate_refresh_token = MagicMock(
            side_effect=TokenExpiredException()
        )
        svc._audit_svc.emit = MagicMock()

        with pytest.raises(TokenExpiredException):
            svc.refresh("expired_token", _make_request())

    def test_revoked_refresh_token_raises(self, svc: AuthService) -> None:
        svc._token_svc.rotate_refresh_token = MagicMock(
            side_effect=TokenRevokedException()
        )
        svc._audit_svc.emit = MagicMock()

        with pytest.raises(TokenRevokedException):
            svc.refresh("revoked_token", _make_request())

    def test_refresh_emits_token_refreshed_audit_event(self, svc: AuthService) -> None:
        user_id = uuid.uuid4()
        session_id = uuid.uuid4()
        user = _make_user()
        user.id = user_id

        new_refresh_record = _make_refresh_record(user_id, session_id)

        svc._token_svc.rotate_refresh_token = MagicMock(
            return_value=("new_raw_token", new_refresh_record)
        )
        svc._user_repo.get_by_id = MagicMock(return_value=user)
        svc._audit_svc.emit = MagicMock()

        svc.refresh("old_raw_token", _make_request())

        event_types = [c.args[0] for c in svc._audit_svc.emit.call_args_list]
        assert AuditEventType.TOKEN_REFRESHED in event_types

    def test_inactive_account_raises_after_rotation(self, svc: AuthService) -> None:
        user_id = uuid.uuid4()
        session_id = uuid.uuid4()
        user = _make_user(status=AccountStatus.INACTIVE)
        user.id = user_id

        new_refresh_record = _make_refresh_record(user_id, session_id)

        svc._token_svc.rotate_refresh_token = MagicMock(
            return_value=("new_raw_token", new_refresh_record)
        )
        svc._user_repo.get_by_id = MagicMock(return_value=user)
        svc._audit_svc.emit = MagicMock()

        with pytest.raises(AccountInactiveException):
            svc.refresh("old_raw_token", _make_request())

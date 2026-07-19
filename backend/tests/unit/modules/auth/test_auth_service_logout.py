"""Unit tests for AuthService.logout."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from core.config.settings import Settings
from modules.auth.models.enums import AuditEventType
from modules.auth.services.auth_service import AuthService

_SETTINGS = Settings(
    DATABASE_URL="postgresql://x:x@localhost/x",
    SECRET_KEY="test-secret-key-minimum-32-chars-ok",
    JWT_SECRET_KEY="test-jwt-secret-key-min-32-chars-ok!",
)


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


class TestLogout:
    def test_logout_revokes_session_refresh_tokens(self, svc: AuthService) -> None:
        user_id = uuid.uuid4()
        session_id = uuid.uuid4()

        svc._session_repo.revoke_session = MagicMock()
        svc._audit_svc.emit = MagicMock()

        with MagicMock() as mock_repo_cls:
            mock_repo_instance = MagicMock()
            mock_repo_cls.return_value = mock_repo_instance

            import modules.auth.repositories.refresh_token_repository as rtr_module

            original = rtr_module.RefreshTokenRepository
            rtr_module.RefreshTokenRepository = mock_repo_cls

            svc.logout(user_id=user_id, session_id=session_id, request=_make_request())

            rtr_module.RefreshTokenRepository = original

        svc._session_repo.revoke_session.assert_called_once_with(session_id)

    def test_logout_emits_logout_audit_event(self, svc: AuthService) -> None:
        user_id = uuid.uuid4()
        session_id = uuid.uuid4()

        svc._session_repo.revoke_session = MagicMock()
        svc._audit_svc.emit = MagicMock()

        with MagicMock() as mock_repo_cls:
            mock_instance = MagicMock()
            mock_repo_cls.return_value = mock_instance

            import modules.auth.repositories.refresh_token_repository as rtr_module

            original = rtr_module.RefreshTokenRepository
            rtr_module.RefreshTokenRepository = mock_repo_cls

            svc.logout(user_id=user_id, session_id=session_id, request=_make_request())

            rtr_module.RefreshTokenRepository = original

        event_types = [c.args[0] for c in svc._audit_svc.emit.call_args_list]
        assert AuditEventType.LOGOUT in event_types

    def test_logout_is_idempotent(self, svc: AuthService) -> None:
        """Calling logout twice on same session must not raise."""
        user_id = uuid.uuid4()
        session_id = uuid.uuid4()

        svc._session_repo.revoke_session = MagicMock()
        svc._audit_svc.emit = MagicMock()

        import modules.auth.repositories.refresh_token_repository as rtr_module

        original = rtr_module.RefreshTokenRepository
        rtr_module.RefreshTokenRepository = MagicMock(return_value=MagicMock())

        svc.logout(user_id=user_id, session_id=session_id, request=_make_request())
        svc.logout(user_id=user_id, session_id=session_id, request=_make_request())

        rtr_module.RefreshTokenRepository = original

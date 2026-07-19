"""T106 — Unit tests for TokenService (mocked repositories).

Covers refresh token lifecycle, password reset token lifecycle, and
replay/theft detection.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from core.auth.exceptions import (
    InvalidTokenException,
    TokenExpiredException,
    TokenRevokedException,
)
from core.config.settings import Settings
from core.utils.datetime import utcnow
from modules.auth.models.password_reset_token import PasswordResetToken
from modules.auth.models.refresh_token import RefreshToken
from modules.auth.services.token_service import TokenService

_SETTINGS = Settings(
    DATABASE_URL="postgresql://x:x@localhost/x",
    SECRET_KEY="test-secret-key-minimum-32-chars-ok",
    JWT_SECRET_KEY="test-jwt-secret-key-min-32-chars-ok!",
    JWT_REFRESH_TOKEN_EXPIRE_DAYS=7,
    JWT_REMEMBER_ME_EXPIRE_DAYS=30,
)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def svc(mock_db: MagicMock) -> TokenService:
    return TokenService(db=mock_db, settings=_SETTINGS)


class TestCreateRefreshToken:
    def test_returns_raw_token_and_record(self, svc: TokenService) -> None:
        user_id = uuid.uuid4()
        session_id = uuid.uuid4()

        mock_record = MagicMock(spec=RefreshToken)
        mock_record.id = uuid.uuid4()

        with patch.object(svc._refresh_repo, "create", return_value=mock_record):
            raw_token, record = svc.create_refresh_token(
                user_id=user_id,
                session_id=session_id,
                remember_me=False,
                ip="127.0.0.1",
                user_agent="test",
            )

        assert isinstance(raw_token, str)
        assert len(raw_token) > 0
        assert record is mock_record

    def test_raw_token_differs_from_stored_hash(self, svc: TokenService) -> None:
        user_id = uuid.uuid4()
        session_id = uuid.uuid4()

        captured_hash: list[str] = []

        def _capture_create(**kwargs):  # type: ignore[no-untyped-def]
            captured_hash.append(kwargs["token_hash"])
            rec = MagicMock(spec=RefreshToken)
            rec.id = uuid.uuid4()
            return rec

        with patch.object(svc._refresh_repo, "create", side_effect=_capture_create):
            raw_token, _ = svc.create_refresh_token(
                user_id=user_id,
                session_id=session_id,
                remember_me=False,
                ip=None,
                user_agent=None,
            )

        assert len(captured_hash) == 1
        assert captured_hash[0] != raw_token
        assert captured_hash[0] == _sha256(raw_token)


class TestRotateRefreshToken:
    def _make_old_token_record(
        self, user_id: uuid.UUID, session_id: uuid.UUID, *, revoked: bool = False
    ) -> tuple[str, MagicMock]:
        raw = secrets.token_urlsafe(32)
        record = MagicMock(spec=RefreshToken)
        record.id = uuid.uuid4()
        record.user_id = user_id
        record.session_id = session_id
        record.remember_me = False
        record.is_revoked = revoked
        record.expires_at = utcnow() + timedelta(days=7)
        return raw, record

    def test_revokes_old_and_returns_new(self, svc: TokenService) -> None:
        user_id = uuid.uuid4()
        session_id = uuid.uuid4()
        raw, old_record = self._make_old_token_record(user_id, session_id)

        new_raw = secrets.token_urlsafe(32)
        new_record = MagicMock(spec=RefreshToken)
        new_record.id = uuid.uuid4()

        with (
            patch.object(
                svc._refresh_repo, "find_by_token_hash", return_value=old_record
            ),
            patch.object(svc._refresh_repo, "revoke") as mock_revoke,
            patch.object(
                svc, "create_refresh_token", return_value=(new_raw, new_record)
            ),
        ):

            result_raw, result_record = svc.rotate_refresh_token(
                raw, ip=None, user_agent=None
            )

        mock_revoke.assert_called_once_with(old_record.id)
        assert result_raw == new_raw
        assert result_record is new_record

    def test_expired_token_raises(self, svc: TokenService) -> None:
        user_id = uuid.uuid4()
        session_id = uuid.uuid4()
        raw, old_record = self._make_old_token_record(user_id, session_id)
        old_record.expires_at = utcnow() - timedelta(minutes=1)  # expired

        with patch.object(
            svc._refresh_repo, "find_by_token_hash", return_value=old_record
        ):
            with pytest.raises(TokenExpiredException):
                svc.rotate_refresh_token(raw, ip=None, user_agent=None)

    def test_revoked_token_raises_and_revokes_all(self, svc: TokenService) -> None:
        user_id = uuid.uuid4()
        session_id = uuid.uuid4()
        raw, old_record = self._make_old_token_record(user_id, session_id, revoked=True)

        with (
            patch.object(
                svc._refresh_repo, "find_by_token_hash", return_value=old_record
            ),
            patch.object(svc._refresh_repo, "revoke_all_by_user") as mock_revoke_all,
        ):

            with pytest.raises(TokenRevokedException):
                svc.rotate_refresh_token(raw, ip=None, user_agent=None)

        mock_revoke_all.assert_called_once_with(user_id)

    def test_unknown_token_raises_invalid(self, svc: TokenService) -> None:
        with patch.object(svc._refresh_repo, "find_by_token_hash", return_value=None):
            with pytest.raises(InvalidTokenException):
                svc.rotate_refresh_token("no-such-token", ip=None, user_agent=None)


class TestConsumePasswordResetToken:
    def _make_reset_record(
        self, *, consumed: bool = False, expired: bool = False
    ) -> tuple[str, MagicMock]:
        raw = secrets.token_urlsafe(32)
        record = MagicMock(spec=PasswordResetToken)
        record.id = uuid.uuid4()
        record.user_id = uuid.uuid4()
        record.is_consumed = consumed
        record.expires_at = (
            utcnow() - timedelta(minutes=1)
            if expired
            else utcnow() + timedelta(hours=1)
        )
        return raw, record

    def test_valid_token_marks_consumed(self, svc: TokenService) -> None:
        raw, record = self._make_reset_record()

        with (
            patch.object(svc._reset_repo, "find_by_token_hash", return_value=record),
            patch.object(svc._reset_repo, "mark_consumed") as mock_consumed,
        ):

            result = svc.consume_password_reset_token(raw)

        mock_consumed.assert_called_once_with(record.id)
        assert result is record

    def test_expired_token_raises(self, svc: TokenService) -> None:
        raw, record = self._make_reset_record(expired=True)

        with patch.object(svc._reset_repo, "find_by_token_hash", return_value=record):
            with pytest.raises(TokenExpiredException):
                svc.consume_password_reset_token(raw)

    def test_consumed_token_raises(self, svc: TokenService) -> None:
        raw, record = self._make_reset_record(consumed=True)

        with patch.object(svc._reset_repo, "find_by_token_hash", return_value=record):
            with pytest.raises(InvalidTokenException):
                svc.consume_password_reset_token(raw)

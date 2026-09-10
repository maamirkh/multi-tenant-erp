"""Unit tests for ProfileService — Phase 6 (US4).

Tests: profile retrieval, profile update, avatar upload (valid format,
too large, invalid format), avatar delete, previous URL retention.

Spec reference: tasks T065.
"""

from __future__ import annotations

import uuid
from typing import cast
from unittest.mock import MagicMock

import pytest

from modules.users_roles.exceptions import (
    AvatarInvalidFormatError,
    AvatarTooLargeError,
)
from modules.users_roles.services.profile_service import ProfileService

# ---------------------------------------------------------------------------
# Magic-byte test fixtures
# ---------------------------------------------------------------------------
_JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 100
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
_WEBP_BYTES = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
_GIF_BYTES = b"GIF89a" + b"\x00" * 100  # not allowed for avatars
_TEXT_BYTES = b"hello world" * 20


def _make_settings(*, max_bytes: int = 5 * 1024 * 1024, retention_days: int = 30):
    s = MagicMock()
    s.USER_AVATAR_MAX_BYTES = max_bytes
    s.AVATAR_RETENTION_DAYS = retention_days
    return s


def _make_user(
    *,
    user_id: uuid.UUID | None = None,
    display_name: str = "Alice",
    phone: str | None = None,
    avatar_url: str | None = None,
    avatar_previous_url: str | None = None,
    email: str = "alice@example.com",
):
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.display_name = display_name
    user.phone = phone
    user.avatar_url = avatar_url
    user.avatar_previous_url = avatar_previous_url
    user.email = email
    return user


def _make_service(
    *,
    user: MagicMock | None = None,
    max_bytes: int = 5 * 1024 * 1024,
    storage_url: str = "https://s3.example.com/avatars/u/img.jpg",
) -> tuple[ProfileService, MagicMock, MagicMock]:
    """Return (service, user_repo_mock, storage_mock)."""
    db = MagicMock()
    user_repo = MagicMock()
    storage = MagicMock()
    settings = _make_settings(max_bytes=max_bytes)

    if user is not None:
        user_repo.get_by_id.return_value = user
    storage.upload.return_value = storage_url

    service = ProfileService(
        db=db,
        user_repo=user_repo,
        storage=storage,
        settings=settings,
    )
    return service, user_repo, storage


# ---------------------------------------------------------------------------
# TestGetProfile
# ---------------------------------------------------------------------------


class TestGetProfile:
    def test_returns_user(self):
        user = _make_user()
        service, user_repo, _ = _make_service(user=user)

        result = service.get_profile(user.id)

        user_repo.get_by_id.assert_called_once_with(user.id)
        assert result is user


# ---------------------------------------------------------------------------
# TestUpdateProfile
# ---------------------------------------------------------------------------


class TestUpdateProfile:
    def test_updates_display_name(self):
        user = _make_user(display_name="Old Name")
        service, _, _ = _make_service(user=user)

        result = service.update_profile(user.id, display_name="New Name")

        assert user.display_name == "New Name"

    def test_updates_phone(self):
        user = _make_user()
        service, _, _ = _make_service(user=user)

        result = service.update_profile(user.id, phone="+44 7911 123456")

        assert user.phone == "+44 7911 123456"

    def test_clears_phone_with_none(self):
        user = _make_user(phone="+1 555 0100")
        service, _, _ = _make_service(user=user)

        result = service.update_profile(user.id, phone=None)

        assert user.phone is None

    def test_sentinel_does_not_change_phone(self):
        """Passing phone=... (sentinel) must leave phone unchanged."""
        user = _make_user(phone="+1 555 0100")
        service, _, _ = _make_service(user=user)

        # phone uses sentinel default (...)
        service.update_profile(user.id, display_name="Updated")

        assert user.phone == "+1 555 0100"

    def test_commits_and_refreshes(self):
        user = _make_user()
        service, _, _ = _make_service(user=user)

        service.update_profile(user.id, display_name="X")

        cast(MagicMock, service._db).commit.assert_called_once()
        cast(MagicMock, service._db).refresh.assert_called_once_with(user)


# ---------------------------------------------------------------------------
# TestUploadAvatar
# ---------------------------------------------------------------------------


class TestUploadAvatar:
    def test_jpeg_upload_succeeds(self):
        user = _make_user()
        service, _, storage = _make_service(user=user, storage_url="https://s3/a.jpg")

        url = service.upload_avatar(user.id, file_bytes=_JPEG_BYTES, filename="a.jpg")

        assert url == "https://s3/a.jpg"
        storage.upload.assert_called_once()

    def test_png_upload_succeeds(self):
        user = _make_user()
        service, _, storage = _make_service(user=user, storage_url="https://s3/a.png")

        url = service.upload_avatar(user.id, file_bytes=_PNG_BYTES, filename="a.png")

        assert url == "https://s3/a.png"

    def test_webp_upload_succeeds(self):
        user = _make_user()
        service, _, storage = _make_service(user=user)

        url = service.upload_avatar(user.id, file_bytes=_WEBP_BYTES, filename="a.webp")

        assert url is not None

    def test_stores_previous_url_for_retention(self):
        user = _make_user(avatar_url="https://s3/old.jpg")
        service, _, _ = _make_service(user=user)

        service.upload_avatar(user.id, file_bytes=_PNG_BYTES, filename="new.png")

        assert user.avatar_previous_url == "https://s3/old.jpg"

    def test_updates_avatar_url_to_new_url(self):
        user = _make_user()
        service, _, _ = _make_service(user=user, storage_url="https://s3/new.jpg")

        service.upload_avatar(user.id, file_bytes=_JPEG_BYTES, filename="new.jpg")

        assert user.avatar_url == "https://s3/new.jpg"

    def test_too_large_raises_error(self):
        user = _make_user()
        service, _, _ = _make_service(user=user, max_bytes=10)

        with pytest.raises(AvatarTooLargeError):
            service.upload_avatar(user.id, file_bytes=b"\x00" * 100, filename="big.jpg")

    def test_invalid_format_gif_raises_error(self):
        """GIF is not allowed for avatars (only JPEG, PNG, WebP)."""
        user = _make_user()
        service, _, _ = _make_service(user=user)

        with pytest.raises(AvatarInvalidFormatError):
            service.upload_avatar(user.id, file_bytes=_GIF_BYTES, filename="anim.gif")

    def test_invalid_format_plain_text_raises_error(self):
        user = _make_user()
        service, _, _ = _make_service(user=user)

        with pytest.raises(AvatarInvalidFormatError):
            service.upload_avatar(user.id, file_bytes=_TEXT_BYTES, filename="text.txt")

    def test_key_uses_user_id_folder(self):
        """Uploaded S3 key must contain the user_id as folder segment."""
        user = _make_user()
        service, _, storage = _make_service(user=user)

        service.upload_avatar(user.id, file_bytes=_PNG_BYTES, filename="a.png")

        call_args = storage.upload.call_args
        key = call_args[0][1]  # second positional arg is the key
        assert str(user.id) in key


# ---------------------------------------------------------------------------
# TestDeleteAvatar
# ---------------------------------------------------------------------------


class TestDeleteAvatar:
    def test_clears_avatar_url(self):
        user = _make_user(avatar_url="https://s3/old.jpg")
        service, _, _ = _make_service(user=user)

        service.delete_avatar(user.id)

        assert user.avatar_url is None

    def test_stores_previous_url_for_retention(self):
        user = _make_user(avatar_url="https://s3/keep.jpg")
        service, _, _ = _make_service(user=user)

        service.delete_avatar(user.id)

        assert user.avatar_previous_url == "https://s3/keep.jpg"

    def test_s3_file_not_deleted(self):
        """File must NOT be deleted from storage during avatar removal."""
        user = _make_user(avatar_url="https://s3/keep.jpg")
        service, _, storage = _make_service(user=user)

        service.delete_avatar(user.id)

        storage.delete.assert_not_called()

    def test_commits_on_delete(self):
        user = _make_user(avatar_url="https://s3/old.jpg")
        service, _, _ = _make_service(user=user)

        service.delete_avatar(user.id)

        cast(MagicMock, service._db).commit.assert_called_once()

    def test_no_error_when_no_avatar(self):
        """Calling delete when avatar_url is None should not raise."""
        user = _make_user(avatar_url=None)
        service, _, _ = _make_service(user=user)

        service.delete_avatar(user.id)  # must not raise

        assert user.avatar_url is None

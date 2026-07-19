"""ProfileService — business logic for user profile and avatar management.

Handles:
- get_profile: load the current user record
- update_profile: update display_name and/or phone
- upload_avatar: validate format/size, upload to S3, store previous URL
- delete_avatar: clear avatar_url while retaining file for AVATAR_RETENTION_DAYS

Avatar format validation uses raw magic-byte inspection (no external
python-magic dependency required).  Allowed formats: JPEG, PNG, WebP.

Spec reference: spec.md FR-010 through FR-015, tasks T058.
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import BinaryIO, Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from core.config.settings import Settings
from modules.auth.models.user import User
from modules.auth.repositories.user_repository import UserRepository
from modules.users_roles.exceptions import (
    AvatarInvalidFormatError,
    AvatarTooLargeError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Avatar MIME detection
# ---------------------------------------------------------------------------

_AVATAR_ALLOWED_MIMES: frozenset[str] = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)

_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
]


def _detect_avatar_mime(file_bytes: bytes) -> str | None:
    """Return the MIME type from magic bytes, or ``None`` if unrecognised."""
    if len(file_bytes) >= 12:
        # WebP: RIFF????WEBP
        if file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP":
            return "image/webp"

    for signature, mime_type in _MAGIC_SIGNATURES:
        if file_bytes[: len(signature)] == signature:
            return mime_type

    return None


def _mime_to_ext(mime_type: str) -> str:
    """Return the file extension for the given MIME type."""
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(
        mime_type, ""
    )


# ---------------------------------------------------------------------------
# Storage protocol — avoids direct boto3 import at module load time
# ---------------------------------------------------------------------------


class _StorageProtocol(Protocol):
    """Structural subtype of ``StorageClient`` accepted by ``ProfileService``."""

    def upload(self, file: BinaryIO, key: str) -> str: ...  # noqa: E704

    def get_url(self, key: str) -> str: ...  # noqa: E704


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ProfileService:
    """Manages user profile data and avatar lifecycle.

    Args:
        db:           SQLAlchemy ``Session`` (used for flush/refresh).
        user_repo:    Repository for ``User`` lookups and commits.
        storage:      Object-storage client (``S3StorageClient`` in production;
                      any object satisfying ``_StorageProtocol`` in tests).
        settings:     Application settings (provides ``USER_AVATAR_MAX_BYTES``
                      and ``AVATAR_RETENTION_DAYS``).
        avatar_folder: S3 key prefix for avatar objects (default: ``"avatars"``).
    """

    def __init__(
        self,
        db: Session,
        user_repo: UserRepository,
        storage: _StorageProtocol,
        settings: Settings,
        avatar_folder: str = "avatars",
    ) -> None:
        self._db = db
        self._user_repo = user_repo
        self._storage = storage
        self._settings = settings
        self._avatar_folder = avatar_folder

    # ── Public API ─────────────────────────────────────────────────────────

    def get_profile(self, user_id: UUID) -> User:
        """Return the User record for ``user_id``.

        Args:
            user_id: Authenticated user's UUID.

        Returns:
            The ``User`` ORM instance.

        Raises:
            NotFoundException: If the user does not exist.
        """
        return self._user_repo.get_by_id(user_id)

    def update_profile(
        self,
        user_id: UUID,
        *,
        display_name: str | None = None,
        phone: str | ... = ...,  # type: ignore[assignment]
    ) -> User:
        """Update the user's display name and/or phone number.

        Uses sentinel ``...`` for ``phone`` to distinguish "not provided"
        from an explicit ``None`` (which clears the field).

        Args:
            user_id:      Authenticated user's UUID.
            display_name: New display name (skipped if ``None``).
            phone:        New phone number, or ``None`` to clear, or ``...``
                          to leave unchanged.

        Returns:
            The updated ``User`` ORM instance.

        Raises:
            NotFoundException: If the user does not exist.
        """
        user = self._user_repo.get_by_id(user_id)
        before: dict = {
            "display_name": user.display_name,
            "phone": user.phone,
        }

        if display_name is not None:
            user.display_name = display_name

        if phone is not ...:
            user.phone = phone  # type: ignore[assignment]

        self._db.commit()
        self._db.refresh(user)

        logger.info(
            "Profile updated",
            extra={
                "user_id": str(user_id),
                "before": before,
                "after": {"display_name": user.display_name, "phone": user.phone},
            },
        )
        return user

    def upload_avatar(
        self,
        user_id: UUID,
        file_bytes: bytes,
        filename: str,
    ) -> str:
        """Validate, upload, and record a new avatar for ``user_id``.

        Validation order:
        1. File size ≤ ``USER_AVATAR_MAX_BYTES``
        2. MIME type in ``_AVATAR_ALLOWED_MIMES`` (detected from magic bytes)

        The previous avatar URL is stored in ``avatar_previous_url`` for
        retention; the S3 file is NOT deleted immediately (background cleanup
        handles removal after ``AVATAR_RETENTION_DAYS`` days).

        Args:
            user_id:    Authenticated user's UUID.
            file_bytes: Raw file content read into memory.
            filename:   Original filename (used for logging only).

        Returns:
            The public URL of the newly uploaded avatar.

        Raises:
            NotFoundException:        If the user does not exist.
            AvatarTooLargeError:      If the file exceeds the size limit.
            AvatarInvalidFormatError: If the MIME type is not allowed.
        """
        max_bytes: int = self._settings.USER_AVATAR_MAX_BYTES

        if len(file_bytes) > max_bytes:
            raise AvatarTooLargeError(
                details={"max_bytes": max_bytes, "received_bytes": len(file_bytes)}
            )

        detected_mime = _detect_avatar_mime(file_bytes)
        if detected_mime is None or detected_mime not in _AVATAR_ALLOWED_MIMES:
            raise AvatarInvalidFormatError(
                details={
                    "filename": filename,
                    "detected_mime": detected_mime,
                    "allowed_types": sorted(_AVATAR_ALLOWED_MIMES),
                }
            )

        user = self._user_repo.get_by_id(user_id)

        # Upload to storage
        ext = _mime_to_ext(detected_mime)
        key = f"{self._avatar_folder}/{user_id}/{uuid4()}{ext}"
        file_obj = BytesIO(file_bytes)
        new_url = self._storage.upload(file_obj, key)

        # Store previous URL for retention; update current
        if user.avatar_url:
            logger.info(
                "Previous avatar queued for retention",
                extra={
                    "user_id": str(user_id),
                    "previous_url": user.avatar_url,
                    "retention_days": self._settings.AVATAR_RETENTION_DAYS,
                },
            )
        user.avatar_previous_url = user.avatar_url
        user.avatar_url = new_url

        self._db.commit()
        self._db.refresh(user)

        logger.info(
            "Avatar uploaded",
            extra={"user_id": str(user_id), "avatar_url": new_url},
        )
        return new_url

    def delete_avatar(self, user_id: UUID) -> None:
        """Remove the current avatar URL from the user record.

        The S3 file is NOT deleted; it is retained for ``AVATAR_RETENTION_DAYS``
        days for potential rollback or audit purposes.

        Args:
            user_id: Authenticated user's UUID.

        Raises:
            NotFoundException: If the user does not exist.
        """
        user = self._user_repo.get_by_id(user_id)
        previous_url = user.avatar_url

        user.avatar_previous_url = previous_url
        user.avatar_url = None

        self._db.commit()

        logger.info(
            "Avatar removed",
            extra={
                "user_id": str(user_id),
                "previous_url": previous_url,
                "retention_days": self._settings.AVATAR_RETENTION_DAYS,
            },
        )

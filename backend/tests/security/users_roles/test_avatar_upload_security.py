"""T137 [P] — Avatar upload security tests.

Verifies that the avatar upload endpoint (POST /api/v1/profile/avatar)
correctly enforces format validation via magic-byte inspection:

- Accepts a file whose extension does not match its content type, if the
  magic bytes identify a valid format (extension is irrelevant).
- Rejects a file whose magic bytes do not match any supported format, even if
  the extension is valid (e.g., .png extension but PDF magic bytes).
- Rejects an oversized file before performing any format check.
- Rejects a non-image file (e.g., PDF, ZIP) detected via magic bytes.

A ``_FakeStorage`` dependency override is used for happy-path tests to avoid
triggering the ``_NullStorageClient`` ``NotImplementedError``.

Spec ref: spec.md FR-010, FR-011, FR-012, tasks T137.
"""

from __future__ import annotations

import uuid

import fastapi
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

# ---------------------------------------------------------------------------
# Magic byte constants
# ---------------------------------------------------------------------------

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
_JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 100
_WEBP_MAGIC = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
_PDF_MAGIC = b"%PDF-1.4\n%%EOF" + b"\x00" * 100
_ZIP_MAGIC = b"PK\x03\x04" + b"\x00" * 100
_CORRUPTED_BYTES = b"\x00\x01\x02\x03\x04\x05\x06\x07" + b"\xff" * 100


# ---------------------------------------------------------------------------
# Fake storage backend (avoids NotImplementedError from _NullStorageClient)
# ---------------------------------------------------------------------------


class _FakeStorage:
    """Returns a deterministic CDN URL without touching any real storage."""

    def upload(self, file: object, key: str) -> str:
        return f"https://cdn.example.com/{key}"

    def get_url(self, key: str) -> str:
        return f"https://cdn.example.com/{key}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _upload_avatar(
    client: TestClient,
    token: str,
    content: bytes,
    filename: str,
    content_type: str = "application/octet-stream",
):
    """POST /api/v1/profile/avatar with the given file content."""
    return client.post(
        "/api/v1/profile/avatar",
        files={"file": (filename, content, content_type)},
        headers=_auth(token),
    )


def _make_profile_service_override():
    """Return a FastAPI dependency factory that injects _FakeStorage."""
    from core.config.settings import get_settings
    from core.database.session import get_db
    from modules.auth.repositories.user_repository import UserRepository
    from modules.users_roles.services.profile_service import ProfileService

    def _svc(
        db=fastapi.Depends(get_db),
        settings=fastapi.Depends(get_settings),
    ) -> ProfileService:
        return ProfileService(
            db=db,
            user_repo=UserRepository(db),
            storage=_FakeStorage(),
            settings=settings,
        )

    return _svc


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def authenticated_user(test_client: TestClient, db_session: Session):
    """Return a logged-in user token for avatar upload tests."""
    prefix = uuid.uuid4().hex[:8]
    user, pwd = create_test_user(db_session, email=f"avatar_sec_{prefix}@example.com")
    return _login(test_client, user.email, pwd)


# ---------------------------------------------------------------------------
# Tests: magic-byte-based format validation
# ---------------------------------------------------------------------------


class TestAvatarFileWithWrongExtensionButValidMagicBytes:
    """Files with valid magic bytes are accepted regardless of extension."""

    def test_png_magic_with_txt_extension_is_accepted(
        self, test_client: TestClient, authenticated_user: str
    ) -> None:
        """PNG magic bytes in a .txt file → accepted (200)."""
        from modules.users_roles.dependencies import get_profile_service

        app = test_client.app
        app.dependency_overrides[get_profile_service] = _make_profile_service_override()
        try:
            resp = _upload_avatar(
                test_client,
                authenticated_user,
                _PNG_MAGIC,
                "document.txt",
                "text/plain",
            )
            assert resp.status_code == 200, (
                f"PNG magic in .txt should be accepted; got {resp.status_code}: {resp.json()}"
            )
        finally:
            app.dependency_overrides.pop(get_profile_service, None)

    def test_jpeg_magic_with_exe_extension_is_accepted(
        self, test_client: TestClient, authenticated_user: str
    ) -> None:
        """JPEG magic bytes in a .exe file → accepted (200)."""
        from modules.users_roles.dependencies import get_profile_service

        app = test_client.app
        app.dependency_overrides[get_profile_service] = _make_profile_service_override()
        try:
            resp = _upload_avatar(
                test_client,
                authenticated_user,
                _JPEG_MAGIC,
                "photo.exe",
                "application/octet-stream",
            )
            assert resp.status_code == 200, (
                f"JPEG magic in .exe should be accepted; got {resp.status_code}: {resp.json()}"
            )
        finally:
            app.dependency_overrides.pop(get_profile_service, None)

    def test_webp_magic_with_bin_extension_is_accepted(
        self, test_client: TestClient, authenticated_user: str
    ) -> None:
        """WebP magic bytes in a .bin file → accepted (200)."""
        from modules.users_roles.dependencies import get_profile_service

        app = test_client.app
        app.dependency_overrides[get_profile_service] = _make_profile_service_override()
        try:
            resp = _upload_avatar(
                test_client,
                authenticated_user,
                _WEBP_MAGIC,
                "data.bin",
                "application/octet-stream",
            )
            assert resp.status_code == 200, (
                f"WebP magic in .bin should be accepted; got {resp.status_code}: {resp.json()}"
            )
        finally:
            app.dependency_overrides.pop(get_profile_service, None)


class TestAvatarFileWithRightExtensionButWrongMagicBytes:
    """Files with invalid magic bytes are rejected even with correct extension."""

    def test_pdf_magic_with_png_extension_returns_400(
        self, test_client: TestClient, authenticated_user: str
    ) -> None:
        """PDF magic bytes in a .png file → rejected (400)."""
        resp = _upload_avatar(
            test_client,
            authenticated_user,
            _PDF_MAGIC,
            "image.png",
            "image/png",
        )
        assert resp.status_code == 400

    def test_zip_magic_with_jpg_extension_returns_400(
        self, test_client: TestClient, authenticated_user: str
    ) -> None:
        """ZIP magic bytes in a .jpg file → rejected (400)."""
        resp = _upload_avatar(
            test_client,
            authenticated_user,
            _ZIP_MAGIC,
            "photo.jpg",
            "image/jpeg",
        )
        assert resp.status_code == 400

    def test_corrupted_bytes_with_png_extension_returns_400(
        self, test_client: TestClient, authenticated_user: str
    ) -> None:
        """Corrupted/random bytes in a .png file → rejected (400)."""
        resp = _upload_avatar(
            test_client,
            authenticated_user,
            _CORRUPTED_BYTES,
            "corrupt.png",
            "image/png",
        )
        assert resp.status_code == 400


class TestAvatarOversizedFileRejected:
    """Files exceeding the configured size limit are rejected before format check."""

    def test_oversized_file_returns_400(
        self, test_client: TestClient, authenticated_user: str
    ) -> None:
        """File exceeding USER_AVATAR_MAX_BYTES is rejected with 400."""
        from core.config.settings import get_settings

        settings = get_settings()
        oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * (
            settings.USER_AVATAR_MAX_BYTES + 1
        )
        resp = _upload_avatar(
            test_client,
            authenticated_user,
            oversized,
            "giant.png",
            "image/png",
        )
        assert resp.status_code == 400

    def test_file_at_size_limit_with_invalid_magic_returns_400(
        self, test_client: TestClient, authenticated_user: str
    ) -> None:
        """File exactly at the limit with bad magic bytes is rejected (400)."""
        from core.config.settings import get_settings

        settings = get_settings()
        # Size check passes; magic-byte check fails
        at_limit = _CORRUPTED_BYTES[:8] + b"\x00" * (settings.USER_AVATAR_MAX_BYTES - 8)
        resp = _upload_avatar(
            test_client,
            authenticated_user,
            at_limit,
            "exact.png",
            "image/png",
        )
        assert resp.status_code == 400


class TestNonImageFileRejected:
    """Non-image files must be rejected regardless of extension."""

    def test_pdf_file_returns_400(
        self, test_client: TestClient, authenticated_user: str
    ) -> None:
        """PDF file (PDF magic bytes, .pdf extension) → rejected (400)."""
        resp = _upload_avatar(
            test_client,
            authenticated_user,
            _PDF_MAGIC,
            "document.pdf",
            "application/pdf",
        )
        assert resp.status_code == 400

    def test_zip_file_returns_400(
        self, test_client: TestClient, authenticated_user: str
    ) -> None:
        """ZIP file (ZIP magic bytes, .zip extension) → rejected (400)."""
        resp = _upload_avatar(
            test_client,
            authenticated_user,
            _ZIP_MAGIC,
            "archive.zip",
            "application/zip",
        )
        assert resp.status_code == 400

    def test_missing_file_field_returns_422(
        self, test_client: TestClient, authenticated_user: str
    ) -> None:
        """POST /profile/avatar without a file field returns 422."""
        resp = test_client.post(
            "/api/v1/profile/avatar",
            headers=_auth(authenticated_user),
        )
        assert resp.status_code == 422

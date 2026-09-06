"""T114 [P] — Logo upload security tests.

Verifies that the logo upload endpoint (POST /{company_id}/logo) correctly:
  - Rejects SVG files containing <script> tags (XSS vector) with 400.
  - Rejects files with invalid/corrupted magic bytes with 400.
  - Rejects PDF magic bytes disguised as .jpg with 400.
  - Accepts a PNG file renamed to .exe (magic-byte detection ignores extension).
  - Accepts a valid PNG (with mocked storage to avoid NotImplementedError).
  - Rejects multipart requests missing the file field with 422.
  - Uses a UUID-based storage key (original filename not used), preventing
    path traversal via filename.

Note: The default get_company_logo_service dependency uses _NullStorageClient,
which raises NotImplementedError on upload().  Tests that exercise the full
upload path override this dependency with a fake storage backend.

Spec ref: spec.md §6.3 Logo Upload, BR-027.
"""

from __future__ import annotations

import uuid as _uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

# ---------------------------------------------------------------------------
# Magic byte constants
# ---------------------------------------------------------------------------

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
_SVG_WITH_SCRIPT = b"<svg><script>alert('xss')</script></svg>"
_SVG_CLEAN = (
    b"<svg xmlns='http://www.w3.org/2000/svg'><rect width='10' height='10'/></svg>"
)
_CORRUPTED_JPEG = b"\x00\x00\x00\x00\xff\xff\xff\xff" + b"\x00" * 50
_PDF_BYTES = b"%PDF-1.4\n%%EOF" + b"\x00" * 50


# ---------------------------------------------------------------------------
# Fake storage for happy-path tests
# ---------------------------------------------------------------------------


class _FakeStorage:
    """Returns a deterministic fake URL without touching S3."""

    def upload(self, file, key: str) -> str:
        return f"https://cdn.example.com/{key}"

    def delete(self, key: str) -> None:
        pass

    def get_url(self, key: str) -> str:
        return f"https://cdn.example.com/{key}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def owner_and_company(test_client: TestClient, db_session: Session):
    """Return (token, company_id) for a fresh owner + company."""
    prefix = _uuid.uuid4().hex[:8]
    user, pwd = create_test_user(db_session, email=f"logo_sec_{prefix}@example.com")
    token = _login(test_client, user.email, pwd)

    resp = test_client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Logo Sec Corp {prefix}",
            "email": f"logo_{prefix}@example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return token, resp.json()["data"]["id"]


@pytest.fixture()
def logo_url(test_client: TestClient, owner_and_company: tuple):
    """Resolve the POST /{company_id}/logo URL."""
    _, company_id = owner_and_company
    return f"/api/v1/companies/{company_id}/logo"


def _upload(client, logo_url, token, content, filename, content_type="image/png"):
    return client.post(
        logo_url,
        files={"logo_file": (filename, content, content_type)},
        headers=_auth(token),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLogoUploadSecurity:
    """Security-focused logo upload validation tests."""

    def test_svg_with_script_tag_returns_400(
        self,
        test_client: TestClient,
        owner_and_company: tuple,
        logo_url: str,
    ) -> None:
        """SVG containing <script> is rejected to prevent stored XSS."""
        token, _ = owner_and_company
        resp = _upload(
            test_client, logo_url, token, _SVG_WITH_SCRIPT, "logo.svg", "image/svg+xml"
        )
        assert resp.status_code == 400
        body = resp.json()
        code = body.get("error", {}).get("code") or body.get("code")
        assert code in (
            "LOGO_INVALID_CONTENT",
            "LOGO_INVALID_FORMAT",
        ), f"Expected LOGO_INVALID_CONTENT or LOGO_INVALID_FORMAT, got: {body}"

    def test_svg_with_javascript_event_handler_returns_400(
        self,
        test_client: TestClient,
        owner_and_company: tuple,
        logo_url: str,
    ) -> None:
        """SVG with JavaScript event handler attributes is rejected."""
        token, _ = owner_and_company
        svg_with_handler = b"<svg><rect onclick=\"alert('xss')\"/></svg>"
        resp = _upload(
            test_client,
            logo_url,
            token,
            svg_with_handler,
            "handler.svg",
            "image/svg+xml",
        )
        assert resp.status_code == 400

    def test_corrupted_file_magic_bytes_returns_400(
        self,
        test_client: TestClient,
        owner_and_company: tuple,
        logo_url: str,
    ) -> None:
        """File with no recognisable magic bytes is rejected."""
        token, _ = owner_and_company
        resp = _upload(
            test_client, logo_url, token, _CORRUPTED_JPEG, "corrupted.jpg", "image/jpeg"
        )
        assert resp.status_code == 400

    def test_pdf_disguised_as_jpg_returns_400(
        self,
        test_client: TestClient,
        owner_and_company: tuple,
        logo_url: str,
    ) -> None:
        """PDF magic bytes with .jpg extension are rejected via MIME detection."""
        token, _ = owner_and_company
        resp = _upload(
            test_client, logo_url, token, _PDF_BYTES, "invoice.jpg", "image/jpeg"
        )
        assert resp.status_code == 400

    def test_missing_file_field_returns_422(
        self,
        test_client: TestClient,
        owner_and_company: tuple,
        logo_url: str,
    ) -> None:
        """Multipart request without logo_file field returns 422."""
        token, _ = owner_and_company
        resp = test_client.post(logo_url, headers=_auth(token))
        assert resp.status_code == 422

    def test_png_with_exe_extension_is_accepted(
        self,
        test_client: TestClient,
        owner_and_company: tuple,
        logo_url: str,
    ) -> None:
        """PNG magic bytes detected correctly regardless of .exe extension."""
        from modules.companies.dependencies import get_company_logo_service
        from modules.companies.services.company_logo_service import CompanyLogoService

        token, _ = owner_and_company

        def _mock_service():
            return CompanyLogoService(storage=_FakeStorage(), max_bytes=2 * 1024 * 1024)

        app = test_client.app
        app.dependency_overrides[get_company_logo_service] = _mock_service
        try:
            resp = _upload(
                test_client,
                logo_url,
                token,
                _PNG_BYTES,
                "malware.exe",
                "application/octet-stream",
            )
            assert resp.status_code == 200, (
                f"PNG renamed to .exe should be accepted; got {resp.status_code}: {resp.json()}"
            )
        finally:
            app.dependency_overrides.clear()

    def test_valid_png_upload_succeeds(
        self,
        test_client: TestClient,
        owner_and_company: tuple,
        logo_url: str,
    ) -> None:
        """Valid PNG upload returns 200 with a logo_url."""
        from modules.companies.dependencies import get_company_logo_service
        from modules.companies.services.company_logo_service import CompanyLogoService

        token, _ = owner_and_company

        def _mock_service():
            return CompanyLogoService(storage=_FakeStorage(), max_bytes=2 * 1024 * 1024)

        app = test_client.app
        app.dependency_overrides[get_company_logo_service] = _mock_service
        try:
            resp = _upload(
                test_client, logo_url, token, _PNG_BYTES, "logo.png", "image/png"
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert "logo_url" in data
            assert data["logo_url"].startswith("https://cdn.example.com/logos/")
        finally:
            app.dependency_overrides.clear()

    def test_path_traversal_filename_uses_uuid_key(
        self,
        test_client: TestClient,
        owner_and_company: tuple,
        logo_url: str,
    ) -> None:
        """Path traversal in filename does not affect the stored key (UUID-based)."""
        from modules.companies.dependencies import get_company_logo_service
        from modules.companies.services.company_logo_service import CompanyLogoService

        token, company_id = owner_and_company
        uploaded_keys: list[str] = []

        class _CapturingStorage:
            def upload(self, file, key: str) -> str:
                uploaded_keys.append(key)
                return f"https://cdn.example.com/{key}"

            def delete(self, key: str) -> None:
                pass

            def get_url(self, key: str) -> str:
                return ""

        def _mock_service():
            return CompanyLogoService(
                storage=_CapturingStorage(), max_bytes=2 * 1024 * 1024
            )

        app = test_client.app
        app.dependency_overrides[get_company_logo_service] = _mock_service
        try:
            resp = _upload(
                test_client,
                logo_url,
                token,
                _PNG_BYTES,
                "../../etc/passwd.png",
                "image/png",
            )
            assert resp.status_code == 200
            assert len(uploaded_keys) == 1
            key = uploaded_keys[0]
            # Key must start with logos/{company_id}/ and contain a UUID, not the filename
            assert key.startswith(f"logos/{company_id}/")
            assert "passwd" not in key
            assert ".." not in key
        finally:
            app.dependency_overrides.clear()

"""T056 [P] [US2] — Integration tests for POST /api/v1/companies/{id}/logo.

Spec ref: spec.md §4 US2, AC-007.
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

# Magic bytes for test file payloads
_PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
_JPEG_HEADER = b"\xff\xd8\xff" + b"\x00" * 100
_INVALID_BYTES = b"NOT_AN_IMAGE_FILE" + b"\x00" * 100
_LARGE_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * (6 * 1024 * 1024)  # 6 MB > 5 MB limit


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_company(client: TestClient, token: str, name: str, email: str) -> str:
    resp = client.post(
        "/api/v1/companies",
        json={"legal_name": name, "email": email},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()["data"]["id"]


class TestLogoUploadValidation:
    def test_oversized_file_returns_400_logo_too_large(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="logo_large@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Logo Large Corp", "ll@corp.com"
        )

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/logo",
            files={"logo_file": ("big.png", BytesIO(_LARGE_BYTES), "image/png")},
            headers=_auth(token),
        )

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "LOGO_TOO_LARGE"

    def test_invalid_format_returns_400_logo_invalid_format(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="logo_invalid@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Logo Invalid Corp", "li@corp.com"
        )

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/logo",
            files={
                "logo_file": ("doc.pdf", BytesIO(_INVALID_BYTES), "application/pdf")
            },
            headers=_auth(token),
        )

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "LOGO_INVALID_FORMAT"

    def test_svg_with_script_returns_400_logo_invalid_content(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="logo_svg@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Logo SVG Corp", "lsvg@corp.com"
        )

        xss_svg = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/logo",
            files={"logo_file": ("evil.svg", BytesIO(xss_svg), "image/svg+xml")},
            headers=_auth(token),
        )

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "LOGO_INVALID_CONTENT"

    def test_unauthenticated_returns_401(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="logo_noauth@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Logo Noauth Corp", "lna@corp.com"
        )

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/logo",
            files={"logo_file": ("logo.png", BytesIO(_PNG_HEADER), "image/png")},
        )

        assert resp.status_code == 401


class TestLogoUploadSuccess:
    def test_valid_png_upload_succeeds_and_returns_url(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="logo_ok@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(test_client, token, "Logo OK Corp", "lok@corp.com")

        with patch(
            "modules.companies.dependencies._NullStorageClient.upload",
            return_value="https://cdn.example.com/logos/logo.png",
        ):
            resp = test_client.post(
                f"/api/v1/companies/{company_id}/logo",
                files={"logo_file": ("logo.png", BytesIO(_PNG_HEADER), "image/png")},
                headers=_auth(token),
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "logo_url" in data
        assert data["company_id"] == company_id

"""T052 [P] [US2] — Integration tests for PATCH /api/v1/companies/{id}.

Spec ref: spec.md §4 US2, AC-003.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user


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


class TestUpdateCompanyValid:
    def test_partial_update_only_changes_provided_fields(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="update_valid@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(test_client, token, "Update Corp", "up@corp.com")

        resp = test_client.patch(
            f"/api/v1/companies/{company_id}",
            json={"trade_name": "UC Trading"},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["trade_name"] == "UC Trading"
        assert data["legal_name"] == "Update Corp"  # unchanged


class TestUpdateCompanyConflict:
    def test_duplicate_name_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="update_dup@example.com")
        token = _login(test_client, user.email, pwd)
        _create_company(test_client, token, "Existing Corp", "existing@corp.com")
        company_id = _create_company(test_client, token, "Other Corp", "other@corp.com")

        resp = test_client.patch(
            f"/api/v1/companies/{company_id}",
            json={"legal_name": "Existing Corp"},
            headers=_auth(token),
        )

        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "COMPANY_NAME_CONFLICT"


class TestUpdateCompanyImmutability:
    def test_slug_immutable_after_activation_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="update_slug@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(test_client, token, "Slug Corp", "slug@corp.com")

        # Activate first (need country)
        test_client.patch(
            f"/api/v1/companies/{company_id}",
            json={"country": "US"},
            headers=_auth(token),
        )
        test_client.post(
            f"/api/v1/companies/{company_id}/activate", headers=_auth(token)
        )

        # Now try to change slug
        resp = test_client.patch(
            f"/api/v1/companies/{company_id}",
            json={"slug": "new-slug"},
            headers=_auth(token),
        )

        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "SLUG_IMMUTABLE"

    def test_currency_change_without_confirm_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="update_cur@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Currency Corp", "cur@corp.com"
        )

        # First set USD, then attempt to change without confirmation
        test_client.patch(
            f"/api/v1/companies/{company_id}",
            json={"country": "US", "default_currency": "USD"},
            headers=_auth(token),
        )
        test_client.post(
            f"/api/v1/companies/{company_id}/activate", headers=_auth(token)
        )

        resp = test_client.patch(
            f"/api/v1/companies/{company_id}",
            json={"default_currency": "EUR"},
            headers=_auth(token),
        )

        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "CURRENCY_CHANGE_WARNING"

    def test_currency_change_with_confirm_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="update_cur_ok@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Currency OK Corp", "curok@corp.com"
        )

        resp = test_client.patch(
            f"/api/v1/companies/{company_id}",
            json={"default_currency": "EUR", "confirm_currency_change": True},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["default_currency"] == "EUR"

"""T053 [P] [US3] — Integration tests for activate/deactivate endpoints.

Spec ref: spec.md §4 US3, AC-004.
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


def _create_and_prepare(
    client: TestClient, token: str, name: str, email: str, with_country: bool = True
) -> str:
    """Create company; optionally patch country to satisfy activation requirements."""
    resp = client.post(
        "/api/v1/companies",
        json={"legal_name": name, "email": email},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    company_id = resp.json()["data"]["id"]

    if with_country:
        client.patch(
            f"/api/v1/companies/{company_id}",
            json={"country": "US"},
            headers=_auth(token),
        )
    return company_id


class TestActivateCompany:
    def test_activate_pending_setup_company_succeeds(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="status_activate@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_and_prepare(
            test_client, token, "Activate Corp", "act@corp.com"
        )

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/activate",
            headers=_auth(token),
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "active"

    def test_activate_with_missing_country_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="status_incomplete@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_and_prepare(
            test_client, token, "Incomplete Corp", "inc@corp.com", with_country=False
        )

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/activate",
            headers=_auth(token),
        )

        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "COMPANY_INCOMPLETE"


class TestDeactivateCompany:
    def test_deactivate_active_company_succeeds(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="status_deactivate@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_and_prepare(
            test_client, token, "Deactivate Corp", "deact@corp.com"
        )

        test_client.post(
            f"/api/v1/companies/{company_id}/activate", headers=_auth(token)
        )

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/deactivate",
            json={"reason": "Pausing operations."},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "inactive"

    def test_invalid_transition_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="status_invalid@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_and_prepare(
            test_client, token, "Invalid Transition Corp", "inv@corp.com"
        )

        # Cannot deactivate a pending_setup company
        resp = test_client.post(
            f"/api/v1/companies/{company_id}/deactivate",
            json={"reason": "Too early."},
            headers=_auth(token),
        )

        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"

    def test_non_owner_cannot_deactivate_returns_403(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner, owner_pwd = create_test_user(
            db_session, email="status_owner@example.com"
        )
        owner_token = _login(test_client, owner.email, owner_pwd)
        company_id = _create_and_prepare(
            test_client, owner_token, "Owner Only Corp", "owner@corp.com"
        )
        test_client.post(
            f"/api/v1/companies/{company_id}/activate", headers=_auth(owner_token)
        )

        other, other_pwd = create_test_user(
            db_session, email="status_other@example.com"
        )
        other_token = _login(test_client, other.email, other_pwd)

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/deactivate",
            json={"reason": "Unauthorized."},
            headers=_auth(other_token),
        )

        assert resp.status_code == 403


class TestReactivateCompany:
    def test_reactivate_inactive_company_succeeds(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="status_reactivate@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_and_prepare(
            test_client, token, "Reactivate Corp", "react@corp.com"
        )

        test_client.post(
            f"/api/v1/companies/{company_id}/activate", headers=_auth(token)
        )
        test_client.post(
            f"/api/v1/companies/{company_id}/deactivate",
            json={"reason": "Taking a break."},
            headers=_auth(token),
        )
        resp = test_client.post(
            f"/api/v1/companies/{company_id}/activate", headers=_auth(token)
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "active"

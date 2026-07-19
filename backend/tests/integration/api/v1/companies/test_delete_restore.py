"""T054 [P] [US4] — Integration tests for DELETE and restore endpoints.

Spec ref: spec.md §4 US4, AC-005.

Note: TestClient.delete() does not support the `json` keyword argument in
this version of starlette/httpx.  Use `client.request("DELETE", url,
content=json.dumps(...), headers={"Content-Type": "application/json"})`.
"""

from __future__ import annotations

import json as _json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.companies.repositories.company_repository import CompanyRepository
from tests.fixtures.auth_fixtures import create_test_user


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _auth_json(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _delete(client: TestClient, url: str, token: str, body: dict):
    """Send DELETE with a JSON body (TestClient.delete lacks json kwarg)."""
    return client.request(
        "DELETE",
        url,
        content=_json.dumps(body),
        headers=_auth_json(token),
    )


def _create_company(client: TestClient, token: str, name: str, email: str) -> str:
    resp = client.post(
        "/api/v1/companies",
        json={"legal_name": name, "email": email},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()["data"]["id"]


def _activate_company(client: TestClient, token: str, company_id: str) -> None:
    """Set country then activate so the company reaches 'active' status."""
    client.patch(
        f"/api/v1/companies/{company_id}",
        json={"country": "US"},
        headers=_auth(token),
    )
    resp = client.post(f"/api/v1/companies/{company_id}/activate", headers=_auth(token))
    assert resp.status_code == 200


class TestSoftDeleteCompany:
    def test_soft_delete_sets_status_deleted(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="delete_valid@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(test_client, token, "Delete Corp", "del@corp.com")
        _activate_company(test_client, token, company_id)

        resp = _delete(
            test_client,
            f"/api/v1/companies/{company_id}",
            token,
            {"reason": "Closing down.", "confirm_delete": True},
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "deleted"
        assert data["deleted_at"] is not None

    def test_deleted_company_not_returned_by_get(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="delete_get@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Hidden Corp", "hidden@corp.com"
        )
        _activate_company(test_client, token, company_id)

        _delete(
            test_client,
            f"/api/v1/companies/{company_id}",
            token,
            {"reason": "Closing.", "confirm_delete": True},
        )
        resp = test_client.get(f"/api/v1/companies/{company_id}", headers=_auth(token))

        assert resp.status_code == 404

    def test_delete_without_confirm_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="delete_noconf@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Unconfirmed Corp", "unc@corp.com"
        )
        _activate_company(test_client, token, company_id)

        resp = _delete(
            test_client,
            f"/api/v1/companies/{company_id}",
            token,
            {"reason": "Oops.", "confirm_delete": False},
        )

        assert resp.status_code == 422


class TestRestoreCompany:
    def test_restore_within_90_days_returns_inactive(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="restore_valid@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Restore Corp", "rest@corp.com"
        )
        _activate_company(test_client, token, company_id)

        _delete(
            test_client,
            f"/api/v1/companies/{company_id}",
            token,
            {"reason": "Temporary closure.", "confirm_delete": True},
        )
        resp = test_client.post(
            f"/api/v1/companies/{company_id}/restore",
            headers=_auth(token),
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "inactive"

    def test_restore_after_90_days_returns_410(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="restore_purged@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Purged Corp", "purged@corp.com"
        )
        _activate_company(test_client, token, company_id)

        _delete(
            test_client,
            f"/api/v1/companies/{company_id}",
            token,
            {"reason": "Long closure.", "confirm_delete": True},
        )

        # Simulate passage of 91 days by backdating deleted_at in the DB
        repo = CompanyRepository(db_session)
        company = repo.get_by_id(UUID(company_id))
        assert company is not None
        company.deleted_at = datetime.now(UTC) - timedelta(days=91)
        db_session.commit()

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/restore",
            headers=_auth(token),
        )

        assert resp.status_code == 410
        assert resp.json()["error"]["code"] == "COMPANY_PURGED"

    def test_non_owner_cannot_restore_returns_403(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner, owner_pwd = create_test_user(
            db_session, email="restore_owner@example.com"
        )
        owner_token = _login(test_client, owner.email, owner_pwd)
        company_id = _create_company(
            test_client, owner_token, "Restore Owner Corp", "rowner@corp.com"
        )
        _activate_company(test_client, owner_token, company_id)
        _delete(
            test_client,
            f"/api/v1/companies/{company_id}",
            owner_token,
            {"reason": "Temp.", "confirm_delete": True},
        )

        other, other_pwd = create_test_user(
            db_session, email="restore_other@example.com"
        )
        other_token = _login(test_client, other.email, other_pwd)

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/restore",
            headers=_auth(other_token),
        )

        assert resp.status_code == 403

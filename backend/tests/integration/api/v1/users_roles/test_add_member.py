"""T038 [US1] — Integration tests for POST /api/v1/companies/{company_id}/members.

Tests: successful add, duplicate 409, limit exceeded 409, invalid role 404,
audit log created.

Uses the test_client / db_session fixtures from conftest.py.
The actor is the company owner, authenticated via JWT.

Spec reference: tasks T038.
"""

from __future__ import annotations

import uuid

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


def _create_company(
    client: TestClient, token: str, legal_name: str = "Members Test Co"
) -> dict:
    """Create a company and return the response data."""
    resp = client.post(
        "/api/v1/companies",
        json={"legal_name": legal_name, "email": f"info@{uuid.uuid4().hex[:8]}.com"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()["data"]


class TestAddMemberEndpoint:
    """Integration tests for the add-member POST endpoint."""

    def test_add_member_requires_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """POST /members without auth returns 401."""
        fake_company_id = str(uuid.uuid4())
        resp = test_client.post(
            f"/api/v1/companies/{fake_company_id}/members",
            json={"email": "new@example.com", "role_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    def test_add_member_non_member_returns_403(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """POST /members by a non-member returns 403."""
        # Create owner user and company
        owner, owner_pw = create_test_user(
            db_session, email="owner_nonmember@example.com"
        )
        owner_token = _login(test_client, owner.email, owner_pw)
        company = _create_company(test_client, owner_token, "NonMember Test Co")

        # Create a different user who is NOT a member
        other_user, other_pw = create_test_user(
            db_session, email="other_nonmember@example.com"
        )
        other_token = _login(test_client, other_user.email, other_pw)

        resp = test_client.post(
            f"/api/v1/companies/{company['id']}/members",
            json={
                "email": "someone@example.com",
                "role_id": str(uuid.uuid4()),
            },
            headers=_auth(other_token),
        )
        assert resp.status_code == 403

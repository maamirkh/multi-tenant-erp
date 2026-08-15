"""API integration tests for Sales Return endpoints — Phase 7.

Tests:
  - POST /returns              — create return (DRAFT)
  - GET  /returns              — list returns (filters)
  - GET  /returns/{id}         — get return detail
  - POST /returns/{id}/submit  — DRAFT → PENDING_APPROVAL
  - POST /returns/{id}/approve — PENDING_APPROVAL → APPROVED
  - POST /returns/{id}/reject  — PENDING_APPROVAL → REJECTED
  - POST /returns/{id}/cancel  — DRAFT | PENDING_APPROVAL → CANCELLED
  - GET  /returns/{id}/lines   — list return lines
  - 404 on unknown return
  - 409 on invalid transitions
  - RBAC: unauthenticated requests are rejected
  - Tenant isolation: Company B cannot access Company A's returns

Task: T202
Spec ref: specs/007-sales-management/spec.md §19 Sales Returns
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_email() -> str:
    return f"ret-test-{uuid4().hex[:8]}@example.com"


_TEST_PASSWORD = "TestPassword@1234"


def _login(client: TestClient, email: str, password: str = _TEST_PASSWORD) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _return_url(company_id: str, path: str = "") -> str:
    return f"/api/v1/companies/{company_id}/sales/returns{path}"


def _create_company(client: TestClient, token: str):
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Sales Test Co {suffix}",
            "email": f"contact-{suffix}@sales-test.example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _create_return_payload(
    customer_id: str | None = None, reason_code_id: str | None = None
) -> dict:
    return {
        "customer_id": customer_id or str(uuid4()),
        "return_date": "2026-08-04",
        "reason_code_id": reason_code_id or str(uuid4()),
        "resolution_type": "CREDIT_NOTE",
        "lines": [
            {
                "description": "Widget",
                "quantity_returned": "2",
                "unit_price": "25.00",
                "condition": "USED",
            }
        ],
    }


# ---------------------------------------------------------------------------
# Create Return
# ---------------------------------------------------------------------------


class TestCreateReturnAPI:
    def test_create_return_201(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)
        resp = test_client.post(
            _return_url(str(company_id)),
            json=_create_return_payload(),
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["status"] == "DRAFT"
        assert data["return_number"].startswith("SR-")

    def test_create_return_unauthenticated_401(self, test_client: TestClient) -> None:
        company_id = uuid4()
        resp = test_client.post(
            _return_url(str(company_id)),
            json=_create_return_payload(),
        )
        assert resp.status_code == 401

    def test_create_return_includes_lines(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)
        resp = test_client.post(
            _return_url(str(company_id)),
            json=_create_return_payload(),
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert len(data["lines"]) == 1
        assert data["lines"][0]["description"] == "Widget"


# ---------------------------------------------------------------------------
# List Returns
# ---------------------------------------------------------------------------


class TestListReturnsAPI:
    def test_list_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)
        test_client.post(
            _return_url(str(company_id)),
            json=_create_return_payload(),
            headers=_auth(token),
        )
        resp = test_client.get(_return_url(str(company_id)), headers=_auth(token))
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total"] >= 1

    def test_list_filter_status(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)
        test_client.post(
            _return_url(str(company_id)),
            json=_create_return_payload(),
            headers=_auth(token),
        )
        resp = test_client.get(
            _return_url(str(company_id)) + "?status=PENDING_APPROVAL",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0


# ---------------------------------------------------------------------------
# Get Return Detail
# ---------------------------------------------------------------------------


class TestGetReturnAPI:
    def test_get_return_200(self, test_client: TestClient, db_session: Session) -> None:
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)
        create_resp = test_client.post(
            _return_url(str(company_id)),
            json=_create_return_payload(),
            headers=_auth(token),
        )
        return_id = create_resp.json()["data"]["id"]
        resp = test_client.get(
            _return_url(str(company_id), f"/{return_id}"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == return_id

    def test_get_return_404(self, test_client: TestClient, db_session: Session) -> None:
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)
        resp = test_client.get(
            _return_url(str(company_id), f"/{uuid4()}"),
            headers=_auth(token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# State Transitions
# ---------------------------------------------------------------------------


def _create_and_get_id(
    client: TestClient,
    company_id: str,
    token: str,
) -> str:
    resp = client.post(
        _return_url(company_id),
        json=_create_return_payload(),
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()["data"]["id"]


class TestReturnTransitionsAPI:
    def test_submit_return_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)
        ret_id = _create_and_get_id(test_client, str(company_id), token)
        resp = test_client.post(
            _return_url(str(company_id), f"/{ret_id}/submit"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "PENDING_APPROVAL"

    def test_approve_return_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)
        ret_id = _create_and_get_id(test_client, str(company_id), token)
        test_client.post(
            _return_url(str(company_id), f"/{ret_id}/submit"),
            json={},
            headers=_auth(token),
        )
        resp = test_client.post(
            _return_url(str(company_id), f"/{ret_id}/approve"),
            json={"auto_approved": False},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "APPROVED"

    def test_reject_return_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)
        ret_id = _create_and_get_id(test_client, str(company_id), token)
        test_client.post(
            _return_url(str(company_id), f"/{ret_id}/submit"),
            json={},
            headers=_auth(token),
        )
        resp = test_client.post(
            _return_url(str(company_id), f"/{ret_id}/reject"),
            json={"rejection_reason": "Goods were not defective"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "REJECTED"

    def test_cancel_draft_return_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)
        ret_id = _create_and_get_id(test_client, str(company_id), token)
        resp = test_client.post(
            _return_url(str(company_id), f"/{ret_id}/cancel"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "CANCELLED"

    def test_invalid_transition_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)
        ret_id = _create_and_get_id(test_client, str(company_id), token)
        # Try to approve from DRAFT (invalid)
        resp = test_client.post(
            _return_url(str(company_id), f"/{ret_id}/approve"),
            json={"auto_approved": False},
            headers=_auth(token),
        )
        assert resp.status_code == 409

    def test_cancel_after_cancel_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)
        ret_id = _create_and_get_id(test_client, str(company_id), token)
        test_client.post(
            _return_url(str(company_id), f"/{ret_id}/cancel"),
            json={},
            headers=_auth(token),
        )
        resp = test_client.post(
            _return_url(str(company_id), f"/{ret_id}/cancel"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Lines
# ---------------------------------------------------------------------------


class TestReturnLinesAPI:
    def test_list_lines_200(self, test_client: TestClient, db_session: Session) -> None:
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)
        ret_id = _create_and_get_id(test_client, str(company_id), token)
        resp = test_client.get(
            _return_url(str(company_id), f"/{ret_id}/lines"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        lines = resp.json()["data"]
        assert len(lines) == 1
        assert lines[0]["description"] == "Widget"

    def test_lines_for_unknown_return_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = _unique_email()
        create_test_user(db_session, email=email)
        token = _login(test_client, email)
        company_id = _create_company(test_client, token)
        resp = test_client.get(
            _return_url(str(company_id), f"/{uuid4()}/lines"),
            headers=_auth(token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestReturnTenantIsolation:
    def test_company_b_cannot_access_company_a_return(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email_a = _unique_email()
        email_b = _unique_email()
        create_test_user(db_session, email=email_a)
        create_test_user(db_session, email=email_b)

        token_a = _login(test_client, email_a)
        token_b = _login(test_client, email_b)
        # Two distinct real companies, each owned by a different user —
        # required now that company-scoped routes enforce membership (see
        # api/v1/router.py's get_current_company_member gate).
        company_a = _create_company(test_client, token_a)
        company_b = _create_company(test_client, token_b)

        create_resp = test_client.post(
            _return_url(str(company_a)),
            json=_create_return_payload(),
            headers=_auth(token_a),
        )
        assert create_resp.status_code == 201
        return_id = create_resp.json()["data"]["id"]

        # Company B's token accessing company_a's return via company_b URL → 404
        resp = test_client.get(
            _return_url(str(company_b), f"/{return_id}"),
            headers=_auth(token_b),
        )
        assert resp.status_code == 404

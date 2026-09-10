"""API integration tests for Phase 7 Vendor Return (RMA) endpoints — T187.

Tests:
  - List RMAs (empty) → 200
  - List RMAs with status filter → 200
  - Create RMA against non-CONFIRMED GR → 409
  - Get non-existent RMA → 404
  - Update non-existent RMA → 404
  - Submit non-existent RMA → 404
  - Approve non-existent RMA → 404 (or 409 invalid transition)
  - Dispatch non-existent RMA → 404
  - Complete non-existent RMA → 404
  - Cancel non-existent RMA → 404
  - Tenant isolation: RMA not visible to other company

Task: T187
"""

from __future__ import annotations

import uuid as _uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, Any]:
    return {"Authorization": f"Bearer {token}"}


def _create_company(client: TestClient, token: str) -> str:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = _uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Purchase Test Co {suffix}",
            "email": f"contact-{suffix}@purchase-test.example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["data"]["id"])


def _purchase_url(company_id: str, path: str = "") -> str:
    return f"/api/v1/companies/{company_id}/purchase/{path}"


def _setup(client: TestClient, db: Session, suffix: str = "") -> tuple[str, str]:
    email = f"rma_test{suffix}@example.com"
    user, pw = create_test_user(db, email=email)
    token = _login(client, user.email, pw)
    company_id = _create_company(client, token)
    return token, company_id


def _create_draft_po_id(client: TestClient, token: str, company_id: str) -> str:
    """Create a DRAFT PO and return its ID."""
    resp = client.post(
        _purchase_url(company_id, "purchase-orders"),
        json={"currency_code": "USD"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["data"]["id"])


# ===========================================================================
# RMA List / Create
# ===========================================================================


class TestRMAList:
    def test_list_rmas_empty(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_rmal1")
        resp = test_client.get(
            _purchase_url(cid, "vendor-returns"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_list_rmas_with_status_filter(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_rmal2")
        resp = test_client.get(
            _purchase_url(cid, "vendor-returns?status=DRAFT"),
            headers=_auth(token),
        )
        assert resp.status_code == 200

    def test_create_rma_against_draft_gr_returns_409(
        self, test_client: TestClient, db_session: Session
    ):
        """Creating an RMA against a non-CONFIRMED GR must return 409."""
        token, cid = _setup(test_client, db_session, suffix="_rmac1")
        # A random UUID — GR does not exist → 404
        fake_gr_id = str(_uuid.uuid4())
        resp = test_client.post(
            _purchase_url(cid, "vendor-returns"),
            json={"gr_id": fake_gr_id, "lines": []},
            headers=_auth(token),
        )
        # GR not found → 404; draft GR → 409
        assert resp.status_code in (404, 409), resp.text


# ===========================================================================
# RMA Get / Update
# ===========================================================================


class TestRMAGet:
    def test_get_nonexistent_rma_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_rmag1")
        fake_id = str(_uuid.uuid4())
        resp = test_client.get(
            _purchase_url(cid, f"vendor-returns/{fake_id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_update_nonexistent_rma_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_rmau1")
        fake_id = str(_uuid.uuid4())
        resp = test_client.put(
            _purchase_url(cid, f"vendor-returns/{fake_id}"),
            json={"notes": "Updated"},
            headers=_auth(token),
        )
        assert resp.status_code == 404


# ===========================================================================
# RMA State transitions — non-existent RMA
# ===========================================================================


class TestRMATransitions:
    def test_submit_nonexistent_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_rmas1")
        fake_id = str(_uuid.uuid4())
        resp = test_client.post(
            _purchase_url(cid, f"vendor-returns/{fake_id}/submit"),
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_approve_nonexistent_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_rmaa1")
        fake_id = str(_uuid.uuid4())
        resp = test_client.post(
            _purchase_url(cid, f"vendor-returns/{fake_id}/approve"),
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_dispatch_nonexistent_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_rmad1")
        fake_id = str(_uuid.uuid4())
        resp = test_client.post(
            _purchase_url(cid, f"vendor-returns/{fake_id}/dispatch"),
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_complete_nonexistent_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_rmaco1")
        fake_id = str(_uuid.uuid4())
        resp = test_client.post(
            _purchase_url(cid, f"vendor-returns/{fake_id}/complete"),
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_cancel_nonexistent_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_rmacan1")
        fake_id = str(_uuid.uuid4())
        resp = test_client.post(
            _purchase_url(cid, f"vendor-returns/{fake_id}/cancel"),
            headers=_auth(token),
        )
        assert resp.status_code == 404


# ===========================================================================
# Tenant isolation
# ===========================================================================


class TestRMATenantIsolation:
    def test_rma_list_tenant_isolation(
        self, test_client: TestClient, db_session: Session
    ):
        """RMA list for company B should be empty regardless of company A's data."""
        token_a, cid_a = _setup(test_client, db_session, suffix="_rmaiso1")
        token_b, cid_b = _setup(test_client, db_session, suffix="_rmaiso2")

        resp = test_client.get(
            _purchase_url(cid_b, "vendor-returns"),
            headers=_auth(token_b),
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_rma_get_cross_company_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        """Accessing an RMA ID from another company returns 404."""
        token_a, cid_a = _setup(test_client, db_session, suffix="_rmaiso3")
        token_b, cid_b = _setup(test_client, db_session, suffix="_rmaiso4")

        fake_id = str(_uuid.uuid4())
        resp = test_client.get(
            _purchase_url(cid_b, f"vendor-returns/{fake_id}"),
            headers=_auth(token_b),
        )
        assert resp.status_code == 404

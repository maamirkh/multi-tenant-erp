"""API integration tests for Phase 4 Purchase Request endpoints — T117.

Tests:
  - PR CRUD: create, list, get, update, delete
  - PR lifecycle: submit, approve, reject, cancel
  - PR line management: add, update, remove
  - PR convert-to-PO
  - Company isolation
  - Validation errors

Task: T117
"""

from __future__ import annotations

import uuid as _uuid
from decimal import Decimal

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
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _url(company_id: str, path: str = "") -> str:
    return f"/api/v1/companies/{company_id}/purchase/purchase-requests{path}"


def _setup(client: TestClient, db: Session, suffix: str = "") -> tuple[str, str]:
    """Create test user and return (token, company_id_str)."""
    email = f"pr_test{suffix}@example.com"
    user, pw = create_test_user(db, email=email)
    token = _login(client, user.email, pw)
    company_id = str(_uuid.uuid4())
    return token, company_id


def _create_pr(client: TestClient, token: str, company_id: str, **kwargs) -> dict:
    payload = {
        "title": kwargs.get("title", "Test Purchase Request"),
        "currency_code": kwargs.get("currency_code", "USD"),
        "lines": kwargs.get("lines", []),
    }
    resp = client.post(_url(company_id), json=payload, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def _line_payload(
    description: str = "Widget", qty: str = "1", unit_cost: str = "10"
) -> dict:
    return {
        "product_description": description,
        "quantity": qty,
        "estimated_unit_cost": unit_cost,
    }


# ===========================================================================
# PR CRUD
# ===========================================================================


class TestPRCreate:
    def test_create_pr_returns_201(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_cr1")
        resp = test_client.post(
            _url(cid),
            json={"title": "Office Supplies", "currency_code": "USD", "lines": []},
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["title"] == "Office Supplies"
        assert data["status"] == "DRAFT"
        assert data["pr_number"].startswith("PR-")

    def test_create_pr_with_lines(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_cr2")
        lines = [_line_payload("Pen", "10", "1"), _line_payload("Paper", "5", "2")]
        resp = test_client.post(
            _url(cid),
            json={"title": "Stationery", "currency_code": "USD", "lines": lines},
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert len(data["lines"]) == 2
        assert Decimal(data["total_estimated_cost"]) == Decimal("20.00")

    def test_create_pr_requires_auth(
        self, test_client: TestClient, db_session: Session
    ):
        _, cid = _setup(test_client, db_session, suffix="_cr3")
        resp = test_client.post(
            _url(cid),
            json={"title": "No Auth PR", "lines": []},
        )
        assert resp.status_code == 401


class TestPRList:
    def test_list_returns_empty_initially(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_ls1")
        resp = test_client.get(_url(cid), headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_list_returns_created_prs(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_ls2")
        _create_pr(test_client, token, cid, title="PR One")
        _create_pr(test_client, token, cid, title="PR Two")
        resp = test_client.get(_url(cid), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2

    def test_list_filter_by_status(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_ls3")
        _create_pr(test_client, token, cid, title="Draft PR")
        resp = test_client.get(
            _url(cid), params={"status": "DRAFT"}, headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert all(pr["status"] == "DRAFT" for pr in data)

    def test_list_company_isolation(self, test_client: TestClient, db_session: Session):
        token_a, cid_a = _setup(test_client, db_session, suffix="_ls_iso_a")
        token_b, cid_b = _setup(test_client, db_session, suffix="_ls_iso_b")
        _create_pr(test_client, token_a, cid_a, title="Company A PR")
        resp = test_client.get(_url(cid_b), headers=_auth(token_b))
        assert resp.json()["data"] == []


class TestPRGet:
    def test_get_existing_pr(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_gt1")
        pr = _create_pr(test_client, token, cid)
        resp = test_client.get(_url(cid, f"/{pr['id']}"), headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == pr["id"]

    def test_get_nonexistent_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_gt2")
        resp = test_client.get(_url(cid, f"/{_uuid.uuid4()}"), headers=_auth(token))
        assert resp.status_code == 404


class TestPRUpdate:
    def test_update_draft_pr(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_upd1")
        pr = _create_pr(test_client, token, cid)
        resp = test_client.put(
            _url(cid, f"/{pr['id']}"),
            json={"title": "Updated Title"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "Updated Title"


# ===========================================================================
# PR Lines
# ===========================================================================


class TestPRLines:
    def test_add_line_to_draft_pr(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_ln1")
        pr = _create_pr(test_client, token, cid)
        resp = test_client.post(
            _url(cid, f"/{pr['id']}/lines"),
            json=_line_payload("Keyboard", "2", "50"),
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["product_description"] == "Keyboard"
        assert data["line_number"] == 1

    def test_remove_line_from_draft_pr(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_ln2")
        pr = _create_pr(test_client, token, cid, lines=[_line_payload()])
        pr_detail = test_client.get(
            _url(cid, f"/{pr['id']}"), headers=_auth(token)
        ).json()["data"]
        line_id = pr_detail["lines"][0]["id"]
        resp = test_client.delete(
            _url(cid, f"/{pr['id']}/lines/{line_id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 204


# ===========================================================================
# PR Actions
# ===========================================================================


class TestPRSubmit:
    def test_submit_draft_with_lines(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_sub1")
        pr = _create_pr(test_client, token, cid)
        # Add a line first
        test_client.post(
            _url(cid, f"/{pr['id']}/lines"),
            json=_line_payload(),
            headers=_auth(token),
        )
        resp = test_client.post(
            _url(cid, f"/{pr['id']}/submit"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "SUBMITTED"

    def test_submit_no_lines_returns_422(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_sub2")
        pr = _create_pr(test_client, token, cid)
        resp = test_client.post(
            _url(cid, f"/{pr['id']}/submit"),
            headers=_auth(token),
        )
        assert resp.status_code == 422


class TestPRApproveRejectCancel:
    def test_approve_submitted_pr(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_apr1")
        pr = _create_pr(test_client, token, cid)
        test_client.post(
            _url(cid, f"/{pr['id']}/lines"), json=_line_payload(), headers=_auth(token)
        )
        test_client.post(_url(cid, f"/{pr['id']}/submit"), headers=_auth(token))
        resp = test_client.post(
            _url(cid, f"/{pr['id']}/approve"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "APPROVED"

    def test_reject_submitted_pr(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_rej1")
        pr = _create_pr(test_client, token, cid)
        test_client.post(
            _url(cid, f"/{pr['id']}/lines"), json=_line_payload(), headers=_auth(token)
        )
        test_client.post(_url(cid, f"/{pr['id']}/submit"), headers=_auth(token))
        resp = test_client.post(
            _url(cid, f"/{pr['id']}/reject"),
            json={"reason": "Budget exceeded."},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "REJECTED"

    def test_cancel_draft_pr(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_can1")
        pr = _create_pr(test_client, token, cid)
        resp = test_client.post(
            _url(cid, f"/{pr['id']}/cancel"),
            json={"reason": "Not needed."},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "CANCELLED"

    def test_cannot_cancel_approved_pr(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_can2")
        pr = _create_pr(test_client, token, cid)
        test_client.post(
            _url(cid, f"/{pr['id']}/lines"), json=_line_payload(), headers=_auth(token)
        )
        test_client.post(_url(cid, f"/{pr['id']}/submit"), headers=_auth(token))
        test_client.post(_url(cid, f"/{pr['id']}/approve"), headers=_auth(token))
        resp = test_client.post(
            _url(cid, f"/{pr['id']}/cancel"),
            json={"reason": "Changed mind."},
            headers=_auth(token),
        )
        assert resp.status_code == 409


class TestPRConvertToPO:
    def test_convert_approved_pr_to_po(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_po1")
        pr = _create_pr(test_client, token, cid)
        test_client.post(
            _url(cid, f"/{pr['id']}/lines"), json=_line_payload(), headers=_auth(token)
        )
        test_client.post(_url(cid, f"/{pr['id']}/submit"), headers=_auth(token))
        test_client.post(_url(cid, f"/{pr['id']}/approve"), headers=_auth(token))
        resp = test_client.post(
            _url(cid, f"/{pr['id']}/convert-to-po"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["po_number"].startswith("PO-")
        assert data["status"] == "DRAFT"

    def test_convert_non_approved_pr_returns_409(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_po2")
        pr = _create_pr(test_client, token, cid)
        resp = test_client.post(
            _url(cid, f"/{pr['id']}/convert-to-po"),
            headers=_auth(token),
        )
        assert resp.status_code == 409

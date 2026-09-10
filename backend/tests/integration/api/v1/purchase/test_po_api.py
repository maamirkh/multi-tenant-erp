"""API integration tests for Phase 5 Purchase Order endpoints — T145.

Tests:
  - Create PO (201), add lines, submit (200)
  - Approve PO (200)
  - Attempt edit of APPROVED PO → 409
  - Amend PO → re-approval triggered
  - Cancel PO before GR → 200
  - Close PO (200)
  - Company isolation
  - Validation errors (422)
  - PDF export endpoint (200)

Task: T145
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


def _url(company_id: str, path: str = "") -> str:
    return f"/api/v1/companies/{company_id}/purchase/purchase-orders{path}"


def _setup(client: TestClient, db: Session, suffix: str = "") -> tuple[str, str]:
    email = f"po_test{suffix}@example.com"
    user, pw = create_test_user(db, email=email)
    token = _login(client, user.email, pw)
    company_id = _create_company(client, token)
    return token, company_id


def _create_po(
    client: TestClient, token: str, company_id: str, **kwargs
) -> dict[str, Any]:
    payload = {
        "currency_code": kwargs.get("currency_code", "USD"),
        "lines": kwargs.get("lines", []),
    }
    if "supplier_id" in kwargs:
        payload["supplier_id"] = kwargs["supplier_id"]
    if "notes" in kwargs:
        payload["notes"] = kwargs["notes"]
    resp = client.post(_url(company_id), json=payload, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return dict(resp.json()["data"])


def _line_payload(
    description: str = "Widget",
    qty: str = "5",
    unit_cost: str = "10.00",
) -> dict[str, Any]:
    return {
        "product_description": description,
        "quantity_ordered": qty,
        "unit_cost": unit_cost,
    }


# ===========================================================================
# PO CRUD — Create / List / Get / Update / Delete
# ===========================================================================


class TestPOCreate:
    def test_create_po_returns_201(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_poc1")
        resp = test_client.post(
            _url(cid),
            json={"currency_code": "USD"},
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["status"] == "DRAFT"
        assert data["po_number"].startswith("PO-")

    def test_create_po_with_lines(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_poc2")
        po = _create_po(
            test_client,
            token,
            cid,
            lines=[_line_payload("Part A", "3", "25.00")],
        )
        assert po["status"] == "DRAFT"
        assert len(po["lines"]) == 1
        assert po["lines"][0]["product_description"] == "Part A"

    def test_create_po_validates_currency_length(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_poc3")
        resp = test_client.post(
            _url(cid),
            json={"currency_code": "TOOLONG"},
            headers=_auth(token),
        )
        assert resp.status_code == 422


class TestPOList:
    def test_list_returns_pos(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_pol1")
        _create_po(test_client, token, cid)
        _create_po(test_client, token, cid)

        resp = test_client.get(_url(cid), headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 2

    def test_list_tenant_isolation(self, test_client: TestClient, db_session: Session):
        token_a, cid_a = _setup(test_client, db_session, suffix="_poliso1")
        token_b, cid_b = _setup(test_client, db_session, suffix="_poliso2")
        _create_po(test_client, token_a, cid_a)

        resp = test_client.get(_url(cid_b), headers=_auth(token_b))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 0


class TestPOGet:
    def test_get_existing_po(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_pog1")
        po = _create_po(test_client, token, cid)

        resp = test_client.get(_url(cid, f"/{po['id']}"), headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == po["id"]

    def test_get_nonexistent_po_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_pog2")
        fake_id = str(_uuid.uuid4())
        resp = test_client.get(_url(cid, f"/{fake_id}"), headers=_auth(token))
        assert resp.status_code == 404

    def test_get_po_cross_company_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        token_a, cid_a = _setup(test_client, db_session, suffix="_pog3a")
        token_b, cid_b = _setup(test_client, db_session, suffix="_pog3b")
        po = _create_po(test_client, token_a, cid_a)

        resp = test_client.get(_url(cid_b, f"/{po['id']}"), headers=_auth(token_b))
        assert resp.status_code == 404


class TestPOUpdate:
    def test_update_draft_po_succeeds(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_pou1")
        po = _create_po(test_client, token, cid)

        resp = test_client.put(
            _url(cid, f"/{po['id']}"),
            json={"notes": "Updated notes"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["notes"] == "Updated notes"

    def test_update_approved_po_returns_409(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_pou2")
        supplier_id = str(_uuid.uuid4())
        po = _create_po(
            test_client,
            token,
            cid,
            supplier_id=supplier_id,
            lines=[_line_payload()],
        )
        # submit → approve
        test_client.post(_url(cid, f"/{po['id']}/submit"), headers=_auth(token))
        test_client.post(_url(cid, f"/{po['id']}/approve"), headers=_auth(token))

        resp = test_client.put(
            _url(cid, f"/{po['id']}"),
            json={"notes": "Attempted direct edit"},
            headers=_auth(token),
        )
        assert resp.status_code == 409


# ===========================================================================
# PO Lines
# ===========================================================================


class TestPOLines:
    def test_add_line_to_draft_po(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_pol_add1")
        po = _create_po(test_client, token, cid)

        resp = test_client.post(
            _url(cid, f"/{po['id']}/lines"),
            json=_line_payload("Bolt", "100", "0.50"),
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        # add_line returns PurchaseOrderRead — inspect the lines array
        data = resp.json()["data"]
        assert len(data["lines"]) == 1
        assert data["lines"][0]["product_description"] == "Bolt"
        assert data["lines"][0]["line_number"] == 1

    def test_update_line(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_pol_upd1")
        po = _create_po(test_client, token, cid, lines=[_line_payload()])
        line_id = po["lines"][0]["id"]

        resp = test_client.put(
            _url(cid, f"/{po['id']}/lines/{line_id}"),
            json={"unit_cost": "20.00"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        # update_line returns PurchaseOrderRead — inspect the lines array
        lines = resp.json()["data"]["lines"]
        assert len(lines) == 1
        assert float(lines[0]["unit_cost"]) == 20.0

    def test_remove_line(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_pol_del1")
        po = _create_po(test_client, token, cid, lines=[_line_payload()])
        line_id = po["lines"][0]["id"]

        resp = test_client.delete(
            _url(cid, f"/{po['id']}/lines/{line_id}"),
            headers=_auth(token),
        )
        # remove_line returns 200 with PurchaseOrderRead (no lines remaining)
        assert resp.status_code == 200
        assert resp.json()["data"]["lines"] == []


# ===========================================================================
# PO Lifecycle — submit / approve / reject / cancel / close / amend
# ===========================================================================


class TestPOSubmit:
    def test_submit_draft_po_succeeds(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_pos1")
        supplier_id = str(_uuid.uuid4())
        po = _create_po(
            test_client,
            token,
            cid,
            supplier_id=supplier_id,
            lines=[_line_payload()],
        )

        resp = test_client.post(_url(cid, f"/{po['id']}/submit"), headers=_auth(token))
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "PENDING_APPROVAL"

    def test_submit_po_without_supplier_returns_422(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_pos2")
        po = _create_po(
            test_client,
            token,
            cid,
            lines=[_line_payload()],
        )

        resp = test_client.post(_url(cid, f"/{po['id']}/submit"), headers=_auth(token))
        assert resp.status_code == 422

    def test_submit_po_without_lines_returns_422(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_pos3")
        supplier_id = str(_uuid.uuid4())
        po = _create_po(test_client, token, cid, supplier_id=supplier_id)

        resp = test_client.post(_url(cid, f"/{po['id']}/submit"), headers=_auth(token))
        assert resp.status_code == 422


class TestPOApprove:
    def test_approve_pending_po_succeeds(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_poa1")
        supplier_id = str(_uuid.uuid4())
        po = _create_po(
            test_client,
            token,
            cid,
            supplier_id=supplier_id,
            lines=[_line_payload()],
        )
        test_client.post(_url(cid, f"/{po['id']}/submit"), headers=_auth(token))

        resp = test_client.post(_url(cid, f"/{po['id']}/approve"), headers=_auth(token))
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "APPROVED"


class TestPOReject:
    def test_reject_pending_po_returns_rejected(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_por1")
        supplier_id = str(_uuid.uuid4())
        po = _create_po(
            test_client,
            token,
            cid,
            supplier_id=supplier_id,
            lines=[_line_payload()],
        )
        test_client.post(_url(cid, f"/{po['id']}/submit"), headers=_auth(token))

        resp = test_client.post(
            _url(cid, f"/{po['id']}/reject"),
            json={"reason": "Budget exceeded", "rejected_by": str(_uuid.uuid4())},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "REJECTED"

    def test_revert_rejected_po_to_draft(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_por2")
        supplier_id = str(_uuid.uuid4())
        po = _create_po(
            test_client,
            token,
            cid,
            supplier_id=supplier_id,
            lines=[_line_payload()],
        )
        test_client.post(_url(cid, f"/{po['id']}/submit"), headers=_auth(token))
        test_client.post(
            _url(cid, f"/{po['id']}/reject"),
            json={"reason": "Over budget", "rejected_by": str(_uuid.uuid4())},
            headers=_auth(token),
        )

        resp = test_client.post(
            _url(cid, f"/{po['id']}/revert-to-draft"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "DRAFT"


class TestPOCancel:
    def test_cancel_draft_po_before_gr(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_poc_cancel1")
        po = _create_po(test_client, token, cid)

        resp = test_client.post(
            _url(cid, f"/{po['id']}/cancel"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "CANCELLED"

    def test_cancel_approved_po_returns_200(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_poc_cancel2")
        supplier_id = str(_uuid.uuid4())
        po = _create_po(
            test_client,
            token,
            cid,
            supplier_id=supplier_id,
            lines=[_line_payload()],
        )
        test_client.post(_url(cid, f"/{po['id']}/submit"), headers=_auth(token))
        test_client.post(_url(cid, f"/{po['id']}/approve"), headers=_auth(token))

        resp = test_client.post(
            _url(cid, f"/{po['id']}/cancel"),
            json={"cancellation_reason": "Supplier changed"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "CANCELLED"

    def test_cancel_after_gr_returns_422(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_poc_cancel3")
        supplier_id = str(_uuid.uuid4())
        po = _create_po(
            test_client,
            token,
            cid,
            supplier_id=supplier_id,
            lines=[_line_payload()],
        )
        test_client.post(_url(cid, f"/{po['id']}/submit"), headers=_auth(token))
        test_client.post(_url(cid, f"/{po['id']}/approve"), headers=_auth(token))

        # Signal that a confirmed GR exists
        resp = test_client.post(
            _url(cid, f"/{po['id']}/cancel"),
            json={"has_confirmed_gr": True},
            headers=_auth(token),
        )
        assert resp.status_code == 422


class TestPOClose:
    def test_close_approved_po(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_poclse1")
        supplier_id = str(_uuid.uuid4())
        po = _create_po(
            test_client,
            token,
            cid,
            supplier_id=supplier_id,
            lines=[_line_payload()],
        )
        test_client.post(_url(cid, f"/{po['id']}/submit"), headers=_auth(token))
        test_client.post(_url(cid, f"/{po['id']}/approve"), headers=_auth(token))

        resp = test_client.post(
            _url(cid, f"/{po['id']}/close"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "CLOSED"


# ===========================================================================
# PO Amendment
# ===========================================================================


class TestPOAmend:
    def test_amend_approved_po_resets_to_pending_approval(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_poam1")
        supplier_id = str(_uuid.uuid4())
        po = _create_po(
            test_client,
            token,
            cid,
            supplier_id=supplier_id,
            lines=[_line_payload()],
        )
        test_client.post(_url(cid, f"/{po['id']}/submit"), headers=_auth(token))
        test_client.post(_url(cid, f"/{po['id']}/approve"), headers=_auth(token))

        resp = test_client.post(
            _url(cid, f"/{po['id']}/amend"),
            json={"reason": "Price correction", "changes": {}},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "PENDING_APPROVAL"

    def test_amend_draft_po_returns_409(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_poam2")
        po = _create_po(test_client, token, cid)

        resp = test_client.post(
            _url(cid, f"/{po['id']}/amend"),
            json={"reason": "Change", "changes": {}},
            headers=_auth(token),
        )
        assert resp.status_code == 409


# ===========================================================================
# PO PDF Export
# ===========================================================================


class TestPOExport:
    def test_pdf_export_returns_200(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="_poexp1")
        po = _create_po(test_client, token, cid)

        resp = test_client.get(
            _url(cid, f"/{po['id']}/export/pdf"),
            headers=_auth(token),
        )
        # Either JSON stub or actual PDF — both acceptable at Phase 5
        assert resp.status_code == 200


# ===========================================================================
# PO Overdue Endpoint
# ===========================================================================


class TestPOOverdue:
    def test_overdue_endpoint_returns_200(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="_pood1")

        resp = test_client.get(_url(cid, "/overdue"), headers=_auth(token))
        assert resp.status_code == 200
        assert isinstance(resp.json()["data"], list)

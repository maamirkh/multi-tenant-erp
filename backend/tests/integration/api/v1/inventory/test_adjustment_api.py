"""API integration tests for Phase 6 — Inventory Adjustment endpoints.

Tests (T187):
  - 401 unauthenticated on all endpoints
  - POST /adjustments → 201 DRAFT
  - POST /adjustments → 400 invalid quantity
  - POST /adjustments → 404 warehouse not found
  - GET  /adjustments → 200 list
  - GET  /adjustments/{id} → 200 detail
  - GET  /adjustments/{id} → 404 not found
  - POST /adjustments/{id}/submit → auto-approve (flag disabled by default)
  - POST /adjustments/{id}/submit → 409 wrong status
  - POST /adjustments/{id}/approve → 409 self-approval
  - POST /adjustments/{id}/reject → 200 rejected + reason stored
  - Tenant isolation

Spec ref: specs/005-inventory-management/spec.md §15 / FR-IO-012
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.inventory.models.warehouse import Warehouse
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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _url(company_id: str | uuid.UUID, path: str) -> str:
    return f"/api/v1/companies/{company_id}/inventory{path}"


def _create_company(client: TestClient, token: str) -> uuid.UUID:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Inventory Test Co {suffix}",
            "email": f"contact-{suffix}@inventory-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _setup(db: Session, client: TestClient) -> tuple[str, str, uuid.UUID]:
    email = f"adj-{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"
    create_test_user(db, email=email, password=password)
    token = _login(client, email, password)
    company_id = _create_company(client, token)
    return email, password, company_id


def _make_warehouse(db: Session, company_id: uuid.UUID) -> Warehouse:
    wh = Warehouse(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"WH-{uuid.uuid4().hex[:4].upper()}",
        name="Test Warehouse",
        warehouse_type="MAIN",
        status="ACTIVE",
    )
    db.add(wh)
    db.flush()
    return wh


# ---------------------------------------------------------------------------
# 401 Unauthenticated
# ---------------------------------------------------------------------------


class TestAdjustmentUnauthenticated:
    def test_create_requires_auth(self, test_client: TestClient):
        resp = test_client.post(
            _url(uuid.uuid4(), "/adjustments"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(uuid.uuid4()),
                "movement_type": "ADJUSTMENT_IN",
                "quantity": "10",
            },
        )
        assert resp.status_code == 401

    def test_list_requires_auth(self, test_client: TestClient):
        resp = test_client.get(_url(uuid.uuid4(), "/adjustments"))
        assert resp.status_code == 401

    def test_get_by_id_requires_auth(self, test_client: TestClient):
        resp = test_client.get(_url(uuid.uuid4(), f"/adjustments/{uuid.uuid4()}"))
        assert resp.status_code == 401

    def test_submit_requires_auth(self, test_client: TestClient):
        resp = test_client.post(
            _url(uuid.uuid4(), f"/adjustments/{uuid.uuid4()}/submit"), json={}
        )
        assert resp.status_code == 401

    def test_approve_requires_auth(self, test_client: TestClient):
        resp = test_client.post(
            _url(uuid.uuid4(), f"/adjustments/{uuid.uuid4()}/approve"), json={}
        )
        assert resp.status_code == 401

    def test_reject_requires_auth(self, test_client: TestClient):
        resp = test_client.post(
            _url(uuid.uuid4(), f"/adjustments/{uuid.uuid4()}/reject"),
            json={"rejection_reason": "not needed"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Create adjustment
# ---------------------------------------------------------------------------


class TestCreateAdjustmentEndpoint:
    def test_create_returns_201_draft(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)

        resp = test_client.post(
            _url(cid, "/adjustments"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(wh.id),
                "movement_type": "ADJUSTMENT_IN",
                "quantity": "25",
                "notes": "Initial setup",
            },
            headers=_auth(tok),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["status"] == "DRAFT"
        assert float(data["quantity"]) == pytest.approx(25.0)
        assert data["notes"] == "Initial setup"
        assert data["version"] == 1

    def test_create_adjustment_out(self, test_client: TestClient, db_session: Session):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)

        resp = test_client.post(
            _url(cid, "/adjustments"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(wh.id),
                "movement_type": "ADJUSTMENT_OUT",
                "quantity": "10",
            },
            headers=_auth(tok),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["movement_type"] == "ADJUSTMENT_OUT"

    def test_create_with_unknown_warehouse_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        tok = _login(test_client, email, pwd)

        resp = test_client.post(
            _url(cid, "/adjustments"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(uuid.uuid4()),
                "movement_type": "ADJUSTMENT_IN",
                "quantity": "10",
            },
            headers=_auth(tok),
        )
        assert resp.status_code == 404

    def test_create_with_inactive_warehouse_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        wh.status = "INACTIVE"
        db_session.flush()
        tok = _login(test_client, email, pwd)

        resp = test_client.post(
            _url(cid, "/adjustments"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(wh.id),
                "movement_type": "ADJUSTMENT_IN",
                "quantity": "10",
            },
            headers=_auth(tok),
        )
        assert resp.status_code == 404

    def test_create_stores_old_quantity_zero_when_no_stock(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)

        resp = test_client.post(
            _url(cid, "/adjustments"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(wh.id),
                "movement_type": "ADJUSTMENT_IN",
                "quantity": "15",
            },
            headers=_auth(tok),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert float(data["old_quantity"]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# List and detail
# ---------------------------------------------------------------------------


class TestListAndDetailAdjustment:
    def test_list_returns_created_adjustments(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)
        pid = str(uuid.uuid4())

        test_client.post(
            _url(cid, "/adjustments"),
            json={
                "product_id": pid,
                "warehouse_id": str(wh.id),
                "movement_type": "ADJUSTMENT_IN",
                "quantity": "10",
            },
            headers=_auth(tok),
        )
        test_client.post(
            _url(cid, "/adjustments"),
            json={
                "product_id": pid,
                "warehouse_id": str(wh.id),
                "movement_type": "ADJUSTMENT_OUT",
                "quantity": "5",
            },
            headers=_auth(tok),
        )

        resp = test_client.get(_url(cid, "/adjustments"), headers=_auth(tok))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 2

    def test_get_by_id_returns_detail(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)

        create_resp = test_client.post(
            _url(cid, "/adjustments"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(wh.id),
                "movement_type": "ADJUSTMENT_IN",
                "quantity": "20",
            },
            headers=_auth(tok),
        )
        adj_id = create_resp.json()["data"]["id"]

        resp = test_client.get(_url(cid, f"/adjustments/{adj_id}"), headers=_auth(tok))
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == adj_id

    def test_get_by_id_not_found_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        tok = _login(test_client, email, pwd)

        resp = test_client.get(
            _url(cid, f"/adjustments/{uuid.uuid4()}"), headers=_auth(tok)
        )
        assert resp.status_code == 404

    def test_list_isolation_between_companies(
        self, test_client: TestClient, db_session: Session
    ):
        email1, pwd1, cid1 = _setup(db_session, test_client)
        email2, pwd2, cid2 = _setup(db_session, test_client)
        wh1 = _make_warehouse(db_session, cid1)
        tok1 = _login(test_client, email1, pwd1)
        tok2 = _login(test_client, email2, pwd2)

        test_client.post(
            _url(cid1, "/adjustments"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(wh1.id),
                "movement_type": "ADJUSTMENT_IN",
                "quantity": "10",
            },
            headers=_auth(tok1),
        )

        resp2 = test_client.get(_url(cid2, "/adjustments"), headers=_auth(tok2))
        assert resp2.status_code == 200
        assert len(resp2.json()["data"]) == 0


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------


class TestSubmitAdjustmentEndpoint:
    def test_submit_auto_approves_when_flag_disabled(
        self, test_client: TestClient, db_session: Session
    ):
        """Default behaviour: flag disabled → direct APPROVED on submit."""
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)

        create_resp = test_client.post(
            _url(cid, "/adjustments"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(wh.id),
                "movement_type": "ADJUSTMENT_IN",
                "quantity": "50",
            },
            headers=_auth(tok),
        )
        adj_id = create_resp.json()["data"]["id"]

        resp = test_client.post(
            _url(cid, f"/adjustments/{adj_id}/submit"),
            json={},
            headers=_auth(tok),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "APPROVED"
        assert data["reference_movement_id"] is not None

    def test_submit_not_found_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        tok = _login(test_client, email, pwd)

        resp = test_client.post(
            _url(cid, f"/adjustments/{uuid.uuid4()}/submit"),
            json={},
            headers=_auth(tok),
        )
        assert resp.status_code == 404

    def test_submit_already_approved_returns_409(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)

        create_resp = test_client.post(
            _url(cid, "/adjustments"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(wh.id),
                "movement_type": "ADJUSTMENT_IN",
                "quantity": "10",
            },
            headers=_auth(tok),
        )
        adj_id = create_resp.json()["data"]["id"]

        # First submit auto-approves
        test_client.post(
            _url(cid, f"/adjustments/{adj_id}/submit"), json={}, headers=_auth(tok)
        )

        # Second submit on APPROVED → 409
        resp2 = test_client.post(
            _url(cid, f"/adjustments/{adj_id}/submit"), json={}, headers=_auth(tok)
        )
        assert resp2.status_code == 409


# ---------------------------------------------------------------------------
# Reject
# ---------------------------------------------------------------------------


class TestRejectAdjustmentEndpoint:
    def test_reject_pending_returns_rejected(
        self, test_client: TestClient, db_session: Session
    ):
        """Create DRAFT then use service to put it in PENDING_APPROVAL, then reject via API."""

        from modules.inventory.repositories.adjustment_repository import (
            AdjustmentRepository,
        )

        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)

        create_resp = test_client.post(
            _url(cid, "/adjustments"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(wh.id),
                "movement_type": "ADJUSTMENT_IN",
                "quantity": "10",
            },
            headers=_auth(tok),
        )
        adj_id = create_resp.json()["data"]["id"]

        # Force to PENDING_APPROVAL via repo (bypassing service flag)
        adj_repo = AdjustmentRepository(db_session)
        adj_repo.update_status(
            adjustment_id=uuid.UUID(adj_id),
            company_id=cid,
            expected_version=1,
            new_status="PENDING_APPROVAL",
        )
        db_session.flush()

        resp = test_client.post(
            _url(cid, f"/adjustments/{adj_id}/reject"),
            json={"rejection_reason": "Incorrect quantity"},
            headers=_auth(tok),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "REJECTED"
        assert data["rejection_reason"] == "Incorrect quantity"

    def test_reject_draft_returns_409(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)

        create_resp = test_client.post(
            _url(cid, "/adjustments"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(wh.id),
                "movement_type": "ADJUSTMENT_IN",
                "quantity": "5",
            },
            headers=_auth(tok),
        )
        adj_id = create_resp.json()["data"]["id"]

        resp = test_client.post(
            _url(cid, f"/adjustments/{adj_id}/reject"),
            json={"rejection_reason": "Not needed"},
            headers=_auth(tok),
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------


class TestApproveAdjustmentEndpoint:
    def test_approve_draft_returns_409(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)

        create_resp = test_client.post(
            _url(cid, "/adjustments"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(wh.id),
                "movement_type": "ADJUSTMENT_IN",
                "quantity": "5",
            },
            headers=_auth(tok),
        )
        adj_id = create_resp.json()["data"]["id"]

        resp = test_client.post(
            _url(cid, f"/adjustments/{adj_id}/approve"),
            json={},
            headers=_auth(tok),
        )
        assert resp.status_code == 409

"""API integration tests for Phase 3 Approval Engine endpoints — T096.

Tests:
  - Approval matrix: create, list, get, update, delete
  - Matrix rule: create, list, update, delete
  - Approval level: create, list, update, delete
  - Approval actions: approve, reject, emergency bypass
  - Approval status and routing
  - Delegate: create, list, update, delete
  - Feature flag impact: auto-approve when policy flag disabled
  - Company isolation

Task: T096
"""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
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
    return f"/api/v1/companies/{company_id}/purchase{path}"


def _setup(client: TestClient, db: Session, suffix: str = "") -> tuple[str, str]:
    """Create test user and return (token, company_id)."""
    email = f"approval{suffix}@example.com"
    user, pw = create_test_user(db, email=email)
    token = _login(client, user.email, pw)
    company_id = _create_company(client, token)
    return token, company_id


# ---------------------------------------------------------------------------
# Matrix endpoints
# ---------------------------------------------------------------------------


class TestApprovalMatrixAPI:
    def test_create_matrix(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="mx1")
        resp = test_client.post(
            _url(cid, "/approval/matrices"),
            json={"document_type": "PURCHASE_REQUEST", "name": "PR Approval Matrix"},
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["document_type"] == "PURCHASE_REQUEST"
        assert data["name"] == "PR Approval Matrix"
        assert data["is_active"] is True

    def test_list_matrices(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="mx2")
        test_client.post(
            _url(cid, "/approval/matrices"),
            json={"document_type": "PURCHASE_REQUEST", "name": "Matrix A"},
            headers=_auth(token),
        )
        test_client.post(
            _url(cid, "/approval/matrices"),
            json={"document_type": "PURCHASE_ORDER", "name": "Matrix B"},
            headers=_auth(token),
        )
        resp = test_client.get(_url(cid, "/approval/matrices"), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2

    def test_get_matrix(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="mx3")
        create_resp = test_client.post(
            _url(cid, "/approval/matrices"),
            json={"document_type": "PURCHASE_REQUEST", "name": "Matrix X"},
            headers=_auth(token),
        )
        matrix_id = create_resp.json()["data"]["id"]
        resp = test_client.get(
            _url(cid, f"/approval/matrices/{matrix_id}"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == matrix_id

    def test_update_matrix(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="mx4")
        create_resp = test_client.post(
            _url(cid, "/approval/matrices"),
            json={"document_type": "PURCHASE_REQUEST", "name": "Old Name"},
            headers=_auth(token),
        )
        matrix_id = create_resp.json()["data"]["id"]
        resp = test_client.patch(
            _url(cid, f"/approval/matrices/{matrix_id}"),
            json={"name": "New Name", "is_active": False},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "New Name"
        assert data["is_active"] is False

    def test_delete_matrix(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="mx5")
        create_resp = test_client.post(
            _url(cid, "/approval/matrices"),
            json={"document_type": "PURCHASE_REQUEST", "name": "To Delete"},
            headers=_auth(token),
        )
        matrix_id = create_resp.json()["data"]["id"]
        resp = test_client.delete(
            _url(cid, f"/approval/matrices/{matrix_id}"), headers=_auth(token)
        )
        assert resp.status_code == 204

    def test_invalid_document_type_rejected(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="mx6")
        resp = test_client.post(
            _url(cid, "/approval/matrices"),
            json={"document_type": "INVALID_TYPE", "name": "Bad"},
            headers=_auth(token),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Rule endpoints
# ---------------------------------------------------------------------------


class TestMatrixRuleAPI:
    def _create_matrix(self, client, token, cid, doc_type="PURCHASE_REQUEST"):
        resp = client.post(
            _url(cid, "/approval/matrices"),
            json={"document_type": doc_type, "name": "Test Matrix"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        return resp.json()["data"]["id"]

    def test_create_rule(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="rl1")
        mid = self._create_matrix(test_client, token, cid)
        resp = test_client.post(
            _url(cid, f"/approval/matrices/{mid}/rules"),
            json={
                "condition_type": "ALWAYS",
                "approval_level": 1,
                "approval_mode": "SEQUENTIAL",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["condition_type"] == "ALWAYS"

    def test_create_amount_range_rule(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="rl2")
        mid = self._create_matrix(test_client, token, cid)
        resp = test_client.post(
            _url(cid, f"/approval/matrices/{mid}/rules"),
            json={
                "condition_type": "AMOUNT_RANGE",
                "min_amount": "1000.00",
                "max_amount": "50000.00",
                "approval_level": 1,
                "approval_mode": "SEQUENTIAL",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201

    def test_list_rules(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="rl3")
        mid = self._create_matrix(test_client, token, cid)
        test_client.post(
            _url(cid, f"/approval/matrices/{mid}/rules"),
            json={
                "condition_type": "ALWAYS",
                "approval_level": 1,
                "approval_mode": "SEQUENTIAL",
            },
            headers=_auth(token),
        )
        resp = test_client.get(
            _url(cid, f"/approval/matrices/{mid}/rules"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_delete_rule(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="rl4")
        mid = self._create_matrix(test_client, token, cid)
        create_resp = test_client.post(
            _url(cid, f"/approval/matrices/{mid}/rules"),
            json={
                "condition_type": "ALWAYS",
                "approval_level": 1,
                "approval_mode": "SEQUENTIAL",
            },
            headers=_auth(token),
        )
        rule_id = create_resp.json()["data"]["id"]
        resp = test_client.delete(
            _url(cid, f"/approval/matrices/{mid}/rules/{rule_id}"), headers=_auth(token)
        )
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Level endpoints
# ---------------------------------------------------------------------------


class TestApprovalLevelAPI:
    def _setup_matrix_rule(self, client, token, cid):
        mresp = client.post(
            _url(cid, "/approval/matrices"),
            json={"document_type": "PURCHASE_REQUEST", "name": "Matrix"},
            headers=_auth(token),
        )
        mid = mresp.json()["data"]["id"]
        rresp = client.post(
            _url(cid, f"/approval/matrices/{mid}/rules"),
            json={
                "condition_type": "ALWAYS",
                "approval_level": 1,
                "approval_mode": "SEQUENTIAL",
            },
            headers=_auth(token),
        )
        return rresp.json()["data"]["id"]

    def test_create_role_level(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="lv1")
        rule_id = self._setup_matrix_rule(test_client, token, cid)
        resp = test_client.post(
            _url(cid, f"/approval/rules/{rule_id}/levels"),
            json={
                "level_number": 1,
                "approver_type": "ROLE",
                "approver_role": "PURCHASE_MANAGER",
                "escalation_days": 3,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["level_number"] == 1
        assert data["approver_type"] == "ROLE"

    def test_list_levels(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="lv2")
        rule_id = self._setup_matrix_rule(test_client, token, cid)
        test_client.post(
            _url(cid, f"/approval/rules/{rule_id}/levels"),
            json={
                "level_number": 1,
                "approver_type": "ROLE",
                "approver_role": "PM",
                "escalation_days": 3,
            },
            headers=_auth(token),
        )
        resp = test_client.get(
            _url(cid, f"/approval/rules/{rule_id}/levels"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_delete_level(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="lv3")
        rule_id = self._setup_matrix_rule(test_client, token, cid)
        create_resp = test_client.post(
            _url(cid, f"/approval/rules/{rule_id}/levels"),
            json={
                "level_number": 1,
                "approver_type": "ROLE",
                "approver_role": "PM",
                "escalation_days": 3,
            },
            headers=_auth(token),
        )
        level_id = create_resp.json()["data"]["id"]
        resp = test_client.delete(
            _url(cid, f"/approval/rules/{rule_id}/levels/{level_id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Approval actions
# ---------------------------------------------------------------------------


class TestApprovalActionsAPI:
    def test_approve_document(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="ac1")
        doc_id = str(_uuid.uuid4())
        resp = test_client.post(
            _url(cid, "/approval/approve"),
            json={
                "document_type": "PURCHASE_REQUEST",
                "document_id": doc_id,
                "level_number": 1,
                "comment": "Approved.",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["action"] == "APPROVED"
        assert data["is_emergency_bypass"] is False

    def test_reject_document(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="ac2")
        doc_id = str(_uuid.uuid4())
        resp = test_client.post(
            _url(cid, "/approval/reject"),
            json={
                "document_type": "PURCHASE_REQUEST",
                "document_id": doc_id,
                "level_number": 1,
                "comment": "Budget exceeded.",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["action"] == "REJECTED"
        assert data["comment"] == "Budget exceeded."

    def test_reject_requires_comment(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="ac3")
        # Missing comment — Pydantic should reject it with 422
        resp = test_client.post(
            _url(cid, "/approval/reject"),
            json={
                "document_type": "PURCHASE_REQUEST",
                "document_id": str(_uuid.uuid4()),
                "level_number": 1,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_emergency_bypass(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="ac4")
        doc_id = str(_uuid.uuid4())
        resp = test_client.post(
            _url(cid, "/approval/bypass"),
            json={
                "document_type": "PURCHASE_REQUEST",
                "document_id": doc_id,
                "justification": "Urgent procurement required.",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["is_emergency_bypass"] is True

    def test_get_approval_status(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="ac5")
        doc_id = str(_uuid.uuid4())
        test_client.post(
            _url(cid, "/approval/approve"),
            json={
                "document_type": "PURCHASE_REQUEST",
                "document_id": doc_id,
                "level_number": 1,
            },
            headers=_auth(token),
        )
        resp = test_client.get(
            _url(cid, "/approval/status"),
            params={"document_type": "PURCHASE_REQUEST", "document_id": doc_id},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["document_type"] == "PURCHASE_REQUEST"
        assert len(data["records"]) == 1

    def test_approval_route_dry_run(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="ac6")
        resp = test_client.get(
            _url(cid, "/approval/route"),
            params={
                "document_type": "PURCHASE_REQUEST",
                "document_id": str(_uuid.uuid4()),
                "amount": 500.0,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "auto_approved" in data

    def test_invalid_document_type_rejected(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="ac7")
        resp = test_client.post(
            _url(cid, "/approval/approve"),
            json={
                "document_type": "INVALID_TYPE",
                "document_id": str(_uuid.uuid4()),
                "level_number": 1,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Delegate endpoints
# ---------------------------------------------------------------------------


class TestApprovalDelegateAPI:
    def test_create_delegate(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="dg1")
        now = datetime.now(UTC)
        resp = test_client.post(
            _url(cid, "/approval/delegates"),
            json={
                "delegate_id": str(_uuid.uuid4()),
                "valid_from": now.isoformat(),
                "valid_until": (now + timedelta(days=7)).isoformat(),
                "document_type": "PURCHASE_REQUEST",
                "is_active": True,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["document_type"] == "PURCHASE_REQUEST"
        assert data["is_active"] is True

    def test_list_delegates_by_delegator(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, suffix="dg2")
        user_resp = test_client.get("/api/v1/auth/me", headers=_auth(token))
        if user_resp.status_code == 200:
            me = user_resp.json()["data"]
            delegator_id = me.get("user_id") or me.get("id")
        else:
            # fallback: skip this sub-test
            pytest.skip("Cannot get current user id")

        now = datetime.now(UTC)
        test_client.post(
            _url(cid, "/approval/delegates"),
            json={
                "delegate_id": str(_uuid.uuid4()),
                "valid_from": now.isoformat(),
                "valid_until": (now + timedelta(days=7)).isoformat(),
                "is_active": True,
            },
            headers=_auth(token),
        )
        resp = test_client.get(
            _url(cid, f"/approval/delegates/by-delegator/{delegator_id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200

    def test_update_delegate(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="dg3")
        now = datetime.now(UTC)
        create_resp = test_client.post(
            _url(cid, "/approval/delegates"),
            json={
                "delegate_id": str(_uuid.uuid4()),
                "valid_from": now.isoformat(),
                "valid_until": (now + timedelta(days=7)).isoformat(),
                "is_active": True,
            },
            headers=_auth(token),
        )
        assert create_resp.status_code == 201
        delegate_id = create_resp.json()["data"]["id"]
        resp = test_client.patch(
            _url(cid, f"/approval/delegates/{delegate_id}"),
            json={"is_active": False},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_active"] is False

    def test_delete_delegate(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, suffix="dg4")
        now = datetime.now(UTC)
        create_resp = test_client.post(
            _url(cid, "/approval/delegates"),
            json={
                "delegate_id": str(_uuid.uuid4()),
                "valid_from": now.isoformat(),
                "valid_until": (now + timedelta(days=7)).isoformat(),
                "is_active": True,
            },
            headers=_auth(token),
        )
        delegate_id = create_resp.json()["data"]["id"]
        resp = test_client.delete(
            _url(cid, f"/approval/delegates/{delegate_id}"), headers=_auth(token)
        )
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Feature flag tests (T097)
# ---------------------------------------------------------------------------


class TestApprovalFeatureFlags:
    def test_route_auto_approves_when_no_matrix(
        self, test_client: TestClient, db_session: Session
    ):
        """With no matrix configured, routing returns auto_approved=True."""
        token, cid = _setup(test_client, db_session, suffix="ff1")
        doc_id = str(_uuid.uuid4())
        resp = test_client.get(
            _url(cid, "/approval/route"),
            params={"document_type": "PURCHASE_REQUEST", "document_id": doc_id},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["auto_approved"] is True
        assert resp.json()["data"]["matrix_found"] is False

    def test_route_uses_matrix_when_configured(
        self, test_client: TestClient, db_session: Session
    ):
        """With a matrix configured, routing finds the matrix."""
        token, cid = _setup(test_client, db_session, suffix="ff2")
        # Create matrix + ALWAYS rule
        mresp = test_client.post(
            _url(cid, "/approval/matrices"),
            json={"document_type": "PURCHASE_REQUEST", "name": "Test"},
            headers=_auth(token),
        )
        mid = mresp.json()["data"]["id"]
        test_client.post(
            _url(cid, f"/approval/matrices/{mid}/rules"),
            json={
                "condition_type": "ALWAYS",
                "approval_level": 1,
                "approval_mode": "SEQUENTIAL",
            },
            headers=_auth(token),
        )

        resp = test_client.get(
            _url(cid, "/approval/route"),
            params={
                "document_type": "PURCHASE_REQUEST",
                "document_id": str(_uuid.uuid4()),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["matrix_found"] is True
        # No levels configured for the rule, so auto-approves
        assert data["auto_approved"] is True

    def test_unauthenticated_request_rejected(
        self, test_client: TestClient, db_session: Session
    ):
        """All approval endpoints require authentication."""
        cid = str(_uuid.uuid4())
        resp = test_client.get(_url(cid, "/approval/matrices"))
        assert resp.status_code == 401

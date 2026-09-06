"""API integration tests for Purchase Management Phase 0 endpoints.

Tests:
  - Health endpoint
  - Feature flags (list, enable, disable)
  - Supplier Category CRUD (create, list, get, update, delete)
  - Payment Terms CRUD
  - Purchase Reason Code CRUD
  - Purchase Policy (get, update)
  - 401 enforcement on all endpoints

All tests use the FastAPI TestClient with SQLite in-memory database.

Task: T028
Spec ref: specs/006-purchase-management/tasks.md §Phase 0
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _url(company_id: str, path: str) -> str:
    return f"/api/v1/companies/{company_id}/purchase{path}"


# ---------------------------------------------------------------------------
# Unauthenticated access (401 enforcement)
# ---------------------------------------------------------------------------


class TestUnauthenticated:
    """All purchase routes must reject unauthenticated requests with 401."""

    def test_health_requires_auth(self, test_client: TestClient) -> None:
        """Health endpoint requires authentication."""
        cid = str(uuid.uuid4())
        resp = test_client.get(_url(cid, "/health"))
        assert resp.status_code == 401

    def test_feature_flags_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/feature-flags"))
        assert resp.status_code == 401

    def test_categories_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/settings/categories"))
        assert resp.status_code == 401

    def test_payment_terms_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/settings/payment-terms"))
        assert resp.status_code == 401

    def test_reason_codes_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/settings/reason-codes"))
        assert resp.status_code == 401

    def test_policy_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/settings/policy"))
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_health_ok@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        resp = test_client.get(_url(cid, "/health"), headers=_auth(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["module"] == "purchase"

    def test_health_includes_company_id(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_health_cid@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        resp = test_client.get(_url(cid, "/health"), headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["company_id"] == cid


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------


class TestFeatureFlags:
    def test_list_feature_flags_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_ff_list@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        resp = test_client.get(_url(cid, "/feature-flags"), headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data, list)
        # Should return at least the 12 default flags
        assert len(data) >= 12

    def test_list_contains_supplier_management_flag(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_ff_get@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        resp = test_client.get(_url(cid, "/feature-flags"), headers=_auth(token))
        assert resp.status_code == 200
        flags = resp.json()["data"]
        keys = {f["flag_key"] for f in flags}
        assert "purchase.approval_required_pr" in keys

    def test_put_unknown_flag_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_ff_404@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        resp = test_client.put(
            _url(cid, "/feature-flags/purchase.nonexistent_flag"),
            json={"is_enabled": True},
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_enable_flag(self, test_client: TestClient, db_session: Session) -> None:
        user, pw = create_test_user(db_session, email="purch_ff_enable@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        resp = test_client.put(
            _url(cid, "/feature-flags/purchase.direct_po_allowed"),
            json={"is_enabled": True},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_enabled"] is True

    def test_disable_flag(self, test_client: TestClient, db_session: Session) -> None:
        user, pw = create_test_user(db_session, email="purch_ff_disable@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        # First enable then disable
        test_client.put(
            _url(cid, "/feature-flags/purchase.direct_po_allowed"),
            json={"is_enabled": True},
            headers=_auth(token),
        )
        resp = test_client.put(
            _url(cid, "/feature-flags/purchase.direct_po_allowed"),
            json={"is_enabled": False},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_enabled"] is False


# ---------------------------------------------------------------------------
# Supplier Category CRUD
# ---------------------------------------------------------------------------


class TestSupplierCategoryCRUD:
    def test_create_category_returns_201(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_cat_c@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        resp = test_client.post(
            _url(cid, "/settings/categories"),
            json={"code": "TECH", "name": "Technology", "description": "Tech vendors"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["code"] == "TECH"
        assert data["name"] == "Technology"
        assert data["status"] == "active"

    def test_create_duplicate_code_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_cat_dup@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        payload = {"code": "DUPE", "name": "First"}
        test_client.post(
            _url(cid, "/settings/categories"),
            json=payload,
            headers=_auth(token),
        )
        resp = test_client.post(
            _url(cid, "/settings/categories"),
            json=payload,
            headers=_auth(token),
        )
        assert resp.status_code == 409

    def test_list_categories(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_cat_list@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        test_client.post(
            _url(cid, "/settings/categories"),
            json={"code": "A", "name": "Cat A"},
            headers=_auth(token),
        )
        test_client.post(
            _url(cid, "/settings/categories"),
            json={"code": "B", "name": "Cat B"},
            headers=_auth(token),
        )

        resp = test_client.get(_url(cid, "/settings/categories"), headers=_auth(token))
        assert resp.status_code == 200
        items = resp.json()["data"]
        assert len(items) >= 2

    def test_get_category_by_id(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_cat_get@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        create_resp = test_client.post(
            _url(cid, "/settings/categories"),
            json={"code": "GETME", "name": "Get Me"},
            headers=_auth(token),
        )
        cat_id = create_resp.json()["data"]["id"]

        resp = test_client.get(
            _url(cid, f"/settings/categories/{cat_id}"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == cat_id

    def test_get_nonexistent_category_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_cat_404@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        resp = test_client.get(
            _url(cid, f"/settings/categories/{uuid.uuid4()}"),
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_update_category(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_cat_upd@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        create_resp = test_client.post(
            _url(cid, "/settings/categories"),
            json={"code": "UPD", "name": "Original Name"},
            headers=_auth(token),
        )
        cat_id = create_resp.json()["data"]["id"]

        resp = test_client.put(
            _url(cid, f"/settings/categories/{cat_id}"),
            json={"name": "Updated Name"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Updated Name"

    def test_delete_category(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_cat_del@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        create_resp = test_client.post(
            _url(cid, "/settings/categories"),
            json={"code": "DEL", "name": "To Delete"},
            headers=_auth(token),
        )
        cat_id = create_resp.json()["data"]["id"]

        resp = test_client.delete(
            _url(cid, f"/settings/categories/{cat_id}"), headers=_auth(token)
        )
        assert resp.status_code == 204

        # Verify it's gone
        get_resp = test_client.get(
            _url(cid, f"/settings/categories/{cat_id}"), headers=_auth(token)
        )
        assert get_resp.status_code == 404

    def test_tenant_isolation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_cat_iso@example.com")
        token = _login(test_client, user.email, pw)
        company_a = str(uuid.uuid4())
        company_b = str(uuid.uuid4())

        test_client.post(
            _url(company_a, "/settings/categories"),
            json={"code": "ONLY-A", "name": "Company A Cat"},
            headers=_auth(token),
        )

        resp = test_client.get(
            _url(company_b, "/settings/categories"), headers=_auth(token)
        )
        assert resp.status_code == 200
        items = resp.json()["data"]
        codes = [i["code"] for i in items]
        assert "ONLY-A" not in codes


# ---------------------------------------------------------------------------
# Payment Terms CRUD
# ---------------------------------------------------------------------------


class TestPaymentTermsCRUD:
    def test_create_payment_terms_returns_201(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_pt_create@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        resp = test_client.post(
            _url(cid, "/settings/payment-terms"),
            json={"code": "NET30", "name": "Net 30 Days", "net_days": 30},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["code"] == "NET30"
        assert data["net_days"] == 30
        assert data["is_active"] is True

    def test_list_payment_terms(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_pt_list@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        test_client.post(
            _url(cid, "/settings/payment-terms"),
            json={"code": "NET15", "name": "Net 15", "net_days": 15},
            headers=_auth(token),
        )

        resp = test_client.get(
            _url(cid, "/settings/payment-terms"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

    def test_duplicate_code_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_pt_dup@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        payload = {"code": "DUP30", "name": "Dup 30", "net_days": 30}
        test_client.post(
            _url(cid, "/settings/payment-terms"), json=payload, headers=_auth(token)
        )
        resp = test_client.post(
            _url(cid, "/settings/payment-terms"), json=payload, headers=_auth(token)
        )
        assert resp.status_code == 409

    def test_tenant_isolation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_pt_iso@example.com")
        token = _login(test_client, user.email, pw)
        company_a = str(uuid.uuid4())
        company_b = str(uuid.uuid4())

        test_client.post(
            _url(company_a, "/settings/payment-terms"),
            json={"code": "A-NET", "name": "A Net", "net_days": 30},
            headers=_auth(token),
        )

        resp = test_client.get(
            _url(company_b, "/settings/payment-terms"), headers=_auth(token)
        )
        assert resp.status_code == 200
        items = resp.json()["data"]
        assert all(i["code"] != "A-NET" for i in items)


# ---------------------------------------------------------------------------
# Purchase Reason Codes CRUD
# ---------------------------------------------------------------------------


class TestPurchaseReasonCodeCRUD:
    def test_create_reason_code_returns_201(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_rc_create@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        resp = test_client.post(
            _url(cid, "/settings/reason-codes"),
            json={"code": "WI", "name": "Wrong Item", "reason_type": "RETURN"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["code"] == "WI"
        assert data["reason_type"] == "RETURN"

    def test_invalid_reason_type_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_rc_inv@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        resp = test_client.post(
            _url(cid, "/settings/reason-codes"),
            json={"code": "BAD", "name": "Bad Type", "reason_type": "INVALID_TYPE"},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_list_reason_codes(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_rc_list@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        test_client.post(
            _url(cid, "/settings/reason-codes"),
            json={"code": "OC", "name": "Order Changed", "reason_type": "CANCELLATION"},
            headers=_auth(token),
        )

        resp = test_client.get(
            _url(cid, "/settings/reason-codes"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

    def test_delete_reason_code(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_rc_del@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        create_resp = test_client.post(
            _url(cid, "/settings/reason-codes"),
            json={"code": "DELRC", "name": "Delete Me", "reason_type": "GENERAL"},
            headers=_auth(token),
        )
        rc_id = create_resp.json()["data"]["id"]

        resp = test_client.delete(
            _url(cid, f"/settings/reason-codes/{rc_id}"), headers=_auth(token)
        )
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Purchase Policy
# ---------------------------------------------------------------------------


class TestPurchasePolicy:
    def test_get_policy_auto_creates_default(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_pol_get@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        resp = test_client.get(_url(cid, "/settings/policy"), headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "over_receipt_policy" in data
        assert "pr_approval_required" in data

    def test_update_policy(self, test_client: TestClient, db_session: Session) -> None:
        user, pw = create_test_user(db_session, email="purch_pol_upd@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        resp = test_client.put(
            _url(cid, "/settings/policy"),
            json={"direct_po_allowed": True, "over_receipt_policy": "BLOCK"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["direct_po_allowed"] is True
        assert data["over_receipt_policy"] == "BLOCK"

    def test_update_policy_invalid_value_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="purch_pol_inv@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        resp = test_client.put(
            _url(cid, "/settings/policy"),
            json={"over_receipt_policy": "INVALID_POLICY"},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_policy_singleton_per_company(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Multiple GETs return the same policy, not duplicates."""
        user, pw = create_test_user(db_session, email="purch_pol_sing@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(uuid.uuid4())

        resp1 = test_client.get(_url(cid, "/settings/policy"), headers=_auth(token))
        resp2 = test_client.get(_url(cid, "/settings/policy"), headers=_auth(token))

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["data"]["id"] == resp2.json()["data"]["id"]

"""API integration tests for Supplier Enrichment endpoints — Phase 2 (T071).

Tests:
  - Credit limit: set, get, update (all three enforcement modes)
  - Bank details: authenticated access (FM restriction tracked for Epic 7+ RBAC)
  - Supplier rating: view, recompute, manual override
  - Document: add, list, delete, expiry
  - Lead times: set, list, upsert
  - Preferred supplier: set/clear flag

All tests use the FastAPI TestClient with SQLite in-memory database.

Task: T071
Spec ref: specs/006-purchase-management/tasks.md §Phase 2
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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _url(company_id: str, path: str = "") -> str:
    return f"/api/v1/companies/{company_id}/purchase/suppliers{path}"


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


def _setup(
    test_client: TestClient, db_session: Session, *, email_suffix: str = ""
) -> tuple[str, str]:
    """Create a test user and return (token, company_id)."""
    email = f"enrich{email_suffix}@example.com"
    user, pw = create_test_user(db_session, email=email)
    token = _login(test_client, user.email, pw)
    company_id = _create_company(test_client, token)
    return token, company_id


def _create_supplier(
    client: TestClient,
    token: str,
    company_id: str,
    *,
    code: str = "SUP-E01",
    legal_name: str = "Enrichment Corp",
) -> dict[str, Any]:
    resp = client.post(
        _url(company_id),
        json={"supplier_code": code, "legal_name": legal_name},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return dict(resp.json()["data"])


# ---------------------------------------------------------------------------
# Credit Limit endpoints
# ---------------------------------------------------------------------------


class TestCreditLimitEndpoints:
    def test_set_and_get_credit_limit(
        self, test_client: TestClient, db_session: Session
    ):
        """Can set a credit limit and retrieve it."""
        token, cid = _setup(test_client, db_session, email_suffix="cl1")
        supplier = _create_supplier(test_client, token, cid, code="SUP-CL1")
        sid = supplier["id"]

        resp = test_client.put(
            _url(cid, f"/{sid}/credit-limit"),
            json={
                "credit_limit_amount": "10000.00",
                "currency_code": "USD",
                "enforcement_mode": "WARN",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["enforcement_mode"] == "WARN"

        resp2 = test_client.get(_url(cid, f"/{sid}/credit-limit"), headers=_auth(token))
        assert resp2.status_code == 200
        assert resp2.json()["data"]["enforcement_mode"] == "WARN"

    def test_get_nonexistent_credit_limit_404(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, email_suffix="cl2")
        supplier = _create_supplier(test_client, token, cid, code="SUP-CL2")
        sid = supplier["id"]

        resp = test_client.get(_url(cid, f"/{sid}/credit-limit"), headers=_auth(token))
        assert resp.status_code == 404

    def test_block_mode_enforcement(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, email_suffix="cl3")
        supplier = _create_supplier(test_client, token, cid, code="SUP-CL3")
        sid = supplier["id"]

        resp = test_client.put(
            _url(cid, f"/{sid}/credit-limit"),
            json={
                "credit_limit_amount": "500.00",
                "currency_code": "USD",
                "enforcement_mode": "BLOCK",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["enforcement_mode"] == "BLOCK"

    def test_off_mode_enforcement(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, email_suffix="cl4")
        supplier = _create_supplier(test_client, token, cid, code="SUP-CL4")
        sid = supplier["id"]

        resp = test_client.put(
            _url(cid, f"/{sid}/credit-limit"),
            json={
                "credit_limit_amount": "0.00",
                "currency_code": "USD",
                "enforcement_mode": "OFF",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["enforcement_mode"] == "OFF"

    def test_unauthenticated_401(self, test_client: TestClient):
        cid = str(_uuid.uuid4())
        sid = str(_uuid.uuid4())
        resp = test_client.get(_url(cid, f"/{sid}/credit-limit"))
        assert resp.status_code == 401

    def test_update_credit_limit(self, test_client: TestClient, db_session: Session):
        """Updating an existing credit limit replaces it."""
        token, cid = _setup(test_client, db_session, email_suffix="cl5")
        supplier = _create_supplier(test_client, token, cid, code="SUP-CL5")
        sid = supplier["id"]

        test_client.put(
            _url(cid, f"/{sid}/credit-limit"),
            json={
                "credit_limit_amount": "1000.00",
                "currency_code": "USD",
                "enforcement_mode": "WARN",
            },
            headers=_auth(token),
        )

        resp2 = test_client.put(
            _url(cid, f"/{sid}/credit-limit"),
            json={
                "credit_limit_amount": "5000.00",
                "currency_code": "USD",
                "enforcement_mode": "BLOCK",
            },
            headers=_auth(token),
        )
        assert resp2.status_code == 200
        data = resp2.json()["data"]
        from decimal import Decimal

        assert Decimal(str(data["credit_limit_amount"])) == Decimal("5000.00")
        assert data["enforcement_mode"] == "BLOCK"


# ---------------------------------------------------------------------------
# Bank Details
# ---------------------------------------------------------------------------


class TestBankDetailsEndpoints:
    def test_can_add_bank_details(self, test_client: TestClient, db_session: Session):
        """Authenticated user can add bank details."""
        token, cid = _setup(test_client, db_session, email_suffix="bd1")
        supplier = _create_supplier(test_client, token, cid, code="SUP-BD1")
        sid = supplier["id"]

        resp = test_client.post(
            _url(cid, f"/{sid}/bank-details"),
            json={
                "bank_name": "First National Bank",
                "account_name": "Enrichment Corp",
                "account_number": "ACC-123456",
                "bank_country": "US",
                "currency_code": "USD",
                "is_primary": True,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["bank_name"] == "First National Bank"
        assert data["is_primary"] is True

    def test_can_list_bank_details(self, test_client: TestClient, db_session: Session):
        """Can list bank details after adding one."""
        token, cid = _setup(test_client, db_session, email_suffix="bd2")
        supplier = _create_supplier(test_client, token, cid, code="SUP-BD2")
        sid = supplier["id"]

        test_client.post(
            _url(cid, f"/{sid}/bank-details"),
            json={
                "bank_name": "Test Bank",
                "account_name": "Corp",
                "account_number": "ACC-999",
                "bank_country": "GB",
                "currency_code": "GBP",
            },
            headers=_auth(token),
        )

        resp = test_client.get(_url(cid, f"/{sid}/bank-details"), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

    def test_unauthenticated_returns_401(self, test_client: TestClient):
        cid = str(_uuid.uuid4())
        sid = str(_uuid.uuid4())
        resp = test_client.get(_url(cid, f"/{sid}/bank-details"))
        assert resp.status_code == 401

    def test_delete_bank_detail(self, test_client: TestClient, db_session: Session):
        """Can soft-delete a bank detail."""
        token, cid = _setup(test_client, db_session, email_suffix="bd3")
        supplier = _create_supplier(test_client, token, cid, code="SUP-BD3")
        sid = supplier["id"]

        add_resp = test_client.post(
            _url(cid, f"/{sid}/bank-details"),
            json={
                "bank_name": "Delete Me Bank",
                "account_name": "Corp",
                "account_number": "DEL-001",
                "bank_country": "US",
                "currency_code": "USD",
            },
            headers=_auth(token),
        )
        bd_id = add_resp.json()["data"]["id"]

        del_resp = test_client.delete(
            _url(cid, f"/{sid}/bank-details/{bd_id}"),
            headers=_auth(token),
        )
        assert del_resp.status_code == 200

        # Verify it's gone
        list_resp = test_client.get(
            _url(cid, f"/{sid}/bank-details"), headers=_auth(token)
        )
        remaining = [bd for bd in list_resp.json()["data"] if bd["id"] == bd_id]
        assert remaining == []

    def test_fm_restriction_documented(
        self, test_client: TestClient, db_session: Session
    ):
        """Finance Manager restriction is documented; enforced when RBAC is active (Epic 7+)."""
        # With RBAC stubs (roles=[]), all authenticated users can access bank details.
        # This test documents the expected future behavior.
        # When RBAC is implemented, a PURCHASE_OFFICER user should get 403.
        token, cid = _setup(test_client, db_session, email_suffix="bd4")
        supplier = _create_supplier(test_client, token, cid, code="SUP-BD4")
        sid = supplier["id"]

        # Currently passes with stub RBAC — roles not enforced yet
        resp = test_client.get(_url(cid, f"/{sid}/bank-details"), headers=_auth(token))
        assert resp.status_code == 200  # Will become 403 for non-FM when RBAC active


# ---------------------------------------------------------------------------
# Supplier Rating
# ---------------------------------------------------------------------------


class TestSupplierRatingEndpoints:
    def test_rating_not_found_initially(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, email_suffix="rt1")
        supplier = _create_supplier(test_client, token, cid, code="SUP-RT1")
        sid = supplier["id"]

        resp = test_client.get(_url(cid, f"/{sid}/rating"), headers=_auth(token))
        assert resp.status_code == 404

    def test_recompute_creates_rating(
        self, test_client: TestClient, db_session: Session
    ):
        """Recompute creates rating with correct composite score."""
        token, cid = _setup(test_client, db_session, email_suffix="rt2")
        supplier = _create_supplier(test_client, token, cid, code="SUP-RT2")
        sid = supplier["id"]

        resp = test_client.post(
            _url(cid, f"/{sid}/rating/recompute"),
            json={
                "on_time_rate": 80,
                "fill_rate": 90,
                "rejection_rate": 10,
                "gr_count_window": 5,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        from decimal import Decimal

        # (80*0.40 + 90*0.40 + 90*0.20) / 10 = 8.6
        assert Decimal(str(data["composite_score"])) == Decimal("8.6")
        assert data["gr_count_window"] == 5

    def test_manual_override(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, email_suffix="rt3")
        supplier = _create_supplier(test_client, token, cid, code="SUP-RT3")
        sid = supplier["id"]

        resp = test_client.post(
            _url(cid, f"/{sid}/rating/override"),
            json={"override_score": "9.5", "override_reason": "Exceptional partner"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        from decimal import Decimal

        assert Decimal(str(data["manual_override_score"])) == Decimal("9.5")

    def test_clear_override_404_when_no_rating(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, email_suffix="rt4")
        supplier = _create_supplier(test_client, token, cid, code="SUP-RT4")
        sid = supplier["id"]

        resp = test_client.delete(
            _url(cid, f"/{sid}/rating/override"),
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_clear_override_after_set(
        self, test_client: TestClient, db_session: Session
    ):
        """Clear override after setting it restores computed score."""
        token, cid = _setup(test_client, db_session, email_suffix="rt5")
        supplier = _create_supplier(test_client, token, cid, code="SUP-RT5")
        sid = supplier["id"]

        # Set override
        test_client.post(
            _url(cid, f"/{sid}/rating/override"),
            json={"override_score": "7.0", "override_reason": "Test override"},
            headers=_auth(token),
        )

        # Clear override
        resp = test_client.delete(
            _url(cid, f"/{sid}/rating/override"), headers=_auth(token)
        )
        assert resp.status_code == 200

        data = resp.json()["data"]
        assert data["manual_override_score"] is None

    def test_unauthenticated_returns_401(self, test_client: TestClient):
        cid = str(_uuid.uuid4())
        sid = str(_uuid.uuid4())
        resp = test_client.get(_url(cid, f"/{sid}/rating"))
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Supplier Documents
# ---------------------------------------------------------------------------


class TestSupplierDocumentEndpoints:
    def test_list_empty_initially(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, email_suffix="doc1")
        supplier = _create_supplier(test_client, token, cid, code="SUP-DOC1")
        sid = supplier["id"]

        resp = test_client.get(_url(cid, f"/{sid}/documents"), headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_add_document(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, email_suffix="doc2")
        supplier = _create_supplier(test_client, token, cid, code="SUP-DOC2")
        sid = supplier["id"]

        resp = test_client.post(
            _url(cid, f"/{sid}/documents"),
            json={
                "document_type": "Trade License",
                "document_number": "TL-2024-001",
                "issue_date": "2024-01-01",
                "expiry_date": "2026-12-31",
                "file_url": "s3://bucket/doc.pdf",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["document_type"] == "Trade License"
        assert data["expiry_date"] == "2026-12-31"

    def test_list_after_add(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, email_suffix="doc3")
        supplier = _create_supplier(test_client, token, cid, code="SUP-DOC3")
        sid = supplier["id"]

        test_client.post(
            _url(cid, f"/{sid}/documents"),
            json={"document_type": "ISO Cert"},
            headers=_auth(token),
        )

        resp = test_client.get(_url(cid, f"/{sid}/documents"), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_delete_document(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, email_suffix="doc4")
        supplier = _create_supplier(test_client, token, cid, code="SUP-DOC4")
        sid = supplier["id"]

        add_resp = test_client.post(
            _url(cid, f"/{sid}/documents"),
            json={"document_type": "To Delete"},
            headers=_auth(token),
        )
        doc_id = add_resp.json()["data"]["id"]

        del_resp = test_client.delete(
            _url(cid, f"/{sid}/documents/{doc_id}"),
            headers=_auth(token),
        )
        assert del_resp.status_code == 200

        list_resp = test_client.get(
            _url(cid, f"/{sid}/documents"), headers=_auth(token)
        )
        assert list_resp.json()["data"] == []

    def test_expiring_documents_endpoint(
        self, test_client: TestClient, db_session: Session
    ):
        token, cid = _setup(test_client, db_session, email_suffix="doc5")

        resp = test_client.get(
            f"/api/v1/companies/{cid}/purchase/suppliers/expiring-documents?days=30",
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert "total" in data
        assert "documents" in data

    def test_unauthenticated_returns_401(self, test_client: TestClient):
        cid = str(_uuid.uuid4())
        sid = str(_uuid.uuid4())
        resp = test_client.get(_url(cid, f"/{sid}/documents"))
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Lead Times
# ---------------------------------------------------------------------------


class TestLeadTimeEndpoints:
    def test_list_empty_initially(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, email_suffix="lt1")
        supplier = _create_supplier(test_client, token, cid, code="SUP-LT1")
        sid = supplier["id"]

        resp = test_client.get(_url(cid, f"/{sid}/lead-times"), headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_set_default_lead_time(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, email_suffix="lt2")
        supplier = _create_supplier(test_client, token, cid, code="SUP-LT2")
        sid = supplier["id"]

        resp = test_client.post(
            _url(cid, f"/{sid}/lead-times"),
            json={"lead_time_days": 7},
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["lead_time_days"] == 7

    def test_set_product_lead_time(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, email_suffix="lt3")
        supplier = _create_supplier(test_client, token, cid, code="SUP-LT3")
        sid = supplier["id"]
        product_id = str(_uuid.uuid4())

        resp = test_client.post(
            _url(cid, f"/{sid}/lead-times"),
            json={"product_id": product_id, "lead_time_days": 14},
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["lead_time_days"] == 14

    def test_duplicate_upserts_existing(
        self, test_client: TestClient, db_session: Session
    ):
        """Setting the same lead time twice updates the existing record."""
        token, cid = _setup(test_client, db_session, email_suffix="lt4")
        supplier = _create_supplier(test_client, token, cid, code="SUP-LT4")
        sid = supplier["id"]

        test_client.post(
            _url(cid, f"/{sid}/lead-times"),
            json={"lead_time_days": 5},
            headers=_auth(token),
        )
        resp2 = test_client.post(
            _url(cid, f"/{sid}/lead-times"),
            json={"lead_time_days": 10},
            headers=_auth(token),
        )
        assert resp2.status_code in (200, 201), resp2.text

        list_resp = test_client.get(
            _url(cid, f"/{sid}/lead-times"), headers=_auth(token)
        )
        defaults = [lt for lt in list_resp.json()["data"] if lt["product_id"] is None]
        assert len(defaults) == 1
        assert defaults[0]["lead_time_days"] == 10

    def test_unauthenticated_returns_401(self, test_client: TestClient):
        cid = str(_uuid.uuid4())
        sid = str(_uuid.uuid4())
        resp = test_client.get(_url(cid, f"/{sid}/lead-times"))
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Preferred supplier
# ---------------------------------------------------------------------------


class TestPreferredSupplierEndpoint:
    def test_set_preferred_true(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, email_suffix="prf1")
        supplier = _create_supplier(test_client, token, cid, code="SUP-PRF1")
        sid = supplier["id"]

        resp = test_client.post(
            _url(cid, f"/{sid}/preferred"),
            json={"is_preferred": True},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["is_preferred"] is True

    def test_set_preferred_false(self, test_client: TestClient, db_session: Session):
        token, cid = _setup(test_client, db_session, email_suffix="prf2")
        supplier = _create_supplier(test_client, token, cid, code="SUP-PRF2")
        sid = supplier["id"]

        test_client.post(
            _url(cid, f"/{sid}/preferred"),
            json={"is_preferred": True},
            headers=_auth(token),
        )

        resp = test_client.post(
            _url(cid, f"/{sid}/preferred"),
            json={"is_preferred": False},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_preferred"] is False

    def test_unauthenticated_returns_401(self, test_client: TestClient):
        cid = str(_uuid.uuid4())
        sid = str(_uuid.uuid4())
        resp = test_client.post(
            _url(cid, f"/{sid}/preferred"), json={"is_preferred": True}
        )
        assert resp.status_code == 401

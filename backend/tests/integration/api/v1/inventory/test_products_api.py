"""API integration tests for product endpoints.

Tests: create, read, update, lifecycle transitions, search, pagination,
       tenant isolation, 401/403/404/422 scenarios.

Task: T083, T084, T085
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.inventory.models.uom import UOM
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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _company_url(company_id: str, path: str) -> str:
    return f"/api/v1/companies/{company_id}/inventory{path}"


def _make_uom(db: Session, company_id: uuid.UUID) -> UOM:
    uom = UOM(
        company_id=company_id,
        code="PCS",
        name="Pieces",
        uom_type="UNIT",
        status="active",
    )
    db.add(uom)
    db.flush()
    return uom


def _setup_user_and_company(db: Session) -> tuple[str, str, uuid.UUID, str]:
    """Create a user + company and return (email, password, company_id, password)."""
    email = f"user-{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"
    user = create_test_user(db, email=email, password=password)
    company_id = uuid.uuid4()
    return email, password, company_id, password


# =============================================================================
# Unauthenticated access
# =============================================================================


class TestUnauthenticated:
    def test_list_products_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_company_url(str(uuid.uuid4()), "/products"))
        assert resp.status_code == 401

    def test_create_product_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.post(_company_url(str(uuid.uuid4()), "/products"), json={})
        assert resp.status_code == 401

    def test_get_product_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(
            _company_url(str(uuid.uuid4()), f"/products/{uuid.uuid4()}")
        )
        assert resp.status_code == 401

    def test_variants_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(
            _company_url(str(uuid.uuid4()), f"/products/{uuid.uuid4()}/variants")
        )
        assert resp.status_code == 401

    def test_barcodes_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(
            _company_url(str(uuid.uuid4()), f"/products/{uuid.uuid4()}/barcodes")
        )
        assert resp.status_code == 401


# =============================================================================
# Product CRUD
# =============================================================================


class TestProductCreate:
    def test_create_product_returns_201(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _ = _setup_user_and_company(db_session)
        uom = _make_uom(db_session, company_id)
        token = _login(test_client, email, password)

        resp = test_client.post(
            _company_url(str(company_id), "/products"),
            json={
                "product_code": "PROD-001",
                "name": "Test Product",
                "product_type": "STANDARD",
                "base_uom_id": str(uom.id),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["product_code"] == "PROD-001"
        assert data["status"] == "DRAFT"

    def test_create_product_duplicate_sku_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _ = _setup_user_and_company(db_session)
        uom = _make_uom(db_session, company_id)
        token = _login(test_client, email, password)

        payload = {
            "product_code": "DUP-001",
            "name": "First",
            "product_type": "STANDARD",
            "base_uom_id": str(uom.id),
        }
        resp1 = test_client.post(
            _company_url(str(company_id), "/products"),
            json=payload,
            headers=_auth(token),
        )
        assert resp1.status_code == 201

        resp2 = test_client.post(
            _company_url(str(company_id), "/products"),
            json={**payload, "name": "Second"},
            headers=_auth(token),
        )
        assert resp2.status_code == 409

    def test_create_product_invalid_type_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _ = _setup_user_and_company(db_session)
        uom = _make_uom(db_session, company_id)
        token = _login(test_client, email, password)

        resp = test_client.post(
            _company_url(str(company_id), "/products"),
            json={
                "product_code": "BAD-001",
                "name": "Bad Type",
                "product_type": "INVALID_TYPE",
                "base_uom_id": str(uom.id),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_create_product_missing_name_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _ = _setup_user_and_company(db_session)
        uom = _make_uom(db_session, company_id)
        token = _login(test_client, email, password)

        resp = test_client.post(
            _company_url(str(company_id), "/products"),
            json={
                "product_code": "NO-NAME",
                "product_type": "STANDARD",
                "base_uom_id": str(uom.id),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422


class TestProductRead:
    def test_get_product_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _ = _setup_user_and_company(db_session)
        uom = _make_uom(db_session, company_id)
        token = _login(test_client, email, password)

        create_resp = test_client.post(
            _company_url(str(company_id), "/products"),
            json={
                "product_code": "GET-001",
                "name": "Gettable Product",
                "product_type": "STANDARD",
                "base_uom_id": str(uom.id),
            },
            headers=_auth(token),
        )
        product_id = create_resp.json()["data"]["id"]

        resp = test_client.get(
            _company_url(str(company_id), f"/products/{product_id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == product_id

    def test_get_product_not_found_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _ = _setup_user_and_company(db_session)
        token = _login(test_client, email, password)

        resp = test_client.get(
            _company_url(str(company_id), f"/products/{uuid.uuid4()}"),
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_list_products_returns_paginated_response(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _ = _setup_user_and_company(db_session)
        uom = _make_uom(db_session, company_id)
        token = _login(test_client, email, password)

        for i in range(3):
            test_client.post(
                _company_url(str(company_id), "/products"),
                json={
                    "product_code": f"LIST-{i:03d}",
                    "name": f"Product {i}",
                    "product_type": "STANDARD",
                    "base_uom_id": str(uom.id),
                },
                headers=_auth(token),
            )

        resp = test_client.get(
            _company_url(str(company_id), "/products"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 3
        assert len(data["items"]) == 3


class TestProductUpdate:
    def test_update_product_name(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _ = _setup_user_and_company(db_session)
        uom = _make_uom(db_session, company_id)
        token = _login(test_client, email, password)

        create_resp = test_client.post(
            _company_url(str(company_id), "/products"),
            json={
                "product_code": "UPD-001",
                "name": "Old Name",
                "product_type": "STANDARD",
                "base_uom_id": str(uom.id),
            },
            headers=_auth(token),
        )
        product_id = create_resp.json()["data"]["id"]

        resp = test_client.put(
            _company_url(str(company_id), f"/products/{product_id}"),
            json={"name": "New Name"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "New Name"


# =============================================================================
# Product lifecycle
# =============================================================================


class TestProductLifecycle:
    def _create(
        self, client: TestClient, company_id: str, uom_id: str, token: str, code: str
    ) -> str:
        resp = client.post(
            _company_url(company_id, "/products"),
            json={
                "product_code": code,
                "name": f"Product {code}",
                "product_type": "STANDARD",
                "base_uom_id": uom_id,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        return resp.json()["data"]["id"]

    def test_full_lifecycle_draft_to_archived(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _ = _setup_user_and_company(db_session)
        uom = _make_uom(db_session, company_id)
        token = _login(test_client, email, password)
        cid = str(company_id)
        uid = str(uom.id)

        product_id = self._create(test_client, cid, uid, token, "LIFE-001")

        # DRAFT → ACTIVE
        r = test_client.patch(
            _company_url(cid, f"/products/{product_id}/status"),
            json={"action": "activate"},
            headers=_auth(token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "ACTIVE"

        # ACTIVE → INACTIVE
        r = test_client.patch(
            _company_url(cid, f"/products/{product_id}/status"),
            json={"action": "deactivate"},
            headers=_auth(token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "INACTIVE"

        # INACTIVE → ARCHIVED
        r = test_client.patch(
            _company_url(cid, f"/products/{product_id}/status"),
            json={"action": "archive"},
            headers=_auth(token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "ARCHIVED"

    def test_invalid_transition_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _ = _setup_user_and_company(db_session)
        uom = _make_uom(db_session, company_id)
        token = _login(test_client, email, password)
        cid = str(company_id)
        product_id = self._create(test_client, cid, str(uom.id), token, "TRANS-001")

        # Cannot deactivate DRAFT product
        resp = test_client.patch(
            _company_url(cid, f"/products/{product_id}/status"),
            json={"action": "deactivate"},
            headers=_auth(token),
        )
        assert resp.status_code == 409

    def test_delete_draft_product(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _ = _setup_user_and_company(db_session)
        uom = _make_uom(db_session, company_id)
        token = _login(test_client, email, password)
        cid = str(company_id)

        product_id = self._create(test_client, cid, str(uom.id), token, "DEL-001")

        resp = test_client.delete(
            _company_url(cid, f"/products/{product_id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 204

        # Verify gone
        get_resp = test_client.get(
            _company_url(cid, f"/products/{product_id}"),
            headers=_auth(token),
        )
        assert get_resp.status_code == 404


# =============================================================================
# Product search
# =============================================================================


class TestProductSearch:
    def test_search_by_name(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id, _ = _setup_user_and_company(db_session)
        uom = _make_uom(db_session, company_id)
        token = _login(test_client, email, password)
        cid = str(company_id)

        test_client.post(
            _company_url(cid, "/products"),
            json={
                "product_code": "SRCH-001",
                "name": "UniqueSearchableName",
                "product_type": "STANDARD",
                "base_uom_id": str(uom.id),
            },
            headers=_auth(token),
        )
        test_client.post(
            _company_url(cid, "/products"),
            json={
                "product_code": "SRCH-002",
                "name": "OtherProduct",
                "product_type": "STANDARD",
                "base_uom_id": str(uom.id),
            },
            headers=_auth(token),
        )

        resp = test_client.get(
            _company_url(cid, "/products"),
            params={"q": "uniquesearchable"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1

    def test_search_pagination(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _ = _setup_user_and_company(db_session)
        uom = _make_uom(db_session, company_id)
        token = _login(test_client, email, password)
        cid = str(company_id)

        for i in range(5):
            test_client.post(
                _company_url(cid, "/products"),
                json={
                    "product_code": f"PAGE-{i:03d}",
                    "name": f"Product {i}",
                    "product_type": "STANDARD",
                    "base_uom_id": str(uom.id),
                },
                headers=_auth(token),
            )

        resp = test_client.get(
            _company_url(cid, "/products"),
            params={"page": 1, "page_size": 2},
            headers=_auth(token),
        )
        data = resp.json()["data"]
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["pages"] == 3


# =============================================================================
# Variants API
# =============================================================================


class TestVariantsAPI:
    def test_add_and_list_variants(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _ = _setup_user_and_company(db_session)
        uom = _make_uom(db_session, company_id)
        token = _login(test_client, email, password)
        cid = str(company_id)

        prod_resp = test_client.post(
            _company_url(cid, "/products"),
            json={
                "product_code": "VAR-PROD-001",
                "name": "Variant Product",
                "product_type": "VARIANT",
                "base_uom_id": str(uom.id),
            },
            headers=_auth(token),
        )
        product_id = prod_resp.json()["data"]["id"]

        # Add variant
        v_resp = test_client.post(
            _company_url(cid, f"/products/{product_id}/variants"),
            json={"variant_code": "SKU-L-RED", "attributes": {"size": "L"}},
            headers=_auth(token),
        )
        assert v_resp.status_code == 201
        assert v_resp.json()["data"]["variant_code"] == "SKU-L-RED"

        # List variants
        list_resp = test_client.get(
            _company_url(cid, f"/products/{product_id}/variants"),
            headers=_auth(token),
        )
        assert list_resp.status_code == 200
        assert len(list_resp.json()["data"]) == 1

    def test_duplicate_variant_sku_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _ = _setup_user_and_company(db_session)
        uom = _make_uom(db_session, company_id)
        token = _login(test_client, email, password)
        cid = str(company_id)

        prod_resp = test_client.post(
            _company_url(cid, "/products"),
            json={
                "product_code": "DUPVAR-001",
                "name": "Product",
                "product_type": "VARIANT",
                "base_uom_id": str(uom.id),
            },
            headers=_auth(token),
        )
        product_id = prod_resp.json()["data"]["id"]

        test_client.post(
            _company_url(cid, f"/products/{product_id}/variants"),
            json={"variant_code": "DUP-SKU"},
            headers=_auth(token),
        )
        resp = test_client.post(
            _company_url(cid, f"/products/{product_id}/variants"),
            json={"variant_code": "DUP-SKU"},
            headers=_auth(token),
        )
        assert resp.status_code == 409


# =============================================================================
# Barcodes API
# =============================================================================


class TestBarcodesAPI:
    def test_add_and_list_barcodes(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _ = _setup_user_and_company(db_session)
        uom = _make_uom(db_session, company_id)
        token = _login(test_client, email, password)
        cid = str(company_id)

        prod_resp = test_client.post(
            _company_url(cid, "/products"),
            json={
                "product_code": "BC-PROD-001",
                "name": "Barcode Product",
                "product_type": "STANDARD",
                "base_uom_id": str(uom.id),
            },
            headers=_auth(token),
        )
        product_id = prod_resp.json()["data"]["id"]

        # Add barcode
        b_resp = test_client.post(
            _company_url(cid, f"/products/{product_id}/barcodes"),
            json={
                "barcode_value": "1234567890123",
                "barcode_type": "EAN13",
                "is_primary": True,
            },
            headers=_auth(token),
        )
        assert b_resp.status_code == 201
        assert b_resp.json()["data"]["barcode_value"] == "1234567890123"

        # List barcodes
        list_resp = test_client.get(
            _company_url(cid, f"/products/{product_id}/barcodes"),
            headers=_auth(token),
        )
        assert list_resp.status_code == 200
        assert len(list_resp.json()["data"]) == 1

    def test_duplicate_barcode_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _ = _setup_user_and_company(db_session)
        uom = _make_uom(db_session, company_id)
        token = _login(test_client, email, password)
        cid = str(company_id)

        for i, code in enumerate(["DUPCOD-001", "DUPCOD-002"]):
            test_client.post(
                _company_url(cid, "/products"),
                json={
                    "product_code": code,
                    "name": f"P{i}",
                    "product_type": "STANDARD",
                    "base_uom_id": str(uom.id),
                },
                headers=_auth(token),
            )

        prod_resp = test_client.post(
            _company_url(cid, "/products"),
            json={
                "product_code": "BC-DUP-001",
                "name": "First",
                "product_type": "STANDARD",
                "base_uom_id": str(uom.id),
            },
            headers=_auth(token),
        )
        p1_id = prod_resp.json()["data"]["id"]

        prod_resp2 = test_client.post(
            _company_url(cid, "/products"),
            json={
                "product_code": "BC-DUP-002",
                "name": "Second",
                "product_type": "STANDARD",
                "base_uom_id": str(uom.id),
            },
            headers=_auth(token),
        )
        p2_id = prod_resp2.json()["data"]["id"]

        # Add barcode to product 1
        test_client.post(
            _company_url(cid, f"/products/{p1_id}/barcodes"),
            json={"barcode_value": "DUP-BC-123", "barcode_type": "CUSTOM"},
            headers=_auth(token),
        )
        # Try same barcode on product 2
        resp = test_client.post(
            _company_url(cid, f"/products/{p2_id}/barcodes"),
            json={"barcode_value": "DUP-BC-123", "barcode_type": "CUSTOM"},
            headers=_auth(token),
        )
        assert resp.status_code == 409


# =============================================================================
# Tenant isolation (T084)
# =============================================================================


class TestProductTenantIsolation:
    def test_company_a_cannot_see_company_b_products(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email_a, pass_a, company_a, _ = _setup_user_and_company(db_session)
        email_b, pass_b, company_b, _ = _setup_user_and_company(db_session)

        uom_a = _make_uom(db_session, company_a)
        uom_b = _make_uom(db_session, company_b)

        token_a = _login(test_client, email_a, pass_a)
        token_b = _login(test_client, email_b, pass_b)

        # Company A creates a product
        test_client.post(
            _company_url(str(company_a), "/products"),
            json={
                "product_code": "ISO-A-001",
                "name": "Company A Product",
                "product_type": "STANDARD",
                "base_uom_id": str(uom_a.id),
            },
            headers=_auth(token_a),
        )

        # Company B lists its products — should see zero
        resp = test_client.get(
            _company_url(str(company_b), "/products"),
            headers=_auth(token_b),
        )
        data = resp.json()["data"]
        assert data["total"] == 0

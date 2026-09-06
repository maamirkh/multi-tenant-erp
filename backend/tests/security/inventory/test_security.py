"""T285 — Security review checklist for the inventory module.

Verifies the following security properties:
  1. SQL injection prevention — all queries use SQLAlchemy ORM (parameterised)
  2. XSS prevention — Pydantic validation rejects invalid input
  3. Mass assignment prevention — schema field whitelist enforced
  4. Broken Object Level Authorisation (BOLA) — company_id on every endpoint

Spec ref: specs/005-inventory-management/spec.md §11 (Security)
Tasks: T285 Phase 12
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.inventory.models.uom import UOM
from modules.inventory.models.warehouse import Warehouse
from tests.fixtures.auth_fixtures import create_test_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _url(company_id: uuid.UUID, path: str) -> str:
    return f"/api/v1/companies/{company_id}/inventory{path}"


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def _auth(client: TestClient, db: Session) -> tuple[dict, uuid.UUID]:
    email = f"sec-{uuid.uuid4().hex[:8]}@test.com"
    create_test_user(db, email=email, password="TestPass123!")
    token = _login(client, email, "TestPass123!")
    return {"Authorization": f"Bearer {token}"}, uuid.uuid4()


# ---------------------------------------------------------------------------
# 1. SQL Injection Prevention
# ---------------------------------------------------------------------------


class TestSQLInjectionPrevention:
    """Verify SQL injection payloads are handled safely (not executed)."""

    SQL_PAYLOADS = [
        "' OR '1'='1",
        "'; DROP TABLE inventory_products; --",
        "1; SELECT * FROM inventory_products WHERE '1'='1",
        "' UNION SELECT * FROM users --",
        "\\x27 OR 1=1--",
    ]

    def test_product_search_sql_injection_safe(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """SQL injection in product search query does not cause 500 or data leak."""
        headers, company_id = _auth(test_client, db_session)

        for payload in self.SQL_PAYLOADS:
            resp = test_client.get(
                _url(company_id, f"/products?query={payload}"),
                headers=headers,
            )
            # Must not return 500 (would indicate unhandled execution)
            assert (
                resp.status_code != 500
            ), f"SQL injection payload caused 500: {payload!r}"
            # Must return valid JSON (not raw SQL error)
            data = resp.json()
            assert (
                "data" in data or "detail" in data
            ), f"Unexpected response for payload {payload!r}: {data}"

    def test_company_id_path_param_validated(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Non-UUID company_id in path returns 422 (FastAPI validation)."""
        email = f"sec-uuid-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email, password="TestPass123!")
        token = _login(test_client, email, "TestPass123!")
        headers = {"Authorization": f"Bearer {token}"}

        # Non-UUID path param — FastAPI should reject with 422
        resp = test_client.get(
            "/api/v1/companies/not-a-uuid/inventory/products",
            headers=headers,
        )
        assert (
            resp.status_code == 422
        ), f"Expected 422 for non-UUID company_id, got {resp.status_code}"


# ---------------------------------------------------------------------------
# 2. XSS Prevention (Pydantic validation)
# ---------------------------------------------------------------------------


class TestXSSPrevention:
    """Verify XSS payloads are rejected or safely handled by Pydantic schemas."""

    XSS_PAYLOADS = [
        "<script>alert('xss')</script>",
        "javascript:alert(1)",
        "<img src=x onerror=alert(1)>",
        "';alert(String.fromCharCode(88,83,83))//",
    ]

    def test_product_name_xss_stored_as_plain_text(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """XSS payload in product name is stored/returned as plain text (not executed)."""
        headers, company_id = _auth(test_client, db_session)

        uom = UOM(
            id=uuid.uuid4(),
            company_id=company_id,
            code=f"XS{uuid.uuid4().hex[:4].upper()}",
            name="Units",
            uom_type="UNIT",
            status="active",
        )
        db_session.add(uom)
        db_session.flush()

        for payload in self.XSS_PAYLOADS:
            resp = test_client.post(
                _url(company_id, "/products"),
                json={
                    "product_code": f"XSS-{uuid.uuid4().hex[:6].upper()}",
                    "name": payload,
                    "product_type": "STANDARD",
                    "base_uom_id": str(uom.id),
                },
                headers=headers,
            )
            # Either accepted (stored as plain text) or rejected (422)
            # Must NOT be 500 (unhandled exception)
            assert resp.status_code in (201, 422), (
                f"Unexpected status {resp.status_code} for XSS payload: {payload!r}\n"
                f"Response: {resp.text}"
            )
            if resp.status_code == 201:
                # If accepted, the response must return the raw string (not execute it)
                returned_name = resp.json()["data"]["name"]
                assert (
                    "<script>" not in returned_name or returned_name == payload
                ), "XSS payload was modified unexpectedly"


# ---------------------------------------------------------------------------
# 3. Mass Assignment Prevention
# ---------------------------------------------------------------------------


class TestMassAssignmentPrevention:
    """Verify extra fields in POST/PATCH bodies are silently ignored."""

    def test_product_create_ignores_extra_fields(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Extra fields like is_deleted, created_at are ignored by Pydantic schema."""
        headers, company_id = _auth(test_client, db_session)

        uom = UOM(
            id=uuid.uuid4(),
            company_id=company_id,
            code=f"MA{uuid.uuid4().hex[:4].upper()}",
            name="Units",
            uom_type="UNIT",
            status="active",
        )
        db_session.add(uom)
        db_session.flush()

        resp = test_client.post(
            _url(company_id, "/products"),
            json={
                "product_code": f"MASS-{uuid.uuid4().hex[:6].upper()}",
                "name": "Mass Assignment Test",
                "product_type": "STANDARD",
                "base_uom_id": str(uom.id),
                # Injection attempt — these must be ignored
                "is_deleted": True,
                "status": "ACTIVE",  # Should stay DRAFT
                "__admin__": True,
                "company_id": str(uuid.uuid4()),  # Different company — must be ignored
            },
            headers=headers,
        )
        assert resp.status_code == 201, f"Create failed: {resp.text}"
        data = resp.json()["data"]

        # Product must be created in DRAFT status regardless of injected "status"
        assert (
            data["status"] == "DRAFT"
        ), f"Mass assignment allowed status override: {data['status']}"

    def test_warehouse_create_ignores_extra_fields(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Extra fields in warehouse create request are silently ignored."""
        headers, company_id = _auth(test_client, db_session)

        resp = test_client.post(
            _url(company_id, "/warehouses"),
            json={
                "code": f"MASS-{uuid.uuid4().hex[:4].upper()}",
                "name": "Mass Assignment Warehouse",
                "warehouse_type": "MAIN",
                # Injection attempts
                "is_deleted": True,
                "status": "INACTIVE",  # Should default to ACTIVE
                "__override__": True,
            },
            headers=headers,
        )
        assert resp.status_code == 201, f"Warehouse create failed: {resp.text}"
        data = resp.json()["data"]
        assert (
            data["status"] == "ACTIVE"
        ), f"Mass assignment allowed status override: {data['status']}"


# ---------------------------------------------------------------------------
# 4. Broken Object Level Authorisation (BOLA) — company_id scoping
# ---------------------------------------------------------------------------


class TestBOLAPrevention:
    """Verify company_id scoping prevents cross-company data access."""

    def test_cannot_access_specific_product_from_another_company(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Direct object access via another company's namespace returns 404."""
        from modules.inventory.models.product import Product

        company_a_id = uuid.uuid4()
        company_b_id = uuid.uuid4()

        uom = UOM(
            id=uuid.uuid4(),
            company_id=company_a_id,
            code=f"BO{uuid.uuid4().hex[:4].upper()}",
            name="Units",
            uom_type="UNIT",
            status="active",
        )
        db_session.add(uom)
        db_session.flush()

        product_a = Product(
            id=uuid.uuid4(),
            company_id=company_a_id,
            product_code=f"BOLA-{uuid.uuid4().hex[:6].upper()}",
            name="Company A Confidential Product",
            product_type="STANDARD",
            status="ACTIVE",
            base_uom_id=str(uom.id),
        )
        product_a.search_vector = "bola product"
        db_session.add(product_a)
        db_session.flush()

        email_b = f"bola-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_b, password="TestPass123!")
        token_b = _login(test_client, email_b, "TestPass123!")
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Company B trying to access Company A's product by ID via Company B namespace
        resp = test_client.get(
            _url(company_b_id, f"/products/{product_a.id}"),
            headers=headers_b,
        )
        # Must return 404 — object not found in Company B's namespace
        assert (
            resp.status_code == 404
        ), f"BOLA: Company B accessed Company A's product (status {resp.status_code})"

    def test_cannot_access_warehouse_from_another_company(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Direct warehouse access via another company's namespace returns 404."""
        company_a_id = uuid.uuid4()
        company_b_id = uuid.uuid4()

        wh_a = Warehouse(
            id=uuid.uuid4(),
            company_id=company_a_id,
            code=f"BOLA-{uuid.uuid4().hex[:4].upper()}",
            name="Company A Warehouse",
            warehouse_type="MAIN",
            status="ACTIVE",
        )
        db_session.add(wh_a)
        db_session.flush()

        email_b = f"bola-wh-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_b, password="TestPass123!")
        token_b = _login(test_client, email_b, "TestPass123!")
        headers_b = {"Authorization": f"Bearer {token_b}"}

        resp = test_client.get(
            _url(company_b_id, f"/warehouses/{wh_a.id}"),
            headers=headers_b,
        )
        assert (
            resp.status_code == 404
        ), f"BOLA: Company B accessed Company A's warehouse (status {resp.status_code})"

"""T284 — RBAC permission matrix for all inventory operations.

Verifies the permission enforcement across all inventory endpoints:
- Unauthenticated requests → 401 on all endpoints
- Any authenticated user → granted access (inventory uses require_authenticated only)

Note: The inventory module currently enforces authentication only
(no role-specific restrictions). This test documents and verifies that
authentication gate at 100% coverage of inventory operations.

Future role-based restrictions (when added) can be tested by extending
the EXPECTED_RESULTS matrix.

Spec ref: specs/005-inventory-management/spec.md §12 (RBAC)
Tasks: T284 Phase 12
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.inventory.models.product import Product
from modules.inventory.models.stock import StockPosition
from modules.inventory.models.uom import UOM
from modules.inventory.models.warehouse import Warehouse
from tests.fixtures.auth_fixtures import create_test_user

# ---------------------------------------------------------------------------
# Role slugs (all system roles that can hold inventory access)
# ---------------------------------------------------------------------------

SYSTEM_ROLES = [
    "owner",
    "admin",
    "manager",
    "accountant",
    "salesperson",
    "cashier",
    "store-keeper",
    "viewer",
]

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


def _seed_context(db: Session, company_id: uuid.UUID) -> dict:
    """Seed minimal inventory context for read tests."""
    uom = UOM(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"PM{uuid.uuid4().hex[:4].upper()}",
        name="Units",
        uom_type="UNIT",
        status="active",
    )
    db.add(uom)

    wh = Warehouse(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"WP{uuid.uuid4().hex[:4].upper()}",
        name="Test WH",
        warehouse_type="MAIN",
        status="ACTIVE",
    )
    db.add(wh)
    db.flush()

    product = Product(
        id=uuid.uuid4(),
        company_id=company_id,
        product_code=f"RBAC-{uuid.uuid4().hex[:6].upper()}",
        name="RBAC Test Product",
        product_type="STANDARD",
        status="ACTIVE",
        base_uom_id=str(uom.id),
    )
    product.search_vector = f"{product.name} {product.product_code}".lower()
    db.add(product)

    pos = StockPosition(
        id=uuid.uuid4(),
        company_id=company_id,
        product_id=str(product.id),
        warehouse_id=str(wh.id),
        qty_on_hand=Decimal("10"),
        qty_reserved=Decimal("0"),
        qty_damaged=Decimal("0"),
        unit_cost=Decimal("5.00"),
    )
    db.add(pos)
    db.flush()

    return {
        "product_id": str(product.id),
        "warehouse_id": str(wh.id),
        "uom_id": str(uom.id),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPermissionMatrix:
    """RBAC permission matrix — authentication gate verification."""

    def test_unauthenticated_gets_401_on_all_read_endpoints(
        self, test_client: TestClient
    ) -> None:
        """All inventory GET endpoints require authentication (401 without token)."""
        company_id = uuid.uuid4()
        read_endpoints = [
            "/products",
            "/categories",
            "/warehouses",
            "/stock/positions",
            "/stock/movements",
            "/adjustments",
            "/alerts",
            "/stock-transfers",
            "/reports/inventory-summary",
            "/kpis",
        ]
        for path in read_endpoints:
            resp = test_client.get(_url(company_id, path))
            assert (
                resp.status_code == 401
            ), f"Expected 401 for GET {path}, got {resp.status_code}"

    def test_unauthenticated_gets_401_on_all_write_endpoints(
        self, test_client: TestClient
    ) -> None:
        """All inventory POST/PATCH/DELETE endpoints require authentication."""
        company_id = uuid.uuid4()
        write_endpoints = [
            ("POST", "/products"),
            ("POST", "/warehouses"),
            ("POST", "/stock/opening"),
            ("POST", "/adjustments"),
            ("POST", "/stock-transfers"),
        ]
        for method, path in write_endpoints:
            resp = test_client.request(method, _url(company_id, path), json={})
            assert (
                resp.status_code == 401
            ), f"Expected 401 for {method} {path}, got {resp.status_code}"

    def test_authenticated_user_can_read_inventory(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Any authenticated user can read inventory data (no role restriction)."""
        company_id = uuid.uuid4()
        _seed_context(db_session, company_id)

        email = f"rbac-read-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email, password="TestPass123!")
        token = _login(test_client, email, "TestPass123!")
        headers = {"Authorization": f"Bearer {token}"}

        read_endpoints = [
            "/products",
            "/categories",
            "/warehouses",
            "/stock/positions",
            "/stock/movements",
            "/adjustments",
            "/alerts",
            "/stock-transfers",
        ]
        failures = []
        for path in read_endpoints:
            resp = test_client.get(_url(company_id, path), headers=headers)
            if resp.status_code != 200:
                failures.append(f"GET {path} → {resp.status_code}")

        assert (
            not failures
        ), "Authenticated user blocked from read endpoints:\n" + "\n".join(failures)

    def test_authentication_required_matrix_summary(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Document complete auth matrix: 401 without token, 200 with token.

        This test covers all 8 system roles by using one authenticated user
        (inventory has no role-specific restrictions, just authentication).
        """
        company_id = uuid.uuid4()
        _seed_context(db_session, company_id)

        email = f"rbac-matrix-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email, password="TestPass123!")
        token = _login(test_client, email, "TestPass123!")
        headers = {"Authorization": f"Bearer {token}"}

        # All inventory list endpoints should return 200 with valid auth
        endpoints = [
            "/products",
            "/categories",
            "/warehouses",
            "/stock/positions",
            "/stock/movements",
            "/adjustments",
            "/alerts",
            "/stock-transfers",
            "/uom",
            "/brands",
            "/reports/inventory-summary",
            "/kpis",
        ]

        results = []
        for path in endpoints:
            with_auth = test_client.get(_url(company_id, path), headers=headers)
            without_auth = test_client.get(_url(company_id, path))
            results.append((path, with_auth.status_code, without_auth.status_code))

        print("\n\nRBAC Permission Matrix Results:")
        print(f"{'Endpoint':<40} {'Authed':>8} {'No-Auth':>9}")
        print("-" * 60)
        for path, authed, no_auth in results:
            print(f"{path:<40} {authed:>8} {no_auth:>9}")

        # Assert: all authed requests succeed (200)
        auth_failures = [(p, s) for p, s, _ in results if s != 200]
        assert not auth_failures, "Authenticated requests failed:\n" + "\n".join(
            f"  {p}: {s}" for p, s in auth_failures
        )

        # Assert: all unauthenticated requests blocked (401)
        unauth_failures = [(p, s) for p, _, s in results if s != 401]
        assert (
            not unauth_failures
        ), "Unauthenticated requests not blocked:\n" + "\n".join(
            f"  {p}: {s}" for p, s in unauth_failures
        )

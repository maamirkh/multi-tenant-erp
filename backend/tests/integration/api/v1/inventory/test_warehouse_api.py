"""API integration tests for Phase 4 Warehouse Management endpoints.

Tests:
  - CRUD: create, get, list, update
  - Status transitions: deactivate, activate, archive
  - Archive guard (has_stock stub — always allows in Phase 4)
  - Location management: add, list, update
  - Tenant isolation: 404 on cross-company access
  - Unauthenticated: 401

Spec ref: specs/005-inventory-management/spec.md §16
"""

from __future__ import annotations

import uuid

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
    email = f"wh-{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"
    create_test_user(db, email=email, password=password)
    token = _login(client, email, password)
    company_id = _create_company(client, token)
    return email, password, company_id


# ---------------------------------------------------------------------------
# 401 Unauthenticated
# ---------------------------------------------------------------------------


class TestWarehouseUnauthenticated:
    def test_create_requires_auth(self, test_client: TestClient):
        resp = test_client.post(
            _url(uuid.uuid4(), "/warehouses"),
            json={"code": "WH-A", "name": "Test"},
        )
        assert resp.status_code == 401

    def test_list_requires_auth(self, test_client: TestClient):
        resp = test_client.get(_url(uuid.uuid4(), "/warehouses"))
        assert resp.status_code == 401

    def test_get_requires_auth(self, test_client: TestClient):
        resp = test_client.get(_url(uuid.uuid4(), f"/warehouses/{uuid.uuid4()}"))
        assert resp.status_code == 401

    def test_locations_requires_auth(self, test_client: TestClient):
        resp = test_client.get(
            _url(uuid.uuid4(), f"/warehouses/{uuid.uuid4()}/locations")
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Warehouse CRUD
# ---------------------------------------------------------------------------


class TestWarehouseCrud:
    def test_create_warehouse(self, test_client: TestClient, db_session: Session):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)

        resp = test_client.post(
            _url(cid, "/warehouses"),
            json={
                "code": "WH-MAIN",
                "name": "Main Warehouse",
                "warehouse_type": "MAIN",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["code"] == "WH-MAIN"
        assert data["warehouse_type"] == "MAIN"
        assert data["status"] == "ACTIVE"

    def test_create_normalises_code_to_uppercase(
        self, test_client: TestClient, db_session: Session
    ):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)

        resp = test_client.post(
            _url(cid, "/warehouses"),
            json={"code": "wh-lower", "name": "Lower Case"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["code"] == "WH-LOWER"

    def test_duplicate_code_returns_409(
        self, test_client: TestClient, db_session: Session
    ):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)

        test_client.post(
            _url(cid, "/warehouses"),
            json={"code": "WH-DUP", "name": "First"},
            headers=_auth(token),
        )
        resp = test_client.post(
            _url(cid, "/warehouses"),
            json={"code": "WH-DUP", "name": "Second"},
            headers=_auth(token),
        )
        assert resp.status_code == 409

    def test_get_warehouse(self, test_client: TestClient, db_session: Session):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)

        create_resp = test_client.post(
            _url(cid, "/warehouses"),
            json={"code": "WH-GET", "name": "Get Me"},
            headers=_auth(token),
        )
        wh_id = create_resp.json()["data"]["id"]

        resp = test_client.get(_url(cid, f"/warehouses/{wh_id}"), headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == wh_id

    def test_get_wrong_company_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        email, password, cid1 = _setup(db_session, test_client)
        token = _login(test_client, email, password)

        create_resp = test_client.post(
            _url(cid1, "/warehouses"),
            json={"code": "WH-CROSS", "name": "Cross"},
            headers=_auth(token),
        )
        wh_id = create_resp.json()["data"]["id"]

        # cid2 is a fake company_id the user is not a member of — denied either
        # at the membership gate (403) or, if it got past that, at the
        # repository's company_id scoping (404). Both are correct "access
        # denied" outcomes (see tests/security/inventory/test_security.py).
        cid2 = uuid.uuid4()
        resp = test_client.get(_url(cid2, f"/warehouses/{wh_id}"), headers=_auth(token))
        assert resp.status_code in (403, 404)

    def test_list_warehouses(self, test_client: TestClient, db_session: Session):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)

        for code in ["WH-LIST-A", "WH-LIST-B"]:
            test_client.post(
                _url(cid, "/warehouses"),
                json={"code": code, "name": code},
                headers=_auth(token),
            )

        resp = test_client.get(_url(cid, "/warehouses"), headers=_auth(token))
        assert resp.status_code == 200
        codes = {w["code"] for w in resp.json()["data"]}
        assert "WH-LIST-A" in codes
        assert "WH-LIST-B" in codes

    def test_update_warehouse(self, test_client: TestClient, db_session: Session):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)

        create_resp = test_client.post(
            _url(cid, "/warehouses"),
            json={"code": "WH-UPD", "name": "Original Name"},
            headers=_auth(token),
        )
        wh_id = create_resp.json()["data"]["id"]

        resp = test_client.patch(
            _url(cid, f"/warehouses/{wh_id}"),
            json={"name": "Updated Name", "city": "Dubai"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "Updated Name"
        assert data["city"] == "Dubai"

    def test_create_with_full_address(
        self, test_client: TestClient, db_session: Session
    ):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)

        resp = test_client.post(
            _url(cid, "/warehouses"),
            json={
                "code": "WH-ADDR",
                "name": "Full Address Warehouse",
                "warehouse_type": "BRANCH",
                "address_line1": "123 Main St",
                "city": "Dubai",
                "country_code": "AE",
                "phone": "+971501234567",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["city"] == "Dubai"
        assert data["country_code"] == "AE"
        assert data["warehouse_type"] == "BRANCH"


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


class TestWarehouseStatusTransitions:
    def _create_wh(
        self, client: TestClient, token: str, cid: uuid.UUID, code: str
    ) -> str:
        resp = client.post(
            _url(cid, "/warehouses"),
            json={"code": code, "name": code},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        return str(resp.json()["data"]["id"])

    def test_deactivate(self, test_client: TestClient, db_session: Session):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)
        wh_id = self._create_wh(test_client, token, cid, "WH-DEACT")

        resp = test_client.post(
            _url(cid, f"/warehouses/{wh_id}/deactivate"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "INACTIVE"

    def test_reactivate(self, test_client: TestClient, db_session: Session):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)
        wh_id = self._create_wh(test_client, token, cid, "WH-REACT")

        test_client.post(
            _url(cid, f"/warehouses/{wh_id}/deactivate"), headers=_auth(token)
        )

        resp = test_client.post(
            _url(cid, f"/warehouses/{wh_id}/activate"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "ACTIVE"

    def test_archive(self, test_client: TestClient, db_session: Session):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)
        wh_id = self._create_wh(test_client, token, cid, "WH-ARCH")

        # Must deactivate first
        test_client.post(
            _url(cid, f"/warehouses/{wh_id}/deactivate"), headers=_auth(token)
        )

        resp = test_client.post(
            _url(cid, f"/warehouses/{wh_id}/archive"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "ARCHIVED"

    def test_invalid_transition_returns_409(
        self, test_client: TestClient, db_session: Session
    ):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)
        wh_id = self._create_wh(test_client, token, cid, "WH-INV")

        # ACTIVE → ARCHIVED (skips INACTIVE) — not allowed
        resp = test_client.post(
            _url(cid, f"/warehouses/{wh_id}/archive"),
            headers=_auth(token),
        )
        assert resp.status_code == 409

    def test_activate_already_active_returns_409(
        self, test_client: TestClient, db_session: Session
    ):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)
        wh_id = self._create_wh(test_client, token, cid, "WH-ACTACT")

        # Already ACTIVE → ACTIVE is invalid
        resp = test_client.post(
            _url(cid, f"/warehouses/{wh_id}/activate"),
            headers=_auth(token),
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Warehouse Locations
# ---------------------------------------------------------------------------


class TestWarehouseLocations:
    def _create_wh(
        self, client: TestClient, token: str, cid: uuid.UUID, code: str
    ) -> str:
        resp = client.post(
            _url(cid, "/warehouses"),
            json={"code": code, "name": code},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        return str(resp.json()["data"]["id"])

    def test_add_location(self, test_client: TestClient, db_session: Session):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)
        wh_id = self._create_wh(test_client, token, cid, "WH-LOCA")

        resp = test_client.post(
            _url(cid, f"/warehouses/{wh_id}/locations"),
            json={
                "location_code": "A-01-01",
                "aisle": "A",
                "zone": "Z1",
                "shelf": "Top",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["location_code"] == "A-01-01"
        assert data["aisle"] == "A"
        assert data["is_active"] is True

    def test_duplicate_location_code_returns_409(
        self, test_client: TestClient, db_session: Session
    ):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)
        wh_id = self._create_wh(test_client, token, cid, "WH-LOCDUP")

        test_client.post(
            _url(cid, f"/warehouses/{wh_id}/locations"),
            json={"location_code": "B-01"},
            headers=_auth(token),
        )
        resp = test_client.post(
            _url(cid, f"/warehouses/{wh_id}/locations"),
            json={"location_code": "B-01"},
            headers=_auth(token),
        )
        assert resp.status_code == 409

    def test_list_locations(self, test_client: TestClient, db_session: Session):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)
        wh_id = self._create_wh(test_client, token, cid, "WH-LOCLIST")

        for code in ["C-01", "C-02"]:
            test_client.post(
                _url(cid, f"/warehouses/{wh_id}/locations"),
                json={"location_code": code},
                headers=_auth(token),
            )

        resp = test_client.get(
            _url(cid, f"/warehouses/{wh_id}/locations"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        codes = {loc["location_code"] for loc in resp.json()["data"]}
        assert "C-01" in codes
        assert "C-02" in codes

    def test_update_location(self, test_client: TestClient, db_session: Session):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)
        wh_id = self._create_wh(test_client, token, cid, "WH-LOCUPD")

        add_resp = test_client.post(
            _url(cid, f"/warehouses/{wh_id}/locations"),
            json={"location_code": "D-01", "aisle": "D"},
            headers=_auth(token),
        )
        loc_id = add_resp.json()["data"]["id"]

        resp = test_client.patch(
            _url(cid, f"/warehouses/{wh_id}/locations/{loc_id}"),
            json={"zone": "NewZone", "is_active": False},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["zone"] == "NewZone"
        assert data["is_active"] is False

    def test_locations_for_nonexistent_warehouse_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)

        resp = test_client.get(
            _url(cid, f"/warehouses/{uuid.uuid4()}/locations"),
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_location_code_normalised_to_uppercase(
        self, test_client: TestClient, db_session: Session
    ):
        email, password, cid = _setup(db_session, test_client)
        token = _login(test_client, email, password)
        wh_id = self._create_wh(test_client, token, cid, "WH-UPPER")

        resp = test_client.post(
            _url(cid, f"/warehouses/{wh_id}/locations"),
            json={"location_code": "e-01-lower"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["location_code"] == "E-01-LOWER"

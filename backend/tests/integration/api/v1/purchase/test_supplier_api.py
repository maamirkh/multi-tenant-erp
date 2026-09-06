"""API integration tests for Supplier endpoints — Phase 1.

Tests:
  - Unauthenticated 401 enforcement on all supplier routes
  - Supplier CRUD (create, list, get, update)
  - Supplier lifecycle transitions (activate, deactivate, block, reactivate, archive)
  - Invalid lifecycle transitions return 422
  - Blocked / non-existent supplier returns 404 or 422
  - Contact management (list, add, set-primary)
  - Address management (list, add, set-default)
  - Bulk CSV import endpoint

All tests use the FastAPI TestClient with SQLite in-memory database.

Task: T052
Spec ref: specs/006-purchase-management/tasks.md §Phase 1
"""

from __future__ import annotations

import csv
import io
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
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _url(company_id: str, path: str = "") -> str:
    return f"/api/v1/companies/{company_id}/purchase/suppliers{path}"


def _create_company(client: TestClient, token: str) -> str:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Purchase Test Co {suffix}",
            "email": f"contact-{suffix}@purchase-test.example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _create_supplier(
    client: TestClient,
    token: str,
    company_id: str,
    *,
    code: str = "SUP-001",
    legal_name: str = "Acme Corp",
) -> dict:
    resp = client.post(
        _url(company_id),
        json={"supplier_code": code, "legal_name": legal_name},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# Unauthenticated access
# ---------------------------------------------------------------------------


class TestSupplierUnauthenticated:
    def test_list_requires_auth(self, test_client: TestClient) -> None:
        cid = str(uuid.uuid4())
        resp = test_client.get(_url(cid))
        assert resp.status_code == 401

    def test_create_requires_auth(self, test_client: TestClient) -> None:
        cid = str(uuid.uuid4())
        resp = test_client.post(
            _url(cid), json={"supplier_code": "X", "legal_name": "Y"}
        )
        assert resp.status_code == 401

    def test_get_requires_auth(self, test_client: TestClient) -> None:
        cid = str(uuid.uuid4())
        resp = test_client.get(_url(cid, f"/{uuid.uuid4()}"))
        assert resp.status_code == 401

    def test_update_requires_auth(self, test_client: TestClient) -> None:
        cid = str(uuid.uuid4())
        resp = test_client.put(
            _url(cid, f"/{uuid.uuid4()}"),
            json={"legal_name": "New Name"},
        )
        assert resp.status_code == 401

    def test_activate_requires_auth(self, test_client: TestClient) -> None:
        cid = str(uuid.uuid4())
        resp = test_client.post(_url(cid, f"/{uuid.uuid4()}/activate"), json={})
        assert resp.status_code == 401

    def test_import_requires_auth(self, test_client: TestClient) -> None:
        cid = str(uuid.uuid4())
        resp = test_client.post(
            _url(cid, "/import"), files={"file": b"supplier_code,legal_name"}
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Supplier CRUD
# ---------------------------------------------------------------------------


class TestSupplierCRUD:
    def test_create_supplier_returns_201(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_create_201@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        resp = test_client.post(
            _url(cid),
            json={"supplier_code": "SUP-001", "legal_name": "Acme Corp"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["supplier_code"] == "SUP-001"
        assert data["legal_name"] == "Acme Corp"
        assert data["status"] == "DRAFT"

    def test_create_supplier_with_all_fields(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_create_full@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        resp = test_client.post(
            _url(cid),
            json={
                "supplier_code": "SUP-002",
                "legal_name": "Beta Supplies Ltd",
                "trading_name": "BetaSupply",
                "supplier_type": "SERVICES",
                "currency_code": "GBP",
                "website": "https://betasupply.com",
                "lead_time_days": 14,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["supplier_type"] == "SERVICES"
        assert data["currency_code"] == "GBP"
        assert data["lead_time_days"] == 14

    def test_create_duplicate_code_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_dup_code@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        test_client.post(
            _url(cid),
            json={"supplier_code": "SUP-DUP", "legal_name": "First"},
            headers=_auth(token),
        )
        resp = test_client.post(
            _url(cid),
            json={"supplier_code": "SUP-DUP", "legal_name": "Second"},
            headers=_auth(token),
        )
        assert resp.status_code == 409

    def test_list_suppliers_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_list_200@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        _create_supplier(test_client, token, cid, code="S-L1", legal_name="Alpha")
        _create_supplier(test_client, token, cid, code="S-L2", legal_name="Beta")

        resp = test_client.get(_url(cid), headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2

    def test_list_supports_status_filter(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_list_filter@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        s = _create_supplier(
            test_client, token, cid, code="S-ACT", legal_name="Active Co"
        )
        _create_supplier(test_client, token, cid, code="S-DRF", legal_name="Draft Co")

        # Activate one supplier
        test_client.post(
            _url(cid, f"/{s['id']}/activate"),
            json={},
            headers=_auth(token),
        )

        resp = test_client.get(_url(cid, "?status=ACTIVE"), headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert all(s["status"] == "ACTIVE" for s in data)

    def test_get_supplier_by_id(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_get_by_id@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        created = _create_supplier(test_client, token, cid, code="S-GET")
        sid = created["id"]

        resp = test_client.get(_url(cid, f"/{sid}"), headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == sid

    def test_get_nonexistent_supplier_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_get_404@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        resp = test_client.get(_url(cid, f"/{uuid.uuid4()}"), headers=_auth(token))
        assert resp.status_code == 404

    def test_update_supplier(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_update@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        created = _create_supplier(test_client, token, cid, code="S-UPD")
        sid = created["id"]

        resp = test_client.put(
            _url(cid, f"/{sid}"),
            json={"legal_name": "Updated Corp", "website": "https://updated.com"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["legal_name"] == "Updated Corp"
        assert data["website"] == "https://updated.com"

    def test_update_nonexistent_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_upd_404@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        resp = test_client.put(
            _url(cid, f"/{uuid.uuid4()}"),
            json={"legal_name": "X"},
            headers=_auth(token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Supplier lifecycle transitions
# ---------------------------------------------------------------------------


class TestSupplierLifecycle:
    def test_activate_draft_supplier(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_activate@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        supplier = _create_supplier(test_client, token, cid, code="S-ACT")
        sid = supplier["id"]

        resp = test_client.post(
            _url(cid, f"/{sid}/activate"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "ACTIVE"

    def test_deactivate_active_supplier(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_deactivate@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        supplier = _create_supplier(test_client, token, cid, code="S-DEACT")
        sid = supplier["id"]

        test_client.post(_url(cid, f"/{sid}/activate"), json={}, headers=_auth(token))

        resp = test_client.post(
            _url(cid, f"/{sid}/deactivate"),
            json={"reason": "Temporarily offline"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "INACTIVE"

    def test_block_active_supplier(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_block@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        supplier = _create_supplier(test_client, token, cid, code="S-BLK")
        sid = supplier["id"]

        test_client.post(_url(cid, f"/{sid}/activate"), json={}, headers=_auth(token))

        resp = test_client.post(
            _url(cid, f"/{sid}/block"),
            json={"reason": "Compliance violation"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "BLOCKED"

    def test_reactivate_blocked_supplier(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_reactivate@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        supplier = _create_supplier(test_client, token, cid, code="S-REACT")
        sid = supplier["id"]

        test_client.post(_url(cid, f"/{sid}/activate"), json={}, headers=_auth(token))
        test_client.post(
            _url(cid, f"/{sid}/block"), json={"reason": "Fraud"}, headers=_auth(token)
        )

        resp = test_client.post(
            _url(cid, f"/{sid}/reactivate"),
            json={"reason": "Issue resolved"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "ACTIVE"

    def test_archive_active_supplier(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_archive@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        supplier = _create_supplier(test_client, token, cid, code="S-ARC")
        sid = supplier["id"]

        test_client.post(_url(cid, f"/{sid}/activate"), json={}, headers=_auth(token))

        resp = test_client.post(
            _url(cid, f"/{sid}/archive"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "ARCHIVED"

    def test_invalid_transition_draft_to_blocked_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_inv_trans@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        supplier = _create_supplier(test_client, token, cid, code="S-INVT")
        sid = supplier["id"]

        # DRAFT → BLOCKED is invalid
        resp = test_client.post(
            _url(cid, f"/{sid}/block"),
            json={"reason": "Not allowed from DRAFT"},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_activate_nonexistent_supplier_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_act_404@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        resp = test_client.post(
            _url(cid, f"/{uuid.uuid4()}/activate"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_archived_supplier_cannot_be_activated(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_arc_act@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        supplier = _create_supplier(test_client, token, cid, code="S-ARCE")
        sid = supplier["id"]

        test_client.post(_url(cid, f"/{sid}/activate"), json={}, headers=_auth(token))
        test_client.post(_url(cid, f"/{sid}/archive"), json={}, headers=_auth(token))

        # Try to activate an ARCHIVED supplier — should fail (terminal state)
        resp = test_client.post(
            _url(cid, f"/{sid}/activate"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Supplier contact management
# ---------------------------------------------------------------------------


class TestSupplierContacts:
    def test_list_contacts_empty(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_contacts_empty@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        supplier = _create_supplier(test_client, token, cid, code="S-CON0")
        sid = supplier["id"]

        resp = test_client.get(_url(cid, f"/{sid}/contacts"), headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_add_contact(self, test_client: TestClient, db_session: Session) -> None:
        user, pw = create_test_user(db_session, email="sup_add_contact@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        supplier = _create_supplier(test_client, token, cid, code="S-CONADD")
        sid = supplier["id"]

        resp = test_client.post(
            _url(cid, f"/{sid}/contacts"),
            json={
                "first_name": "Alice",
                "last_name": "Smith",
                "role": "Accounts",
                "email": "alice@acme.com",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["first_name"] == "Alice"
        assert data["last_name"] == "Smith"

    def test_add_multiple_contacts_and_list(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_contacts_list@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        supplier = _create_supplier(test_client, token, cid, code="S-CONLST")
        sid = supplier["id"]

        test_client.post(
            _url(cid, f"/{sid}/contacts"),
            json={"first_name": "Alice", "last_name": "A"},
            headers=_auth(token),
        )
        test_client.post(
            _url(cid, f"/{sid}/contacts"),
            json={"first_name": "Bob", "last_name": "B"},
            headers=_auth(token),
        )

        resp = test_client.get(_url(cid, f"/{sid}/contacts"), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2

    def test_set_primary_contact(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_set_primary@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        supplier = _create_supplier(test_client, token, cid, code="S-PRIM")
        sid = supplier["id"]

        c1 = test_client.post(
            _url(cid, f"/{sid}/contacts"),
            json={"first_name": "Alice", "last_name": "A"},
            headers=_auth(token),
        ).json()["data"]

        resp = test_client.post(
            _url(cid, f"/{sid}/contacts/{c1['id']}/set-primary"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_primary"] is True


# ---------------------------------------------------------------------------
# Supplier address management
# ---------------------------------------------------------------------------


class TestSupplierAddresses:
    def test_list_addresses_empty(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_addr_empty@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        supplier = _create_supplier(test_client, token, cid, code="S-ADDR0")
        sid = supplier["id"]

        resp = test_client.get(_url(cid, f"/{sid}/addresses"), headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_add_address(self, test_client: TestClient, db_session: Session) -> None:
        user, pw = create_test_user(db_session, email="sup_add_addr@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        supplier = _create_supplier(test_client, token, cid, code="S-ADDRADD")
        sid = supplier["id"]

        resp = test_client.post(
            _url(cid, f"/{sid}/addresses"),
            json={
                "address_type": "BILLING",
                "address_line_1": "123 Main St",
                "city": "New York",
                "country_code": "US",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["city"] == "New York"
        assert data["address_type"] == "BILLING"

    def test_set_default_address(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_def_addr@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        supplier = _create_supplier(test_client, token, cid, code="S-DEFADDR")
        sid = supplier["id"]

        addr = test_client.post(
            _url(cid, f"/{sid}/addresses"),
            json={
                "address_type": "SHIPPING",
                "address_line_1": "456 Oak Ave",
                "city": "Chicago",
                "country_code": "US",
            },
            headers=_auth(token),
        ).json()["data"]

        resp = test_client.post(
            _url(cid, f"/{sid}/addresses/{addr['id']}/set-default"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_default"] is True


# ---------------------------------------------------------------------------
# Bulk CSV import
# ---------------------------------------------------------------------------


class TestSupplierBulkImport:
    def _build_csv(self, rows: list[dict]) -> bytes:
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=["supplier_code", "legal_name", "trading_name", "supplier_type"],
        )
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8")

    def test_import_valid_csv(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_import_ok@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        csv_bytes = self._build_csv(
            [
                {
                    "supplier_code": "IMP-001",
                    "legal_name": "Import One",
                    "trading_name": "",
                    "supplier_type": "GOODS",
                },
                {
                    "supplier_code": "IMP-002",
                    "legal_name": "Import Two",
                    "trading_name": "ImpTwo",
                    "supplier_type": "SERVICES",
                },
            ]
        )

        resp = test_client.post(
            _url(cid, "/import"),
            files={"file": ("suppliers.csv", csv_bytes, "text/csv")},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        result = resp.json()["data"]
        assert result["total_rows"] == 2
        assert result["created"] == 2
        assert result["failed"] == 0

    def test_import_missing_required_field_collects_error(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_import_err@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        # Missing legal_name on row 2
        csv_bytes = b"supplier_code,legal_name\nIMPE-001,Good Co\nIMPE-002,\n"

        resp = test_client.post(
            _url(cid, "/import"),
            files={"file": ("suppliers.csv", csv_bytes, "text/csv")},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        result = resp.json()["data"]
        assert result["total_rows"] == 2
        assert result["created"] == 1
        assert result["failed"] == 1
        assert len(result["errors"]) == 1

    def test_import_duplicate_code_in_csv_skipped(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_import_dup@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        # First create a supplier with the same code
        _create_supplier(
            test_client, token, cid, code="DUPCHECK-01", legal_name="Existing"
        )

        csv_bytes = (
            b"supplier_code,legal_name\nDUPCHECK-01,Duplicate\nDUPCHECK-02,New One\n"
        )

        resp = test_client.post(
            _url(cid, "/import"),
            files={"file": ("suppliers.csv", csv_bytes, "text/csv")},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        result = resp.json()["data"]
        # DUPCHECK-01 skipped, DUPCHECK-02 created
        assert result["created"] == 1
        assert result["skipped"] + result["failed"] >= 1

    def test_import_empty_csv_returns_zero_rows(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_import_empty@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)

        csv_bytes = b"supplier_code,legal_name\n"

        resp = test_client.post(
            _url(cid, "/import"),
            files={"file": ("suppliers.csv", csv_bytes, "text/csv")},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        result = resp.json()["data"]
        assert result["total_rows"] == 0
        assert result["created"] == 0


# ---------------------------------------------------------------------------
# Tenant isolation at API level
# ---------------------------------------------------------------------------


class TestSupplierTenantIsolation:
    def test_company_a_cannot_see_company_b_supplier(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_iso_a@example.com")
        token = _login(test_client, user.email, pw)
        cid_a = _create_company(test_client, token)
        cid_b = _create_company(test_client, token)

        # Create supplier under company B
        sup_b = _create_supplier(
            test_client, token, cid_b, code="SUP-B1", legal_name="B Corp"
        )

        # Try to fetch it under company A
        resp = test_client.get(
            _url(cid_a, f"/{sup_b['id']}"),
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_company_a_list_does_not_include_company_b(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="sup_iso_list@example.com")
        token = _login(test_client, user.email, pw)
        cid_a = _create_company(test_client, token)
        cid_b = _create_company(test_client, token)

        _create_supplier(
            test_client, token, cid_a, code="SUP-A1", legal_name="Company A Supplier"
        )
        _create_supplier(
            test_client, token, cid_b, code="SUP-B1", legal_name="Company B Supplier"
        )

        resp = test_client.get(_url(cid_a), headers=_auth(token))
        data = resp.json()["data"]
        legal_names = [s["legal_name"] for s in data]
        assert "Company A Supplier" in legal_names
        assert "Company B Supplier" not in legal_names

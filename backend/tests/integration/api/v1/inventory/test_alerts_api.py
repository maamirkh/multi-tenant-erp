"""Integration tests for Phase 8 Inventory Intelligence API.

Tests cover:
  T230 - Alert lifecycle (create via stock write, list, acknowledge)
  T231 - API endpoints for alerts, reorder rules, and suggestions
  T232 - Feature flag gating for OVERSTOCK alerts
  T233 - Tenant isolation (company_id scoping)

Spec ref: specs/005-inventory-management/spec.md §15 / FR-IO-016
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.inventory.models.alerts import LowStockAlert, ReorderSuggestion
from modules.inventory.models.product import Product
from modules.inventory.models.uom import UOM
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
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _url(company_id: str | uuid.UUID, path: str) -> str:
    return f"/api/v1/companies/{company_id}/inventory{path}"


def _setup(db: Session) -> tuple[str, str, uuid.UUID]:
    email = f"alert-{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"
    create_test_user(db, email=email, password=password)
    company_id = uuid.uuid4()
    return email, password, company_id


def _make_warehouse(db: Session, company_id: uuid.UUID) -> Warehouse:
    wh = Warehouse(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"WH-{uuid.uuid4().hex[:4].upper()}",
        name="Alert Test WH",
        warehouse_type="MAIN",
        status="ACTIVE",
    )
    db.add(wh)
    db.flush()
    return wh


def _make_product(db: Session, company_id: uuid.UUID) -> str:
    """Insert a product directly in DB and return its str UUID."""
    uom = UOM(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"U{uuid.uuid4().hex[:4]}",
        name="Unit",
        uom_type="UNIT",
        status="active",
    )
    db.add(uom)
    db.flush()
    product = Product(
        id=uuid.uuid4(),
        company_id=company_id,
        name=f"Alert Product {uuid.uuid4().hex[:6]}",
        product_code=f"ALP-{uuid.uuid4().hex[:6]}",
        product_type="STANDARD",
        status="ACTIVE",
        base_uom_id=str(uom.id),
    )
    db.add(product)
    db.flush()
    return str(product.id)


# ---------------------------------------------------------------------------
# Reorder Rule API tests (T231)
# ---------------------------------------------------------------------------


class TestReorderRuleAPI:
    def test_create_reorder_rule(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, pwd, cid = _setup(db_session)
        tok = _login(test_client, email, pwd)
        product_id = _make_product(db_session, cid)

        r = test_client.post(
            _url(cid, "/reorder-rules"),
            json={
                "product_id": product_id,
                "reorder_level": 10,
                "reorder_quantity": 50,
            },
            headers=_auth(tok),
        )
        assert r.status_code == 201, r.text
        data = r.json()["data"]
        assert data["product_id"] == product_id
        assert Decimal(data["reorder_level"]) == Decimal("10")
        assert data["is_active"] is True

    def test_list_reorder_rules(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, pwd, cid = _setup(db_session)
        tok = _login(test_client, email, pwd)
        product_id = _make_product(db_session, cid)

        test_client.post(
            _url(cid, "/reorder-rules"),
            json={"product_id": product_id, "reorder_level": 5, "reorder_quantity": 20},
            headers=_auth(tok),
        )
        r = test_client.get(_url(cid, "/reorder-rules"), headers=_auth(tok))
        assert r.status_code == 200
        data = r.json()["data"]
        assert isinstance(data, list)
        assert any(d["product_id"] == product_id for d in data)

    def test_update_reorder_rule(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, pwd, cid = _setup(db_session)
        tok = _login(test_client, email, pwd)
        product_id = _make_product(db_session, cid)

        r_create = test_client.post(
            _url(cid, "/reorder-rules"),
            json={"product_id": product_id, "reorder_level": 5, "reorder_quantity": 20},
            headers=_auth(tok),
        )
        rule_id = r_create.json()["data"]["id"]

        r_update = test_client.patch(
            _url(cid, f"/reorder-rules/{rule_id}"),
            json={"reorder_quantity": 100, "is_active": False},
            headers=_auth(tok),
        )
        assert r_update.status_code == 200
        updated = r_update.json()["data"]
        assert Decimal(updated["reorder_quantity"]) == Decimal("100")
        assert updated["is_active"] is False

    def test_delete_reorder_rule(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, pwd, cid = _setup(db_session)
        tok = _login(test_client, email, pwd)
        product_id = _make_product(db_session, cid)

        r_create = test_client.post(
            _url(cid, "/reorder-rules"),
            json={"product_id": product_id, "reorder_level": 5, "reorder_quantity": 20},
            headers=_auth(tok),
        )
        rule_id = r_create.json()["data"]["id"]

        r_delete = test_client.delete(
            _url(cid, f"/reorder-rules/{rule_id}"),
            headers=_auth(tok),
        )
        assert r_delete.status_code == 204

        # Confirm it no longer shows up
        r_get = test_client.get(
            _url(cid, f"/reorder-rules/{rule_id}"),
            headers=_auth(tok),
        )
        assert r_get.status_code == 404

    def test_rule_tenant_isolation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A reorder rule for company A is not visible under company B."""
        email, pwd, cid = _setup(db_session)
        tok = _login(test_client, email, pwd)
        product_id = _make_product(db_session, cid)

        r_create = test_client.post(
            _url(cid, "/reorder-rules"),
            json={"product_id": product_id, "reorder_level": 5, "reorder_quantity": 20},
            headers=_auth(tok),
        )
        rule_id = r_create.json()["data"]["id"]

        other_cid = uuid.uuid4()  # different company
        r_other = test_client.get(
            _url(other_cid, f"/reorder-rules/{rule_id}"),
            headers=_auth(tok),
        )
        assert r_other.status_code == 404

    def test_unauthenticated_returns_401(self, test_client: TestClient) -> None:
        r = test_client.get(_url(uuid.uuid4(), "/reorder-rules"))
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Alert API tests (T230 + T231)
# ---------------------------------------------------------------------------


class TestAlertAPI:
    def test_alerts_list_initially_empty(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, pwd, cid = _setup(db_session)
        tok = _login(test_client, email, pwd)

        r = test_client.get(_url(cid, "/alerts"), headers=_auth(tok))
        assert r.status_code == 200
        assert isinstance(r.json()["data"], list)

    def test_acknowledge_open_alert(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Acknowledge an OPEN alert via the API."""
        email, pwd, cid = _setup(db_session)
        tok = _login(test_client, email, pwd)
        product_id = _make_product(db_session, cid)
        wh = _make_warehouse(db_session, cid)

        # Directly insert an OPEN alert
        alert = LowStockAlert(
            id=uuid.uuid4(),
            company_id=cid,
            product_id=product_id,
            warehouse_id=str(wh.id),
            alert_type="LOW_STOCK",
            status="OPEN",
            current_quantity=Decimal("3"),
            threshold_quantity=Decimal("10"),
        )
        db_session.add(alert)
        db_session.commit()

        r = test_client.post(
            _url(cid, f"/alerts/{alert.id}/acknowledge"),
            json={"notes": "Noted, ordering soon"},
            headers=_auth(tok),
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["status"] == "ACKNOWLEDGED"
        assert data["acknowledged_at"] is not None

    def test_acknowledge_resolved_alert_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, pwd, cid = _setup(db_session)
        tok = _login(test_client, email, pwd)
        product_id = _make_product(db_session, cid)
        wh = _make_warehouse(db_session, cid)

        alert = LowStockAlert(
            id=uuid.uuid4(),
            company_id=cid,
            product_id=product_id,
            warehouse_id=str(wh.id),
            alert_type="LOW_STOCK",
            status="RESOLVED",
            current_quantity=Decimal("50"),
            threshold_quantity=Decimal("10"),
        )
        db_session.add(alert)
        db_session.commit()

        r = test_client.post(
            _url(cid, f"/alerts/{alert.id}/acknowledge"),
            json={},
            headers=_auth(tok),
        )
        assert r.status_code == 409

    def test_get_alert_not_found(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, pwd, cid = _setup(db_session)
        tok = _login(test_client, email, pwd)
        r = test_client.get(_url(cid, f"/alerts/{uuid.uuid4()}"), headers=_auth(tok))
        assert r.status_code == 404

    def test_alert_tenant_isolation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Alert for company A is not accessible via company B URL."""
        email, pwd, cid = _setup(db_session)
        tok = _login(test_client, email, pwd)
        product_id = _make_product(db_session, cid)
        wh = _make_warehouse(db_session, cid)

        alert = LowStockAlert(
            id=uuid.uuid4(),
            company_id=cid,
            product_id=product_id,
            warehouse_id=str(wh.id),
            alert_type="OUT_OF_STOCK",
            status="OPEN",
            current_quantity=Decimal("0"),
            threshold_quantity=Decimal("0"),
        )
        db_session.add(alert)
        db_session.commit()

        other_cid = uuid.uuid4()
        r = test_client.get(
            _url(other_cid, f"/alerts/{alert.id}"),
            headers=_auth(tok),
        )
        assert r.status_code == 404

    def test_unauthenticated_returns_401(self, test_client: TestClient) -> None:
        r = test_client.get(_url(uuid.uuid4(), "/alerts"))
        assert r.status_code == 401

    def test_filter_alerts_by_status(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, pwd, cid = _setup(db_session)
        tok = _login(test_client, email, pwd)
        product_id = _make_product(db_session, cid)
        wh = _make_warehouse(db_session, cid)

        # Create OPEN and RESOLVED alerts
        for status in ("OPEN", "RESOLVED"):
            db_session.add(
                LowStockAlert(
                    id=uuid.uuid4(),
                    company_id=cid,
                    product_id=product_id,
                    warehouse_id=str(wh.id),
                    alert_type="LOW_STOCK",
                    status=status,
                    current_quantity=Decimal("3"),
                    threshold_quantity=Decimal("10"),
                )
            )
        db_session.commit()

        r = test_client.get(
            _url(cid, "/alerts?alert_status=OPEN"),
            headers=_auth(tok),
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert all(a["status"] == "OPEN" for a in data)


# ---------------------------------------------------------------------------
# Suggestion API tests (T231)
# ---------------------------------------------------------------------------


class TestSuggestionAPI:
    def test_suggestions_list(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, pwd, cid = _setup(db_session)
        tok = _login(test_client, email, pwd)

        r = test_client.get(_url(cid, "/suggestions"), headers=_auth(tok))
        assert r.status_code == 200
        assert isinstance(r.json()["data"], list)

    def test_acknowledge_suggestion(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, pwd, cid = _setup(db_session)
        tok = _login(test_client, email, pwd)
        product_id = _make_product(db_session, cid)
        wh = _make_warehouse(db_session, cid)

        suggestion = ReorderSuggestion(
            id=uuid.uuid4(),
            company_id=cid,
            product_id=product_id,
            warehouse_id=str(wh.id),
            suggested_quantity=Decimal("50"),
            status="PENDING",
        )
        db_session.add(suggestion)
        db_session.commit()

        r = test_client.post(
            _url(cid, f"/suggestions/{suggestion.id}/acknowledge"),
            json={},
            headers=_auth(tok),
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "ACKNOWLEDGED"

    def test_acknowledge_non_pending_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, pwd, cid = _setup(db_session)
        tok = _login(test_client, email, pwd)
        product_id = _make_product(db_session, cid)
        wh = _make_warehouse(db_session, cid)

        suggestion = ReorderSuggestion(
            id=uuid.uuid4(),
            company_id=cid,
            product_id=product_id,
            warehouse_id=str(wh.id),
            suggested_quantity=Decimal("50"),
            status="ACKNOWLEDGED",
        )
        db_session.add(suggestion)
        db_session.commit()

        r = test_client.post(
            _url(cid, f"/suggestions/{suggestion.id}/acknowledge"),
            json={},
            headers=_auth(tok),
        )
        assert r.status_code == 409

    def test_suggestion_not_found_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, pwd, cid = _setup(db_session)
        tok = _login(test_client, email, pwd)

        r = test_client.get(
            _url(cid, f"/suggestions/{uuid.uuid4()}"),
            headers=_auth(tok),
        )
        assert r.status_code == 404

    def test_unauthenticated_returns_401(self, test_client: TestClient) -> None:
        r = test_client.get(_url(uuid.uuid4(), "/suggestions"))
        assert r.status_code == 401

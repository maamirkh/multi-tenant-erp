"""API integration tests for Pricing endpoints — Phase 2.

Tests:
  - POST /price-lists — create price list
  - GET  /price-lists — list price lists
  - GET  /price-lists/{id} — get price list
  - PUT  /price-lists/{id} — update price list
  - DELETE /price-lists/{id} — delete price list
  - POST /price-lists/{id}/entries — add entry
  - PUT  /price-lists/{id}/entries/{eid} — update entry
  - DELETE /price-lists/{id}/entries/{eid} — delete entry
  - POST /customer-prices — create customer-specific price
  - GET  /customer-prices — list customer-specific prices
  - DELETE /customer-prices/{id} — delete customer-specific price
  - POST /discount-rules — create discount rule
  - GET  /discount-rules — list discount rules
  - DELETE /discount-rules/{id} — delete discount rule
  - POST /pricing/resolve — resolve price (7-level hierarchy)
  - POST /pricing/check-margin — margin guard check
  - 409 on duplicate price list name
  - Tenant isolation: company A cannot see company B data

Task: T081
"""

from __future__ import annotations

from uuid import uuid4

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


def _url(company_id: str, path: str) -> str:
    return f"/api/v1/companies/{company_id}/sales{path}"


def _create_price_list(
    client: TestClient,
    company_id: str,
    token: str,
    name: str = "Standard",
    is_default: bool = False,
    priority: int = 0,
) -> dict:
    resp = client.post(
        _url(company_id, "/price-lists"),
        json={
            "name": name,
            "currency_code": "USD",
            "effective_from": "2026-01-01",
            "is_default": is_default,
            "priority": priority,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# Price List CRUD
# ---------------------------------------------------------------------------


class TestPriceListCRUD:
    def test_create_price_list_success(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        resp = test_client.post(
            _url(company_id, "/price-lists"),
            json={
                "name": "Premium List",
                "currency_code": "USD",
                "effective_from": "2026-01-01",
                "priority": 10,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["name"] == "Premium List"
        assert data["currency_code"] == "USD"
        assert data["priority"] == 10

    def test_create_price_list_duplicate_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        _create_price_list(test_client, company_id, token, name="Duplicate")

        resp = test_client.post(
            _url(company_id, "/price-lists"),
            json={
                "name": "Duplicate",
                "currency_code": "USD",
                "effective_from": "2026-01-01",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 409

    def test_list_price_lists_returns_created_list(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        _create_price_list(test_client, company_id, token, name="List A")
        _create_price_list(test_client, company_id, token, name="List B")

        resp = test_client.get(_url(company_id, "/price-lists"), headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        names = [pl["name"] for pl in data]
        assert "List A" in names
        assert "List B" in names

    def test_get_price_list_by_id(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        created = _create_price_list(test_client, company_id, token, name="Get Me")

        resp = test_client.get(
            _url(company_id, f"/price-lists/{created['id']}"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Get Me"

    def test_get_price_list_not_found_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        resp = test_client.get(
            _url(company_id, f"/price-lists/{uuid4()}"), headers=_auth(token)
        )
        assert resp.status_code == 404

    def test_update_price_list(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        created = _create_price_list(test_client, company_id, token, name="Original")

        resp = test_client.put(
            _url(company_id, f"/price-lists/{created['id']}"),
            json={"priority": 50},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["priority"] == 50

    def test_delete_price_list(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        created = _create_price_list(test_client, company_id, token, name="To Delete")

        resp = test_client.delete(
            _url(company_id, f"/price-lists/{created['id']}"), headers=_auth(token)
        )
        assert resp.status_code == 204

        # Should not be findable
        get_resp = test_client.get(
            _url(company_id, f"/price-lists/{created['id']}"), headers=_auth(token)
        )
        assert get_resp.status_code == 404

    def test_unauthenticated_request_returns_401(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = str(uuid4())
        resp = test_client.get(_url(company_id, "/price-lists"))
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Price Entries
# ---------------------------------------------------------------------------


class TestPriceEntryEndpoints:
    def test_add_entry_to_price_list(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        pl = _create_price_list(test_client, company_id, token, name="Entry Test")
        product_id = str(uuid4())

        resp = test_client.post(
            _url(company_id, f"/price-lists/{pl['id']}/entries"),
            json={
                "product_id": product_id,
                "unit_price": "49.99",
                "minimum_quantity": "1",
                "unit_of_measure": "EA",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["unit_price"] == "49.9900"
        assert data["product_id"] == product_id

    def test_update_price_entry(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        pl = _create_price_list(
            test_client, company_id, token, name="Update Entry Test"
        )
        product_id = str(uuid4())

        entry_resp = test_client.post(
            _url(company_id, f"/price-lists/{pl['id']}/entries"),
            json={
                "product_id": product_id,
                "unit_price": "100.00",
                "unit_of_measure": "EA",
            },
            headers=_auth(token),
        )
        entry_id = entry_resp.json()["data"]["id"]

        resp = test_client.put(
            _url(company_id, f"/price-lists/{pl['id']}/entries/{entry_id}"),
            json={"unit_price": "85.00"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["unit_price"] == "85.0000"

    def test_delete_price_entry(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        pl = _create_price_list(
            test_client, company_id, token, name="Delete Entry Test"
        )
        product_id = str(uuid4())

        entry_resp = test_client.post(
            _url(company_id, f"/price-lists/{pl['id']}/entries"),
            json={
                "product_id": product_id,
                "unit_price": "100.00",
                "unit_of_measure": "EA",
            },
            headers=_auth(token),
        )
        entry_id = entry_resp.json()["data"]["id"]

        resp = test_client.delete(
            _url(company_id, f"/price-lists/{pl['id']}/entries/{entry_id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Customer-Specific Prices
# ---------------------------------------------------------------------------


class TestCustomerSpecificPriceEndpoints:
    def test_create_customer_price(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())
        customer_id = str(uuid4())
        product_id = str(uuid4())

        resp = test_client.post(
            _url(company_id, "/customer-prices"),
            json={
                "customer_id": customer_id,
                "product_id": product_id,
                "unit_price": "75.00",
                "effective_from": "2026-01-01",
                "minimum_quantity": "1",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["customer_id"] == customer_id
        assert data["unit_price"] == "75.0000"

    def test_list_customer_prices(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())
        customer_id = str(uuid4())

        test_client.post(
            _url(company_id, "/customer-prices"),
            json={
                "customer_id": customer_id,
                "product_id": str(uuid4()),
                "unit_price": "50.00",
                "effective_from": "2026-01-01",
            },
            headers=_auth(token),
        )

        resp = test_client.get(
            _url(company_id, "/customer-prices"),
            headers=_auth(token),
        )
        assert resp.status_code == 200

    def test_delete_customer_price(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        create_resp = test_client.post(
            _url(company_id, "/customer-prices"),
            json={
                "customer_id": str(uuid4()),
                "product_id": str(uuid4()),
                "unit_price": "60.00",
                "effective_from": "2026-01-01",
            },
            headers=_auth(token),
        )
        price_id = create_resp.json()["data"]["id"]

        resp = test_client.delete(
            _url(company_id, f"/customer-prices/{price_id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Discount Rules
# ---------------------------------------------------------------------------


class TestDiscountRuleEndpoints:
    def test_create_discount_rule(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        resp = test_client.post(
            _url(company_id, "/discount-rules"),
            json={
                "name": "Summer Sale 10%",
                "rule_type": "PERCENTAGE",
                "discount_value": "10.00",
                "effective_from": "2026-06-01",
                "applicability": "ALL_CUSTOMERS",
                "product_scope": "ALL_PRODUCTS",
                "priority": 5,
                "is_stackable": False,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["name"] == "Summer Sale 10%"
        assert data["rule_type"] == "PERCENTAGE"

    def test_list_discount_rules(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        test_client.post(
            _url(company_id, "/discount-rules"),
            json={
                "name": "VIP Discount",
                "rule_type": "PERCENTAGE",
                "discount_value": "15.00",
                "effective_from": "2026-01-01",
            },
            headers=_auth(token),
        )

        resp = test_client.get(
            _url(company_id, "/discount-rules"), headers=_auth(token)
        )
        assert resp.status_code == 200

    def test_update_discount_rule(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        create_resp = test_client.post(
            _url(company_id, "/discount-rules"),
            json={
                "name": "Update Me",
                "rule_type": "PERCENTAGE",
                "discount_value": "5.00",
                "effective_from": "2026-01-01",
            },
            headers=_auth(token),
        )
        rule_id = create_resp.json()["data"]["id"]

        resp = test_client.put(
            _url(company_id, f"/discount-rules/{rule_id}"),
            json={"priority": 20},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["priority"] == 20

    def test_delete_discount_rule(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        create_resp = test_client.post(
            _url(company_id, "/discount-rules"),
            json={
                "name": "Delete Me",
                "rule_type": "FIXED_AMOUNT",
                "discount_value": "5.00",
                "effective_from": "2026-01-01",
            },
            headers=_auth(token),
        )
        rule_id = create_resp.json()["data"]["id"]

        resp = test_client.delete(
            _url(company_id, f"/discount-rules/{rule_id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Pricing Resolution Endpoint
# ---------------------------------------------------------------------------


class TestPricingResolveEndpoint:
    def test_resolve_returns_base_price_when_no_lists(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        resp = test_client.post(
            _url(company_id, "/pricing/resolve"),
            json={
                "product_id": str(uuid4()),
                "quantity": "1",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["price_source"] == "BASE_PRICE"
        assert data["resolution_level"] == 7

    def test_resolve_with_manual_price_returns_level_1(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        resp = test_client.post(
            _url(company_id, "/pricing/resolve"),
            json={
                "product_id": str(uuid4()),
                "quantity": "5",
                "manual_price": "99.99",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["price_source"] == "MANUAL"
        assert data["resolution_level"] == 1
        # manual_price is not stored via DB, so precision comes back as-is
        assert data["unit_price"].startswith("99.99")

    def test_resolve_with_default_price_list_returns_level_6(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())
        product_id = str(uuid4())

        # Create a default price list
        pl = _create_price_list(
            test_client, company_id, token, name="Default List", is_default=True
        )

        # Add a price entry
        test_client.post(
            _url(company_id, f"/price-lists/{pl['id']}/entries"),
            json={
                "product_id": product_id,
                "unit_price": "55.00",
                "minimum_quantity": "1",
                "unit_of_measure": "EA",
            },
            headers=_auth(token),
        )

        resp = test_client.post(
            _url(company_id, "/pricing/resolve"),
            json={"product_id": product_id, "quantity": "1"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["price_source"] == "DEFAULT_LIST"
        assert data["resolution_level"] == 6
        assert data["unit_price"] == "55.0000"


# ---------------------------------------------------------------------------
# Margin Guard Endpoint
# ---------------------------------------------------------------------------


class TestMarginCheckEndpoint:
    def test_margin_ok_when_above_threshold(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        resp = test_client.post(
            _url(company_id, "/pricing/check-margin"),
            json={
                "unit_price": "100.00",
                "cost_price": "70.00",
                "min_margin_pct": "20.00",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["action"] == "OK"
        assert data["passes"] is True
        assert data["margin_percentage"] == "30.00"

    def test_margin_warn_when_below_threshold(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        resp = test_client.post(
            _url(company_id, "/pricing/check-margin"),
            json={
                "unit_price": "100.00",
                "cost_price": "90.00",
                "min_margin_pct": "20.00",
                "block_on_low_margin": False,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["action"] == "WARN"
        assert data["passes"] is False

    def test_margin_block_when_configured_to_block(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        resp = test_client.post(
            _url(company_id, "/pricing/check-margin"),
            json={
                "unit_price": "100.00",
                "cost_price": "90.00",
                "min_margin_pct": "20.00",
                "block_on_low_margin": True,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["action"] == "BLOCK"

    def test_margin_ok_when_no_threshold(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        resp = test_client.post(
            _url(company_id, "/pricing/check-margin"),
            json={
                "unit_price": "10.00",
                "cost_price": "9.50",
                "min_margin_pct": None,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["action"] == "OK"

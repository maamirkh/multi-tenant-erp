"""API integration tests for Customer Master endpoints — Phase 1.

Tests:
  - POST /customers — create customer
  - GET  /customers — list/search customers
  - GET  /customers/{id} — get customer detail
  - PUT  /customers/{id} — update customer
  - POST /customers/{id}/transitions — status transitions
  - POST /customers/{id}/contacts — add contact
  - POST /customers/{id}/addresses — add address
  - POST /customers/{id}/notes — add note
  - PUT  /customers/{id}/credit — update credit
  - 409 on duplicate customer_code
  - 422 on invalid transition

Task: T059
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateCustomer:
    def test_create_customer_success(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        # Need a category — create one first
        cat_resp = test_client.post(
            _url(company_id, "/customer-categories"),
            json={"code": "RETAIL", "name": "Retail"},
            headers=_auth(token),
        )
        assert cat_resp.status_code == 201, cat_resp.text
        category_id = cat_resp.json()["data"]["id"]

        resp = test_client.post(
            _url(company_id, "/customers"),
            json={
                "customer_code": "CUST-001",
                "legal_name": "ACME Corporation",
                "customer_type": "COMPANY",
                "category_id": category_id,
                "currency_code": "USD",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["customer_code"] == "CUST-001"
        assert data["status"] == "DRAFT"
        assert data["credit_status"] == "GOOD"

    def test_create_customer_duplicate_code_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        cat_resp = test_client.post(
            _url(company_id, "/customer-categories"),
            json={"code": "DUP", "name": "Dup"},
            headers=_auth(token),
        )
        category_id = cat_resp.json()["data"]["id"]

        body = {
            "customer_code": "DUP-001",
            "legal_name": "First Corp",
            "customer_type": "COMPANY",
            "category_id": category_id,
            "currency_code": "USD",
        }

        resp1 = test_client.post(
            _url(company_id, "/customers"), json=body, headers=_auth(token)
        )
        assert resp1.status_code == 201

        resp2 = test_client.post(
            _url(company_id, "/customers"), json=body, headers=_auth(token)
        )
        assert resp2.status_code == 409


class TestListCustomers:
    def test_list_customers_empty(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        resp = test_client.get(_url(company_id, "/customers"), headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_list_customers_returns_created(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        cat_resp = test_client.post(
            _url(company_id, "/customer-categories"),
            json={"code": "LIST", "name": "List"},
            headers=_auth(token),
        )
        category_id = cat_resp.json()["data"]["id"]

        test_client.post(
            _url(company_id, "/customers"),
            json={
                "customer_code": "LIST-001",
                "legal_name": "Listed Corp",
                "customer_type": "COMPANY",
                "category_id": category_id,
                "currency_code": "USD",
            },
            headers=_auth(token),
        )

        resp = test_client.get(_url(company_id, "/customers"), headers=_auth(token))
        assert resp.status_code == 200
        codes = [c["customer_code"] for c in resp.json()["data"]]
        assert "LIST-001" in codes


class TestGetCustomer:
    def test_get_customer_by_id(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        cat_resp = test_client.post(
            _url(company_id, "/customer-categories"),
            json={"code": "GET", "name": "Get"},
            headers=_auth(token),
        )
        category_id = cat_resp.json()["data"]["id"]

        create_resp = test_client.post(
            _url(company_id, "/customers"),
            json={
                "customer_code": "GET-001",
                "legal_name": "Get Corp",
                "customer_type": "COMPANY",
                "category_id": category_id,
                "currency_code": "USD",
            },
            headers=_auth(token),
        )
        customer_id = create_resp.json()["data"]["id"]

        get_resp = test_client.get(
            _url(company_id, f"/customers/{customer_id}"), headers=_auth(token)
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["id"] == customer_id

    def test_get_nonexistent_customer_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())
        fake_id = str(uuid4())

        resp = test_client.get(
            _url(company_id, f"/customers/{fake_id}"), headers=_auth(token)
        )
        assert resp.status_code == 404


class TestUpdateCustomer:
    def test_update_customer_legal_name(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        cat_resp = test_client.post(
            _url(company_id, "/customer-categories"),
            json={"code": "UPD", "name": "Upd"},
            headers=_auth(token),
        )
        category_id = cat_resp.json()["data"]["id"]

        create_resp = test_client.post(
            _url(company_id, "/customers"),
            json={
                "customer_code": "UPD-001",
                "legal_name": "Old Name Corp",
                "customer_type": "COMPANY",
                "category_id": category_id,
                "currency_code": "USD",
            },
            headers=_auth(token),
        )
        customer_id = create_resp.json()["data"]["id"]

        update_resp = test_client.put(
            _url(company_id, f"/customers/{customer_id}"),
            json={"legal_name": "New Name Corp"},
            headers=_auth(token),
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["data"]["legal_name"] == "New Name Corp"


class TestCustomerTransitions:
    def _create_customer_with_contact_and_address(
        self,
        client: TestClient,
        db_session: Session,
        company_id: str,
        token: str,
        code: str,
    ) -> str:
        """Helper: create customer + contact + address + payment term."""
        # Create category
        cat_resp = client.post(
            _url(company_id, "/customer-categories"),
            json={"code": f"CAT{code}", "name": f"Cat {code}"},
            headers=_auth(token),
        )
        category_id = cat_resp.json()["data"]["id"]

        # Create payment term
        term_resp = client.post(
            _url(company_id, "/payment-terms"),
            json={"code": f"NET{code}", "name": f"Net {code}", "due_days": 30},
            headers=_auth(token),
        )
        term_id = term_resp.json()["data"]["id"]

        # Create customer
        create_resp = client.post(
            _url(company_id, "/customers"),
            json={
                "customer_code": code,
                "legal_name": f"Corp {code}",
                "customer_type": "COMPANY",
                "category_id": category_id,
                "currency_code": "USD",
                "payment_term_id": term_id,
            },
            headers=_auth(token),
        )
        customer_id = create_resp.json()["data"]["id"]

        # Add contact
        client.post(
            _url(company_id, f"/customers/{customer_id}/contacts"),
            json={"contact_name": "Test Contact", "is_primary": True},
            headers=_auth(token),
        )

        # Add billing address
        client.post(
            _url(company_id, f"/customers/{customer_id}/addresses"),
            json={
                "address_type": "BILLING",
                "address_line_1": "123 Main St",
                "city": "New York",
                "country_code": "US",
                "is_default_billing": True,
            },
            headers=_auth(token),
        )

        return customer_id

    def test_activate_customer(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        customer_id = self._create_customer_with_contact_and_address(
            test_client, db_session, company_id, token, "ACT001"
        )

        resp = test_client.post(
            _url(company_id, f"/customers/{customer_id}/transitions"),
            json={"action": "activate"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "ACTIVE"

    def test_activate_without_contact_fails(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        cat_resp = test_client.post(
            _url(company_id, "/customer-categories"),
            json={"code": "NOCT", "name": "NoCt"},
            headers=_auth(token),
        )
        category_id = cat_resp.json()["data"]["id"]

        term_resp = test_client.post(
            _url(company_id, "/payment-terms"),
            json={"code": "NOCT30", "name": "NoCtNet30", "due_days": 30},
            headers=_auth(token),
        )
        term_id = term_resp.json()["data"]["id"]

        create_resp = test_client.post(
            _url(company_id, "/customers"),
            json={
                "customer_code": "NOCT-001",
                "legal_name": "No Contact Corp",
                "customer_type": "COMPANY",
                "category_id": category_id,
                "currency_code": "USD",
                "payment_term_id": term_id,
            },
            headers=_auth(token),
        )
        customer_id = create_resp.json()["data"]["id"]

        resp = test_client.post(
            _url(company_id, f"/customers/{customer_id}/transitions"),
            json={"action": "activate"},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_invalid_transition_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        cat_resp = test_client.post(
            _url(company_id, "/customer-categories"),
            json={"code": "INV", "name": "Inv"},
            headers=_auth(token),
        )
        category_id = cat_resp.json()["data"]["id"]

        create_resp = test_client.post(
            _url(company_id, "/customers"),
            json={
                "customer_code": "INV-001",
                "legal_name": "Invalid Corp",
                "customer_type": "COMPANY",
                "category_id": category_id,
                "currency_code": "USD",
            },
            headers=_auth(token),
        )
        customer_id = create_resp.json()["data"]["id"]

        # DRAFT cannot be held
        resp = test_client.post(
            _url(company_id, f"/customers/{customer_id}/transitions"),
            json={"action": "hold"},
            headers=_auth(token),
        )
        assert resp.status_code == 422


class TestCustomerContactAPI:
    def test_add_and_list_contact(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        cat_resp = test_client.post(
            _url(company_id, "/customer-categories"),
            json={"code": "CTCAT", "name": "Ct Cat"},
            headers=_auth(token),
        )
        category_id = cat_resp.json()["data"]["id"]

        create_resp = test_client.post(
            _url(company_id, "/customers"),
            json={
                "customer_code": "CT-001",
                "legal_name": "Contact Corp",
                "customer_type": "COMPANY",
                "category_id": category_id,
                "currency_code": "USD",
            },
            headers=_auth(token),
        )
        customer_id = create_resp.json()["data"]["id"]

        contact_resp = test_client.post(
            _url(company_id, f"/customers/{customer_id}/contacts"),
            json={"contact_name": "John Doe", "email": "john@example.com"},
            headers=_auth(token),
        )
        assert contact_resp.status_code == 201
        assert contact_resp.json()["data"]["contact_name"] == "John Doe"

        list_resp = test_client.get(
            _url(company_id, f"/customers/{customer_id}/contacts"),
            headers=_auth(token),
        )
        assert list_resp.status_code == 200
        assert len(list_resp.json()["data"]) == 1


class TestCustomerAddressAPI:
    def test_add_and_list_address(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        cat_resp = test_client.post(
            _url(company_id, "/customer-categories"),
            json={"code": "ADCAT", "name": "Ad Cat"},
            headers=_auth(token),
        )
        category_id = cat_resp.json()["data"]["id"]

        create_resp = test_client.post(
            _url(company_id, "/customers"),
            json={
                "customer_code": "AD-001",
                "legal_name": "Address Corp",
                "customer_type": "COMPANY",
                "category_id": category_id,
                "currency_code": "USD",
            },
            headers=_auth(token),
        )
        customer_id = create_resp.json()["data"]["id"]

        addr_resp = test_client.post(
            _url(company_id, f"/customers/{customer_id}/addresses"),
            json={
                "address_type": "BILLING",
                "address_line_1": "123 Main St",
                "city": "New York",
                "country_code": "US",
                "is_default_billing": True,
            },
            headers=_auth(token),
        )
        assert addr_resp.status_code == 201
        assert addr_resp.json()["data"]["city"] == "New York"

        list_resp = test_client.get(
            _url(company_id, f"/customers/{customer_id}/addresses"),
            headers=_auth(token),
        )
        assert list_resp.status_code == 200
        assert len(list_resp.json()["data"]) == 1


class TestCustomerNoteAPI:
    def test_add_and_list_note(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        cat_resp = test_client.post(
            _url(company_id, "/customer-categories"),
            json={"code": "NTCAT", "name": "Nt Cat"},
            headers=_auth(token),
        )
        category_id = cat_resp.json()["data"]["id"]

        create_resp = test_client.post(
            _url(company_id, "/customers"),
            json={
                "customer_code": "NT-001",
                "legal_name": "Note Corp",
                "customer_type": "COMPANY",
                "category_id": category_id,
                "currency_code": "USD",
            },
            headers=_auth(token),
        )
        customer_id = create_resp.json()["data"]["id"]

        note_resp = test_client.post(
            _url(company_id, f"/customers/{customer_id}/notes"),
            json={"content": "Internal note for this customer"},
            headers=_auth(token),
        )
        assert note_resp.status_code == 201
        assert "Internal note" in note_resp.json()["data"]["content"]

        list_resp = test_client.get(
            _url(company_id, f"/customers/{customer_id}/notes"),
            headers=_auth(token),
        )
        assert list_resp.status_code == 200
        assert len(list_resp.json()["data"]) == 1


class TestCustomerCreditAPI:
    def test_update_credit(self, test_client: TestClient, db_session: Session) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        cat_resp = test_client.post(
            _url(company_id, "/customer-categories"),
            json={"code": "CRCAT", "name": "Cr Cat"},
            headers=_auth(token),
        )
        category_id = cat_resp.json()["data"]["id"]

        create_resp = test_client.post(
            _url(company_id, "/customers"),
            json={
                "customer_code": "CR-001",
                "legal_name": "Credit Corp",
                "customer_type": "COMPANY",
                "category_id": category_id,
                "currency_code": "USD",
            },
            headers=_auth(token),
        )
        customer_id = create_resp.json()["data"]["id"]

        credit_resp = test_client.put(
            _url(company_id, f"/customers/{customer_id}/credit"),
            json={"credit_limit": "50000.00"},
            headers=_auth(token),
        )
        assert credit_resp.status_code == 200
        assert float(credit_resp.json()["data"]["credit_limit"]) == 50000.0

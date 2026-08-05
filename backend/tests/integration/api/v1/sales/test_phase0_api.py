"""API integration tests for Phase 0 sales endpoints.

Tests:
  - Health endpoint returns 200
  - Customer Category CRUD via API
  - Customer Group CRUD via API
  - Payment Term CRUD via API
  - Reason Code CRUD via API
  - Configuration get/update via API
  - Feature flag listing via API
  - 409 on duplicate code creation

Requires the FastAPI test client.

Task: T030
"""

from __future__ import annotations

from uuid import uuid4

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
    return f"/api/v1/companies/{company_id}/sales{path}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSalesHealthEndpoint:
    """Test /health endpoint."""

    def test_health_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        response = test_client.get(_url(company_id, "/health"), headers=_auth(token))
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "healthy"
        assert data["module"] == "sales"
        assert data["version"] == "1.0.0"


class TestCustomerCategoryAPI:
    """Test Customer Category CRUD endpoints."""

    def test_list_empty(self, test_client: TestClient, db_session: Session) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        response = test_client.get(
            _url(company_id, "/customer-categories"), headers=_auth(token)
        )
        assert response.status_code == 200
        assert isinstance(response.json()["data"], list)

    def test_create_category(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        response = test_client.post(
            _url(company_id, "/customer-categories"),
            json={"code": "RETAIL", "name": "Retail Customers"},
            headers=_auth(token),
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["code"] == "RETAIL"
        assert data["name"] == "Retail Customers"
        assert data["is_active"] is True

    def test_duplicate_code_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        test_client.post(
            _url(company_id, "/customer-categories"),
            json={"code": "DUP", "name": "First"},
            headers=_auth(token),
        )
        response = test_client.post(
            _url(company_id, "/customer-categories"),
            json={"code": "DUP", "name": "Second"},
            headers=_auth(token),
        )
        assert response.status_code == 409

    def test_update_category(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        create_resp = test_client.post(
            _url(company_id, "/customer-categories"),
            json={"code": "UPD", "name": "Original"},
            headers=_auth(token),
        )
        cat_id = create_resp.json()["data"]["id"]

        update_resp = test_client.put(
            _url(company_id, f"/customer-categories/{cat_id}"),
            json={"name": "Updated"},
            headers=_auth(token),
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["data"]["name"] == "Updated"


class TestCustomerGroupAPI:
    """Test Customer Group CRUD endpoints."""

    def test_create_group(self, test_client: TestClient, db_session: Session) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        response = test_client.post(
            _url(company_id, "/customer-groups"),
            json={"code": "VIP", "name": "VIP Customers"},
            headers=_auth(token),
        )
        assert response.status_code == 201
        assert response.json()["data"]["code"] == "VIP"


class TestPaymentTermAPI:
    """Test Payment Term CRUD endpoints."""

    def test_create_payment_term(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        response = test_client.post(
            _url(company_id, "/payment-terms"),
            json={"code": "NET30", "name": "Net 30", "due_days": 30},
            headers=_auth(token),
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["code"] == "NET30"
        assert data["due_days"] == 30


class TestReasonCodeAPI:
    """Test Reason Code CRUD endpoints."""

    def test_create_reason_code(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        response = test_client.post(
            _url(company_id, "/reason-codes"),
            json={"code": "DEFECTIVE", "name": "Defective", "reason_type": "RETURN"},
            headers=_auth(token),
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["code"] == "DEFECTIVE"
        assert data["reason_type"] == "RETURN"


class TestFeatureFlagsAPI:
    """Test Feature Flags endpoint."""

    def test_list_flags(self, test_client: TestClient, db_session: Session) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        response = test_client.get(
            _url(company_id, "/feature-flags"), headers=_auth(token)
        )
        assert response.status_code == 200
        flags = response.json()["data"]
        assert len(flags) == 14
        keys = [f["flag_key"] for f in flags]
        assert "sales.approval_required_so" in keys


class TestConfigurationAPI:
    """Test Configuration endpoints."""

    def test_get_configuration_creates_defaults(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        token = _login(test_client, user.email, password)
        company_id = str(uuid4())

        response = test_client.get(
            _url(company_id, "/configuration"), headers=_auth(token)
        )
        assert response.status_code == 200
        config = response.json()["data"]
        assert config["default_quotation_validity_days"] == 30
        assert config["reservation_expiry_hours"] == 48

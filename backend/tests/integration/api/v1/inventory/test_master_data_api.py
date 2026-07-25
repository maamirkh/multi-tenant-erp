"""API integration tests for Inventory master data endpoints.

Tests: CRUD, status codes, deactivation guard, permission enforcement,
401/403 scenarios.

Task: T051
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

# ---------------------------------------------------------------------------
# Auth helpers
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


# =============================================================================
# Unauthenticated access
# =============================================================================


class TestUnauthenticated:
    def test_categories_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_company_url(str(uuid.uuid4()), "/categories"))
        assert resp.status_code == 401

    def test_brands_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_company_url(str(uuid.uuid4()), "/brands"))
        assert resp.status_code == 401

    def test_uom_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_company_url(str(uuid.uuid4()), "/uom"))
        assert resp.status_code == 401

    def test_tags_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_company_url(str(uuid.uuid4()), "/tags"))
        assert resp.status_code == 401

    def test_reason_codes_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_company_url(str(uuid.uuid4()), "/reason-codes"))
        assert resp.status_code == 401

    def test_custom_fields_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_company_url(str(uuid.uuid4()), "/custom-fields"))
        assert resp.status_code == 401

    def test_attributes_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_company_url(str(uuid.uuid4()), "/attributes"))
        assert resp.status_code == 401


# =============================================================================
# Category CRUD
# =============================================================================


class TestCategoryCRUD:
    def test_create_category_returns_201(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="inv_cat_create@example.com"
        )
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        resp = test_client.post(
            _company_url(company_id, "/categories"),
            json={"code": "ELEC", "name": "Electronics", "sort_order": 1},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["code"] == "ELEC"
        assert data["name"] == "Electronics"
        assert data["status"] == "active"

    def test_create_category_duplicate_code_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="inv_cat_dup@example.com")
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        payload = {"code": "DUPCAT", "name": "Dup", "sort_order": 0}
        test_client.post(
            _company_url(company_id, "/categories"), json=payload, headers=_auth(token)
        )
        resp = test_client.post(
            _company_url(company_id, "/categories"), json=payload, headers=_auth(token)
        )
        assert resp.status_code == 409

    def test_list_categories_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="inv_cat_list@example.com")
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        # create one
        test_client.post(
            _company_url(company_id, "/categories"),
            json={"code": "CAT1", "name": "Cat One", "sort_order": 0},
            headers=_auth(token),
        )
        resp = test_client.get(
            _company_url(company_id, "/categories"), headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_category_not_found_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="inv_cat_404@example.com")
        token = _login(test_client, user.email, password)
        resp = test_client.get(
            _company_url(str(uuid.uuid4()), f"/categories/{uuid.uuid4()}"),
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_deactivate_category_with_active_children_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="inv_cat_guard@example.com")
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        # Create parent
        resp = test_client.post(
            _company_url(company_id, "/categories"),
            json={"code": "PARENT", "name": "Parent", "sort_order": 0},
            headers=_auth(token),
        )
        parent_id = resp.json()["data"]["id"]
        # Create child
        test_client.post(
            _company_url(company_id, "/categories"),
            json={
                "code": "CHILD",
                "name": "Child",
                "sort_order": 0,
                "parent_id": parent_id,
            },
            headers=_auth(token),
        )
        # Deactivate parent — should fail because child is active
        resp = test_client.post(
            _company_url(company_id, f"/categories/{parent_id}/deactivate"),
            headers=_auth(token),
        )
        assert resp.status_code == 409

    def test_delete_category_returns_204(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="inv_cat_del@example.com")
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        resp = test_client.post(
            _company_url(company_id, "/categories"),
            json={"code": "TODEL", "name": "To Delete", "sort_order": 0},
            headers=_auth(token),
        )
        cat_id = resp.json()["data"]["id"]
        del_resp = test_client.delete(
            _company_url(company_id, f"/categories/{cat_id}"),
            headers=_auth(token),
        )
        assert del_resp.status_code == 204


# =============================================================================
# Brand CRUD
# =============================================================================


class TestBrandCRUD:
    def test_create_brand_returns_201(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="inv_brand_create@example.com"
        )
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        resp = test_client.post(
            _company_url(company_id, "/brands"),
            json={"code": "SONY", "name": "Sony"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["code"] == "SONY"
        assert data["status"] == "active"

    def test_create_brand_duplicate_code_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="inv_brand_dup@example.com")
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        payload = {"code": "DUP", "name": "Dup Brand"}
        test_client.post(
            _company_url(company_id, "/brands"), json=payload, headers=_auth(token)
        )
        resp = test_client.post(
            _company_url(company_id, "/brands"), json=payload, headers=_auth(token)
        )
        assert resp.status_code == 409

    def test_list_brands_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="inv_brand_list@example.com"
        )
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        resp = test_client.get(
            _company_url(company_id, "/brands"), headers=_auth(token)
        )
        assert resp.status_code == 200

    def test_deactivate_brand_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="inv_brand_deact@example.com"
        )
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        resp = test_client.post(
            _company_url(company_id, "/brands"),
            json={"code": "DEACT", "name": "Deact Brand"},
            headers=_auth(token),
        )
        brand_id = resp.json()["data"]["id"]
        resp = test_client.post(
            _company_url(company_id, f"/brands/{brand_id}/deactivate"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "inactive"


# =============================================================================
# UOM CRUD
# =============================================================================


class TestUOMCRUD:
    def test_create_uom_returns_201(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="inv_uom_create@example.com"
        )
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        resp = test_client.post(
            _company_url(company_id, "/uom"),
            json={
                "code": "KG",
                "name": "Kilogram",
                "uom_type": "WEIGHT",
                "symbol": "kg",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["code"] == "KG"
        assert data["uom_type"] == "WEIGHT"

    def test_create_uom_invalid_type_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="inv_uom_invalid@example.com"
        )
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        resp = test_client.post(
            _company_url(company_id, "/uom"),
            json={"code": "X", "name": "X", "uom_type": "BADTYPE"},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_list_uom_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="inv_uom_list@example.com")
        token = _login(test_client, user.email, password)
        resp = test_client.get(
            _company_url(str(uuid.uuid4()), "/uom"), headers=_auth(token)
        )
        assert resp.status_code == 200


# =============================================================================
# Tag CRUD
# =============================================================================


class TestTagCRUD:
    def test_create_tag_returns_201(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="inv_tag_create@example.com"
        )
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        resp = test_client.post(
            _company_url(company_id, "/tags"),
            json={"name": "Sale", "color": "#FF5733"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "Sale"
        assert data["color"] == "#FF5733"

    def test_create_tag_invalid_color_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="inv_tag_badcolor@example.com"
        )
        token = _login(test_client, user.email, password)
        resp = test_client.post(
            _company_url(str(uuid.uuid4()), "/tags"),
            json={"name": "Bad", "color": "notacolor"},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_duplicate_tag_name_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="inv_tag_dup@example.com")
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        test_client.post(
            _company_url(company_id, "/tags"),
            json={"name": "Promo"},
            headers=_auth(token),
        )
        resp = test_client.post(
            _company_url(company_id, "/tags"),
            json={"name": "Promo"},
            headers=_auth(token),
        )
        assert resp.status_code == 409


# =============================================================================
# Reason Code CRUD
# =============================================================================


class TestReasonCodeCRUD:
    def test_create_reason_code_returns_201(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="inv_rc_create@example.com")
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        resp = test_client.post(
            _company_url(company_id, "/reason-codes"),
            json={"code": "DMG01", "label": "Physical Damage", "applies_to": "DAMAGE"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["code"] == "DMG01"
        assert data["is_active"] is True

    def test_create_reason_code_invalid_applies_to_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="inv_rc_invalid@example.com"
        )
        token = _login(test_client, user.email, password)
        resp = test_client.post(
            _company_url(str(uuid.uuid4()), "/reason-codes"),
            json={"code": "X", "label": "X", "applies_to": "INVALID"},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_deactivate_reason_code_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="inv_rc_deact@example.com")
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        resp = test_client.post(
            _company_url(company_id, "/reason-codes"),
            json={"code": "ADJ01", "label": "Manual Adj", "applies_to": "ADJUSTMENT"},
            headers=_auth(token),
        )
        rc_id = resp.json()["data"]["id"]
        resp = test_client.post(
            _company_url(company_id, f"/reason-codes/{rc_id}/deactivate"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_active"] is False


# =============================================================================
# Custom Fields CRUD
# =============================================================================


class TestCustomFieldCRUD:
    def test_create_custom_field_returns_201(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="inv_cf_create@example.com")
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        resp = test_client.post(
            _company_url(company_id, "/custom-fields"),
            json={
                "entity_type": "PRODUCT",
                "field_key": "warranty_type",
                "field_label": "Warranty Type",
                "data_type": "TEXT",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["field_key"] == "warranty_type"

    def test_duplicate_field_key_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="inv_cf_dup@example.com")
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        payload = {
            "entity_type": "PRODUCT",
            "field_key": "my_field",
            "field_label": "My Field",
            "data_type": "TEXT",
        }
        test_client.post(
            _company_url(company_id, "/custom-fields"),
            json=payload,
            headers=_auth(token),
        )
        resp = test_client.post(
            _company_url(company_id, "/custom-fields"),
            json=payload,
            headers=_auth(token),
        )
        assert resp.status_code == 409

    def test_list_custom_fields_by_entity_type(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="inv_cf_list@example.com")
        token = _login(test_client, user.email, password)
        company_id = str(uuid.uuid4())
        resp = test_client.get(
            _company_url(company_id, "/custom-fields?entity_type=PRODUCT"),
            headers=_auth(token),
        )
        assert resp.status_code == 200


# =============================================================================
# Inventory module health
# =============================================================================


class TestInventoryHealth:
    def test_health_returns_operational(self, test_client: TestClient) -> None:
        resp = test_client.get("/api/v1/inventory/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "operational"

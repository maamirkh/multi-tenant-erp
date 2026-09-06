"""T286 — Soft-delete completeness verification.

Verifies that:
  1. Every inventory entity with a DELETE endpoint performs soft-delete
     (sets is_deleted=True, does NOT physically remove the row).
  2. Deleted entities are excluded from list responses.
  3. Hard DELETE is not possible — data is always recoverable.

Spec ref: specs/005-inventory-management/spec.md §10 (Data Management)
Tasks: T286 Phase 12
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.inventory.models.category import Category
from modules.inventory.models.product import Product
from modules.inventory.models.reason_code import ReasonCode
from modules.inventory.models.uom import UOM
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


def _create_company(client: TestClient, token: str) -> uuid.UUID:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Inventory Test Co {suffix}",
            "email": f"contact-{suffix}@inv-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _auth(client: TestClient, db: Session) -> tuple[dict, uuid.UUID]:
    email = f"sd-{uuid.uuid4().hex[:8]}@test.com"
    create_test_user(db, email=email, password="TestPass123!")
    token = _login(client, email, "TestPass123!")
    company_id = _create_company(client, token)
    return {"Authorization": f"Bearer {token}"}, company_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSoftDeleteCompleteness:
    """Verify all DELETE endpoints perform soft-delete (is_deleted=True)."""

    def test_category_soft_delete(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """DELETE /categories/{id} sets is_deleted=True; row still exists in DB."""
        headers, company_id = _auth(test_client, db_session)

        # Create category
        resp = test_client.post(
            _url(company_id, "/categories"),
            json={
                "code": f"SDCAT{uuid.uuid4().hex[:4].upper()}",
                "name": "Soft Delete Cat",
            },
            headers=headers,
        )
        assert resp.status_code == 201, f"Create failed: {resp.text}"
        cat_id = resp.json()["data"]["id"]

        # Delete category
        resp = test_client.delete(
            _url(company_id, f"/categories/{cat_id}"),
            headers=headers,
        )
        assert resp.status_code == 204, f"Delete failed: {resp.text}"

        # Verify row still exists in DB with is_deleted=True
        category = (
            db_session.execute(select(Category).where(Category.id == uuid.UUID(cat_id)))
            .scalars()
            .one_or_none()
        )
        assert category is not None, (
            "Row was hard-deleted from DB (should be soft-deleted)"
        )
        assert category.is_deleted is True, f"is_deleted not set: {category.is_deleted}"

        # Verify excluded from list
        resp = test_client.get(_url(company_id, "/categories"), headers=headers)
        assert resp.status_code == 200
        cat_ids = [c["id"] for c in resp.json()["data"]]
        assert cat_id not in cat_ids, "Soft-deleted category still in list response"

    def test_product_soft_delete(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """DELETE /products/{id} sets is_deleted=True; row still exists in DB."""
        headers, company_id = _auth(test_client, db_session)

        uom = UOM(
            id=uuid.uuid4(),
            company_id=company_id,
            code=f"SD{uuid.uuid4().hex[:4].upper()}",
            name="Units",
            uom_type="UNIT",
            status="active",
        )
        db_session.add(uom)
        db_session.flush()

        # Create product
        resp = test_client.post(
            _url(company_id, "/products"),
            json={
                "product_code": f"SD-{uuid.uuid4().hex[:6].upper()}",
                "name": "Soft Delete Product",
                "product_type": "STANDARD",
                "base_uom_id": str(uom.id),
            },
            headers=headers,
        )
        assert resp.status_code == 201
        product_id = resp.json()["data"]["id"]

        # Delete
        resp = test_client.delete(
            _url(company_id, f"/products/{product_id}"),
            headers=headers,
        )
        assert resp.status_code == 204, f"Delete failed: {resp.text}"

        # Verify soft-deleted in DB
        product = (
            db_session.execute(
                select(Product).where(Product.id == uuid.UUID(product_id))
            )
            .scalars()
            .one_or_none()
        )
        assert product is not None, "Product row was hard-deleted"
        assert product.is_deleted is True

    def test_uom_soft_delete(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """DELETE /uom/{id} sets is_deleted=True."""
        headers, company_id = _auth(test_client, db_session)

        # Create UOM
        resp = test_client.post(
            _url(company_id, "/uom"),
            json={
                "code": f"SU{uuid.uuid4().hex[:4].upper()}",
                "name": "Soft Delete UOM",
                "uom_type": "UNIT",
            },
            headers=headers,
        )
        assert resp.status_code == 201, f"UOM create failed: {resp.text}"
        uom_id = resp.json()["data"]["id"]

        # Delete
        resp = test_client.delete(
            _url(company_id, f"/uom/{uom_id}"),
            headers=headers,
        )
        assert resp.status_code == 204, f"UOM delete failed: {resp.text}"

        # Verify soft-deleted
        uom = (
            db_session.execute(select(UOM).where(UOM.id == uuid.UUID(uom_id)))
            .scalars()
            .one_or_none()
        )
        assert uom is not None, "UOM row was hard-deleted"
        assert uom.is_deleted is True

    def test_reason_code_soft_delete(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """DELETE /reason-codes/{id} sets is_deleted=True."""
        headers, company_id = _auth(test_client, db_session)

        # Create reason code
        resp = test_client.post(
            _url(company_id, "/reason-codes"),
            json={
                "code": f"SR{uuid.uuid4().hex[:4].upper()}",
                "label": "Soft Delete Reason",
                "applies_to": "ADJUSTMENT",
            },
            headers=headers,
        )
        assert resp.status_code == 201, f"Reason code create failed: {resp.text}"
        rc_id = resp.json()["data"]["id"]

        # Delete
        resp = test_client.delete(
            _url(company_id, f"/reason-codes/{rc_id}"),
            headers=headers,
        )
        assert resp.status_code == 204, f"Reason code delete failed: {resp.text}"

        # Verify
        rc = (
            db_session.execute(
                select(ReasonCode).where(ReasonCode.id == uuid.UUID(rc_id))
            )
            .scalars()
            .one_or_none()
        )
        assert rc is not None, "ReasonCode row was hard-deleted"
        assert rc.is_deleted is True

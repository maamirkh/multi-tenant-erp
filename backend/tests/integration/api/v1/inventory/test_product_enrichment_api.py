"""API integration tests for Phase 3 product enrichment endpoints.

Tests: tags, custom-fields, notes, images, import, export.

Spec ref: specs/005-inventory-management/spec.md §14, §35
"""

from __future__ import annotations

import io
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.inventory.models.product import Product
from modules.inventory.models.tag import Tag
from modules.inventory.models.uom import UOM
from modules.inventory.repositories.product_repository import ProductRepository
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
    email = f"user-{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"
    create_test_user(db, email=email, password=password)
    token = _login(client, email, password)
    company_id = _create_company(client, token)
    return email, password, company_id


def _make_uom(db: Session, company_id: uuid.UUID) -> UOM:
    uom = UOM(
        company_id=company_id,
        code=f"PCS-{uuid.uuid4().hex[:4]}",
        name="Pieces",
        uom_type="UNIT",
        status="active",
    )
    db.add(uom)
    db.flush()
    return uom


def _make_product(
    db: Session, company_id: uuid.UUID, uom: UOM, code: str | None = None
) -> Product:
    p = Product(
        company_id=company_id,
        product_code=code or f"P-{uuid.uuid4().hex[:6]}",
        name="Test Product",
        product_type="STANDARD",
        status="DRAFT",
        base_uom_id=str(uom.id),
    )
    p.search_vector = ProductRepository.build_search_vector(p)
    db.add(p)
    db.flush()
    return p


def _make_tag(db: Session, company_id: uuid.UUID) -> Tag:
    t = Tag(
        company_id=company_id,
        name=f"tag-{uuid.uuid4().hex[:6]}",
        color="#FF0000",
    )
    db.add(t)
    db.flush()
    return t


# =============================================================================
# Unauthenticated access
# =============================================================================


class TestEnrichmentUnauthenticated:
    def test_tags_requires_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        resp = test_client.get(_url(company_id, f"/products/{uuid.uuid4()}/tags"))
        assert resp.status_code == 401

    def test_notes_requires_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        resp = test_client.get(_url(company_id, f"/products/{uuid.uuid4()}/notes"))
        assert resp.status_code == 401

    def test_custom_fields_requires_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        resp = test_client.get(
            _url(company_id, f"/products/{uuid.uuid4()}/custom-fields")
        )
        assert resp.status_code == 401

    def test_images_requires_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        resp = test_client.get(_url(company_id, f"/products/{uuid.uuid4()}/images"))
        assert resp.status_code == 401


# =============================================================================
# Tags
# =============================================================================


class TestProductTagsApi:
    def test_assign_and_list_tags(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        tag = _make_tag(db_session, company_id)
        db_session.commit()

        token = _login(test_client, email, password)
        headers = _auth(token)

        # Assign tag
        resp = test_client.post(
            _url(company_id, f"/products/{product.id}/tags"),
            json={"tag_id": str(tag.id)},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["tag_id"] == str(tag.id)

        # List tags
        resp = test_client.get(
            _url(company_id, f"/products/{product.id}/tags"), headers=headers
        )
        assert resp.status_code == 200
        tags = resp.json()["data"]
        assert len(tags) == 1
        assert tags[0]["tag_id"] == str(tag.id)

    def test_assign_tag_idempotent(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        tag = _make_tag(db_session, company_id)
        db_session.commit()

        token = _login(test_client, email, password)
        headers = _auth(token)

        test_client.post(
            _url(company_id, f"/products/{product.id}/tags"),
            json={"tag_id": str(tag.id)},
            headers=headers,
        )
        test_client.post(
            _url(company_id, f"/products/{product.id}/tags"),
            json={"tag_id": str(tag.id)},
            headers=headers,
        )

        resp = test_client.get(
            _url(company_id, f"/products/{product.id}/tags"), headers=headers
        )
        assert len(resp.json()["data"]) == 1  # still just one

    def test_remove_tag(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        tag = _make_tag(db_session, company_id)
        db_session.commit()

        token = _login(test_client, email, password)
        headers = _auth(token)

        test_client.post(
            _url(company_id, f"/products/{product.id}/tags"),
            json={"tag_id": str(tag.id)},
            headers=headers,
        )

        resp = test_client.delete(
            _url(company_id, f"/products/{product.id}/tags/{tag.id}"),
            headers=headers,
        )
        assert resp.status_code == 204

        resp = test_client.get(
            _url(company_id, f"/products/{product.id}/tags"), headers=headers
        )
        assert len(resp.json()["data"]) == 0

    def test_assign_nonexistent_tag_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        db_session.commit()

        token = _login(test_client, email, password)
        resp = test_client.post(
            _url(company_id, f"/products/{product.id}/tags"),
            json={"tag_id": str(uuid.uuid4())},
            headers=_auth(token),
        )
        assert resp.status_code == 404


# =============================================================================
# Custom Field Values
# =============================================================================


class TestCustomFieldValuesApi:
    def test_set_and_list_custom_field(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        db_session.commit()

        token = _login(test_client, email, password)
        headers = _auth(token)

        resp = test_client.post(
            _url(company_id, f"/products/{product.id}/custom-fields"),
            json={"field_key": "warranty_months", "value_text": "24"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["field_key"] == "warranty_months"
        assert resp.json()["data"]["value_text"] == "24"

        resp = test_client.get(
            _url(company_id, f"/products/{product.id}/custom-fields"), headers=headers
        )
        assert resp.status_code == 200
        fields = resp.json()["data"]
        assert len(fields) == 1
        assert fields[0]["field_key"] == "warranty_months"

    def test_upsert_updates_value(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        db_session.commit()

        token = _login(test_client, email, password)
        headers = _auth(token)

        test_client.post(
            _url(company_id, f"/products/{product.id}/custom-fields"),
            json={"field_key": "colour", "value_text": "Red"},
            headers=headers,
        )
        test_client.post(
            _url(company_id, f"/products/{product.id}/custom-fields"),
            json={"field_key": "colour", "value_text": "Blue"},
            headers=headers,
        )

        resp = test_client.get(
            _url(company_id, f"/products/{product.id}/custom-fields"), headers=headers
        )
        fields = resp.json()["data"]
        assert len(fields) == 1
        assert fields[0]["value_text"] == "Blue"

    def test_delete_custom_field(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        db_session.commit()

        token = _login(test_client, email, password)
        headers = _auth(token)

        test_client.post(
            _url(company_id, f"/products/{product.id}/custom-fields"),
            json={"field_key": "to_delete", "value_text": "bye"},
            headers=headers,
        )
        resp = test_client.delete(
            _url(company_id, f"/products/{product.id}/custom-fields/to_delete"),
            headers=headers,
        )
        assert resp.status_code == 204

        resp = test_client.get(
            _url(company_id, f"/products/{product.id}/custom-fields"), headers=headers
        )
        assert len(resp.json()["data"]) == 0


# =============================================================================
# Internal Notes
# =============================================================================


class TestInternalNotesApi:
    def test_add_and_list_notes(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        db_session.commit()

        token = _login(test_client, email, password)
        headers = _auth(token)

        resp = test_client.post(
            _url(company_id, f"/products/{product.id}/notes"),
            json={"note_text": "Price updated for Q3."},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        assert "Q3" in resp.json()["data"]["note_text"]

        resp = test_client.get(
            _url(company_id, f"/products/{product.id}/notes"), headers=headers
        )
        assert resp.status_code == 200
        notes = resp.json()["data"]
        assert len(notes) == 1

    def test_multiple_notes_all_returned(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        db_session.commit()

        token = _login(test_client, email, password)
        headers = _auth(token)

        test_client.post(
            _url(company_id, f"/products/{product.id}/notes"),
            json={"note_text": "First note"},
            headers=headers,
        )
        test_client.post(
            _url(company_id, f"/products/{product.id}/notes"),
            json={"note_text": "Second note"},
            headers=headers,
        )

        resp = test_client.get(
            _url(company_id, f"/products/{product.id}/notes"), headers=headers
        )
        notes = resp.json()["data"]
        assert len(notes) == 2

    def test_empty_note_text_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        db_session.commit()

        token = _login(test_client, email, password)
        resp = test_client.post(
            _url(company_id, f"/products/{product.id}/notes"),
            json={"note_text": ""},
            headers=_auth(token),
        )
        assert resp.status_code == 422


# =============================================================================
# Images
# =============================================================================


class TestProductImagesApi:
    def test_upload_image(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        db_session.commit()

        token = _login(test_client, email, password)
        headers = _auth(token)

        file_content = b"fake image bytes PNG"
        resp = test_client.post(
            _url(company_id, f"/products/{product.id}/images"),
            files={"file": ("test.png", io.BytesIO(file_content), "image/png")},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert "s3_key" in data
        assert "url" in data
        assert str(product.id) in data["product_id"]

    def test_list_images(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        db_session.commit()

        token = _login(test_client, email, password)
        headers = _auth(token)

        for i in range(2):
            test_client.post(
                _url(company_id, f"/products/{product.id}/images"),
                files={"file": (f"img{i}.png", io.BytesIO(b"img"), "image/png")},
                data={"sort_order": str(i)},
                headers=headers,
            )

        resp = test_client.get(
            _url(company_id, f"/products/{product.id}/images"), headers=headers
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2

    def test_delete_image(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        db_session.commit()

        token = _login(test_client, email, password)
        headers = _auth(token)

        resp = test_client.post(
            _url(company_id, f"/products/{product.id}/images"),
            files={"file": ("del.png", io.BytesIO(b"img"), "image/png")},
            headers=headers,
        )
        image_id = resp.json()["data"]["id"]

        resp = test_client.delete(
            _url(company_id, f"/products/{product.id}/images/{image_id}"),
            headers=headers,
        )
        assert resp.status_code == 204

        resp = test_client.get(
            _url(company_id, f"/products/{product.id}/images"), headers=headers
        )
        assert len(resp.json()["data"]) == 0


# =============================================================================
# Bulk Import / Export
# =============================================================================


class TestBulkImportExportApi:
    def _make_csv(self, rows: list[dict[str, Any]]) -> bytes:
        import csv
        import io as iomod

        fields = (
            list(rows[0].keys()) if rows else ["product_code", "name", "base_uom_code"]
        )
        buf = iomod.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8")

    def test_import_valid_csv(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        db_session.commit()

        token = _login(test_client, email, password)
        headers = _auth(token)

        csv_content = self._make_csv(
            [
                {
                    "product_code": "TV-001",
                    "name": "Smart TV 55in",
                    "base_uom_code": uom.code,
                    "product_type": "STANDARD",
                }
            ]
        )

        resp = test_client.post(
            _url(company_id, "/products/import"),
            files={"file": ("products.csv", io.BytesIO(csv_content), "text/csv")},
            headers=headers,
        )
        assert resp.status_code == 202, resp.text
        data = resp.json()["data"]
        assert data["status"] in ("COMPLETED", "FAILED_WITH_ERRORS")
        assert data["file_name"] == "products.csv"

    def test_import_job_pollable(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        db_session.commit()

        token = _login(test_client, email, password)
        headers = _auth(token)

        csv_content = self._make_csv(
            [{"product_code": "A-001", "name": "Product A", "base_uom_code": uom.code}]
        )
        resp = test_client.post(
            _url(company_id, "/products/import"),
            files={"file": ("import.csv", io.BytesIO(csv_content), "text/csv")},
            headers=headers,
        )
        job_id = resp.json()["data"]["id"]

        resp = test_client.get(
            _url(company_id, f"/products/import/{job_id}"), headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == job_id

    def test_import_nonexistent_job_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        db_session.commit()

        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, f"/products/import/{uuid.uuid4()}"),
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_export_returns_csv(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom, "EXPORT-001")
        db_session.commit()

        token = _login(test_client, email, password)
        resp = test_client.post(
            _url(company_id, "/products/export"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert b"EXPORT-001" in resp.content

    def test_import_missing_columns_creates_failed_job(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        db_session.commit()

        token = _login(test_client, email, password)
        bad_csv = b"name,product_type\nTV,STANDARD\n"
        resp = test_client.post(
            _url(company_id, "/products/import"),
            files={"file": ("bad.csv", io.BytesIO(bad_csv), "text/csv")},
            headers=_auth(token),
        )
        assert resp.status_code == 202
        assert resp.json()["data"]["status"] == "FAILED"

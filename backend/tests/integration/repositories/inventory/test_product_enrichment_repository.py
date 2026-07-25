"""Integration tests for Phase 3 enrichment repositories.

Tests: ProductTagRepository, ProductCustomFieldValueRepository,
       ProductInternalNoteRepository, ImportJobRepository.

Spec ref: specs/005-inventory-management/spec.md §14, §35
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from modules.inventory.models.product import Product
from modules.inventory.models.tag import Tag
from modules.inventory.models.uom import UOM
from modules.inventory.repositories.product_enrichment_repository import (
    ImportJobRepository,
    ProductCustomFieldValueRepository,
    ProductInternalNoteRepository,
    ProductTagRepository,
)
from modules.inventory.repositories.product_repository import ProductRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _make_tag(db: Session, company_id: uuid.UUID, name: str | None = None) -> Tag:
    t = Tag(
        company_id=company_id,
        name=name or f"tag-{uuid.uuid4().hex[:6]}",
        color="#FF0000",
    )
    db.add(t)
    db.flush()
    return t


# =============================================================================
# ProductTagRepository
# =============================================================================


class TestProductTagRepository:
    def test_assign_tag_creates_join(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        tag = _make_tag(db_session, company_id)

        repo = ProductTagRepository(db_session)
        pt = repo.assign(company_id, str(product.id), str(tag.id))

        assert str(pt.product_id) == str(product.id)
        assert str(pt.tag_id) == str(tag.id)

    def test_assign_same_tag_twice_is_idempotent(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        tag = _make_tag(db_session, company_id)

        repo = ProductTagRepository(db_session)
        pt1 = repo.assign(company_id, str(product.id), str(tag.id))
        pt2 = repo.assign(company_id, str(product.id), str(tag.id))

        assert pt1.id == pt2.id  # same record returned

    def test_list_returns_all_assigned_tags(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        tag1 = _make_tag(db_session, company_id, "electronics")
        tag2 = _make_tag(db_session, company_id, "sale")

        repo = ProductTagRepository(db_session)
        repo.assign(company_id, str(product.id), str(tag1.id))
        repo.assign(company_id, str(product.id), str(tag2.id))

        tags = repo.list_for_product(company_id, str(product.id))
        assert len(tags) == 2

    def test_remove_tag_soft_deletes(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        tag = _make_tag(db_session, company_id)

        repo = ProductTagRepository(db_session)
        repo.assign(company_id, str(product.id), str(tag.id))
        removed = repo.remove(company_id, str(product.id), str(tag.id))

        assert removed is True
        tags = repo.list_for_product(company_id, str(product.id))
        assert len(tags) == 0

    def test_remove_nonexistent_tag_returns_false(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        repo = ProductTagRepository(db_session)
        result = repo.remove(company_id, str(uuid.uuid4()), str(uuid.uuid4()))
        assert result is False

    def test_company_isolation(self, db_session: Session) -> None:
        """Tags from company A are not visible to company B."""
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        uom_a = _make_uom(db_session, company_a)
        uom_b = _make_uom(db_session, company_b)
        product_a = _make_product(db_session, company_a, uom_a)
        product_b = _make_product(db_session, company_b, uom_b)
        tag_a = _make_tag(db_session, company_a)

        repo = ProductTagRepository(db_session)
        repo.assign(company_a, str(product_a.id), str(tag_a.id))

        # Company B should see no tags on its product
        tags_b = repo.list_for_product(company_b, str(product_b.id))
        assert len(tags_b) == 0


# =============================================================================
# ProductCustomFieldValueRepository
# =============================================================================


class TestProductCustomFieldValueRepository:
    def test_set_and_get_text_value(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        repo = ProductCustomFieldValueRepository(db_session)

        cfv = repo.set_value(
            company_id, str(product.id), "warranty_months", value_text="24"
        )

        assert cfv.field_key == "warranty_months"
        assert cfv.value_text == "24"

    def test_upsert_updates_existing_value(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        repo = ProductCustomFieldValueRepository(db_session)

        repo.set_value(company_id, str(product.id), "colour", value_text="Red")
        repo.set_value(company_id, str(product.id), "colour", value_text="Blue")

        values = repo.list_values(company_id, str(product.id))
        assert len(values) == 1  # upserted, not duplicated
        assert values[0].value_text == "Blue"

    def test_set_multiple_fields(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        repo = ProductCustomFieldValueRepository(db_session)

        repo.set_value(company_id, str(product.id), "field_a", value_text="A")
        repo.set_value(company_id, str(product.id), "field_b", value_bool=True)
        repo.set_value(
            company_id, str(product.id), "field_c", value_json={"tags": ["x", "y"]}
        )

        values = repo.list_values(company_id, str(product.id))
        assert len(values) == 3

    def test_delete_value_soft_deletes(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        repo = ProductCustomFieldValueRepository(db_session)

        repo.set_value(company_id, str(product.id), "to_delete", value_text="bye")
        deleted = repo.delete_value(company_id, str(product.id), "to_delete")

        assert deleted is True
        values = repo.list_values(company_id, str(product.id))
        assert len(values) == 0

    def test_company_isolation(self, db_session: Session) -> None:
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        uom_a = _make_uom(db_session, company_a)
        uom_b = _make_uom(db_session, company_b)
        prod_a = _make_product(db_session, company_a, uom_a)
        prod_b = _make_product(db_session, company_b, uom_b)

        repo = ProductCustomFieldValueRepository(db_session)
        repo.set_value(company_a, str(prod_a.id), "secret", value_text="classified")

        values_b = repo.list_values(company_b, str(prod_b.id))
        assert len(values_b) == 0


# =============================================================================
# ProductInternalNoteRepository
# =============================================================================


class TestProductInternalNoteRepository:
    def test_add_note(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        author_id = str(uuid.uuid4())
        repo = ProductInternalNoteRepository(db_session)

        note = repo.add_note(company_id, str(product.id), "Test note", author_id)

        assert note.note_text == "Test note"
        assert note.author_id == author_id

    def test_list_notes_returns_all(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        repo = ProductInternalNoteRepository(db_session)

        repo.add_note(company_id, str(product.id), "First note")
        repo.add_note(company_id, str(product.id), "Second note")

        notes = repo.list_notes(company_id, str(product.id))
        assert len(notes) == 2
        note_texts = {n.note_text for n in notes}
        assert "First note" in note_texts
        assert "Second note" in note_texts

    def test_notes_are_not_editable_by_repo(self, db_session: Session) -> None:
        """Repository has no update method — append-only by design."""
        repo = ProductInternalNoteRepository(db_session)
        assert not hasattr(repo, "update_note")
        assert not hasattr(repo, "delete_note")

    def test_system_note_has_null_author(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom)
        repo = ProductInternalNoteRepository(db_session)

        note = repo.add_note(
            company_id, str(product.id), "System event", author_id=None
        )

        assert note.author_id is None

    def test_notes_are_company_isolated(self, db_session: Session) -> None:
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        uom_a = _make_uom(db_session, company_a)
        uom_b = _make_uom(db_session, company_b)
        prod_a = _make_product(db_session, company_a, uom_a)
        prod_b = _make_product(db_session, company_b, uom_b)
        repo = ProductInternalNoteRepository(db_session)

        repo.add_note(company_a, str(prod_a.id), "Company A confidential note")

        notes_b = repo.list_notes(company_b, str(prod_b.id))
        assert len(notes_b) == 0


# =============================================================================
# ImportJobRepository
# =============================================================================


class TestImportJobRepository:
    def test_create_job(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        repo = ImportJobRepository(db_session)

        job = repo.create(company_id, "products.csv", total_rows=100)

        assert job.file_name == "products.csv"
        assert job.total_rows == 100
        assert job.id is not None

    def test_get_job_by_id(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        repo = ImportJobRepository(db_session)

        job = repo.create(company_id, "test.csv")
        db_session.commit()

        fetched = repo.get(company_id, job.id)
        assert fetched is not None
        assert fetched.id == job.id

    def test_get_job_wrong_company_returns_none(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        other_company = uuid.uuid4()
        repo = ImportJobRepository(db_session)

        job = repo.create(company_id, "test.csv")
        db_session.commit()

        fetched = repo.get(other_company, job.id)
        assert fetched is None

    def test_update_status_completed(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        repo = ImportJobRepository(db_session)

        job = repo.create(company_id, "batch.csv", total_rows=50)
        repo.update_status(job, "PROCESSING")
        repo.update_status(
            job, "COMPLETED", processed_rows=50, failed_rows=0, error_rows=None
        )

        assert job.status == "COMPLETED"
        assert job.processed_rows == 50
        assert job.failed_rows == 0

    def test_update_status_failed_with_errors(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        repo = ImportJobRepository(db_session)

        error_payload = [
            {"row_number": 3, "product_code": "X", "errors": ["UOM not found"]}
        ]
        job = repo.create(company_id, "batch.csv", total_rows=5)
        repo.update_status(
            job,
            "FAILED_WITH_ERRORS",
            processed_rows=4,
            failed_rows=1,
            error_rows=error_payload,
        )

        assert job.status == "FAILED_WITH_ERRORS"
        assert len(job.error_rows) == 1

    def test_list_for_company_returns_all(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        repo = ImportJobRepository(db_session)

        repo.create(company_id, "first.csv")
        db_session.commit()
        repo.create(company_id, "second.csv")
        db_session.commit()

        jobs = repo.list_for_company(company_id)
        assert len(jobs) == 2
        file_names = {j.file_name for j in jobs}
        assert "first.csv" in file_names
        assert "second.csv" in file_names

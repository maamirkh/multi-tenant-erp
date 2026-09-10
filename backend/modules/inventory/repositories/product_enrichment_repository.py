"""ProductEnrichmentRepository — data-access for Phase 3 enrichment entities.

Covers:
  - ProductTag        : assign / remove tags on products
  - ProductCustomFieldValue : set / get / list[Any] per-product custom field values
  - ProductInternalNote : append-only notes
  - ImportJob          : create / get / update import job state

All operations are scoped to ``company_id`` for multi-tenant isolation.

Spec ref: specs/005-inventory-management/spec.md §14, §35
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.inventory.models.product_enrichment import (
    ImportJob,
    ProductCustomFieldValue,
    ProductInternalNote,
    ProductTag,
)

# =============================================================================
# ProductTagRepository
# =============================================================================


class ProductTagRepository:
    """Data-access for the product↔tag many-to-many join table."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def assign(self, company_id: UUID, product_id: str, tag_id: str) -> ProductTag:
        """Assign a tag to a product (idempotent — no-op if already assigned)."""
        existing = (
            self.db.execute(
                select(ProductTag)
                .where(ProductTag.company_id == company_id)
                .where(ProductTag.product_id == product_id)
                .where(ProductTag.tag_id == tag_id)
                .where(ProductTag.is_deleted == False)  # noqa: E712
            )
            .scalars()
            .one_or_none()
        )
        if existing:
            return existing
        pt = ProductTag(
            company_id=company_id,
            product_id=product_id,
            tag_id=tag_id,
        )
        self.db.add(pt)
        self.db.flush()
        return pt

    def remove(self, company_id: UUID, product_id: str, tag_id: str) -> bool:
        """Soft-delete the product↔tag join. Returns True if found and removed."""
        pt = (
            self.db.execute(
                select(ProductTag)
                .where(ProductTag.company_id == company_id)
                .where(ProductTag.product_id == product_id)
                .where(ProductTag.tag_id == tag_id)
                .where(ProductTag.is_deleted == False)  # noqa: E712
            )
            .scalars()
            .one_or_none()
        )
        if not pt:
            return False
        pt.is_deleted = True
        self.db.flush()
        return True

    def list_for_product(self, company_id: UUID, product_id: str) -> list[ProductTag]:
        """Return all active tag assignments for the given product."""
        return list[Any](
            self.db.execute(
                select(ProductTag)
                .where(ProductTag.company_id == company_id)
                .where(ProductTag.product_id == product_id)
                .where(ProductTag.is_deleted == False)  # noqa: E712
            )
            .scalars()
            .all()
        )

    def list_products_for_tag(self, company_id: UUID, tag_id: str) -> list[str]:
        """Return product_ids that carry the given tag."""
        rows = (
            self.db.execute(
                select(ProductTag.product_id)
                .where(ProductTag.company_id == company_id)
                .where(ProductTag.tag_id == tag_id)
                .where(ProductTag.is_deleted == False)  # noqa: E712
            )
            .scalars()
            .all()
        )
        return list[Any](rows)


# =============================================================================
# ProductCustomFieldValueRepository
# =============================================================================


class ProductCustomFieldValueRepository:
    """Data-access for per-product custom field values."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def set_value(
        self,
        company_id: UUID,
        product_id: str,
        field_key: str,
        value_text: str | None = None,
        value_number: str | None = None,
        value_bool: bool | None = None,
        value_json: dict[str, Any] | None = None,
    ) -> ProductCustomFieldValue:
        """Upsert a custom field value for the product."""
        existing = (
            self.db.execute(
                select(ProductCustomFieldValue)
                .where(ProductCustomFieldValue.company_id == company_id)
                .where(ProductCustomFieldValue.product_id == product_id)
                .where(ProductCustomFieldValue.field_key == field_key)
                .where(ProductCustomFieldValue.is_deleted == False)  # noqa: E712
            )
            .scalars()
            .one_or_none()
        )
        if existing:
            existing.value_text = value_text
            existing.value_number = value_number
            existing.value_bool = value_bool
            existing.value_json = value_json
            self.db.flush()
            return existing

        cfv = ProductCustomFieldValue(
            company_id=company_id,
            product_id=product_id,
            field_key=field_key,
            value_text=value_text,
            value_number=value_number,
            value_bool=value_bool,
            value_json=value_json,
        )
        self.db.add(cfv)
        self.db.flush()
        return cfv

    def get_value(
        self, company_id: UUID, product_id: str, field_key: str
    ) -> ProductCustomFieldValue | None:
        return (
            self.db.execute(
                select(ProductCustomFieldValue)
                .where(ProductCustomFieldValue.company_id == company_id)
                .where(ProductCustomFieldValue.product_id == product_id)
                .where(ProductCustomFieldValue.field_key == field_key)
                .where(ProductCustomFieldValue.is_deleted == False)  # noqa: E712
            )
            .scalars()
            .one_or_none()
        )

    def list_values(
        self, company_id: UUID, product_id: str
    ) -> list[ProductCustomFieldValue]:
        return list[Any](
            self.db.execute(
                select(ProductCustomFieldValue)
                .where(ProductCustomFieldValue.company_id == company_id)
                .where(ProductCustomFieldValue.product_id == product_id)
                .where(ProductCustomFieldValue.is_deleted == False)  # noqa: E712
                .order_by(ProductCustomFieldValue.field_key)
            )
            .scalars()
            .all()
        )

    def delete_value(self, company_id: UUID, product_id: str, field_key: str) -> bool:
        cfv = self.get_value(company_id, product_id, field_key)
        if not cfv:
            return False
        cfv.is_deleted = True
        self.db.flush()
        return True


# =============================================================================
# ProductInternalNoteRepository
# =============================================================================


class ProductInternalNoteRepository:
    """Data-access for append-only product internal notes."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add_note(
        self,
        company_id: UUID,
        product_id: str,
        note_text: str,
        author_id: str | None = None,
    ) -> ProductInternalNote:
        """Append a new note (no update or delete — audit trail)."""
        note = ProductInternalNote(
            company_id=company_id,
            product_id=product_id,
            note_text=note_text,
            author_id=author_id,
        )
        self.db.add(note)
        self.db.flush()
        return note

    def list_notes(
        self, company_id: UUID, product_id: str
    ) -> list[ProductInternalNote]:
        """Return all notes for the product, newest first."""
        return list[Any](
            self.db.execute(
                select(ProductInternalNote)
                .where(ProductInternalNote.company_id == company_id)
                .where(ProductInternalNote.product_id == product_id)
                .where(ProductInternalNote.is_deleted == False)  # noqa: E712
                .order_by(ProductInternalNote.created_at.desc())
            )
            .scalars()
            .all()
        )


# =============================================================================
# ImportJobRepository
# =============================================================================


class ImportJobRepository:
    """Data-access for bulk import job state tracking."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        company_id: UUID,
        file_name: str,
        total_rows: int = 0,
        created_by: UUID | None = None,
    ) -> ImportJob:
        job = ImportJob(
            company_id=company_id,
            file_name=file_name,
            total_rows=total_rows,
            status="PENDING",
            created_by=created_by,
        )
        self.db.add(job)
        self.db.flush()
        return job

    def get(self, company_id: UUID, job_id: UUID) -> ImportJob | None:
        return (
            self.db.execute(
                select(ImportJob)
                .where(ImportJob.company_id == company_id)
                .where(ImportJob.id == job_id)
                .where(ImportJob.is_deleted == False)  # noqa: E712
            )
            .scalars()
            .one_or_none()
        )

    def update_status(
        self,
        job: ImportJob,
        status: str,
        processed_rows: int | None = None,
        failed_rows: int | None = None,
        error_rows: list[Any] | None = None,
        error_message: str | None = None,
    ) -> ImportJob:
        job.status = status
        if processed_rows is not None:
            job.processed_rows = processed_rows
        if failed_rows is not None:
            job.failed_rows = failed_rows
        if error_rows is not None:
            job.error_rows = error_rows
        if error_message is not None:
            job.error_message = error_message
        self.db.flush()
        return job

    def list_for_company(self, company_id: UUID, limit: int = 50) -> list[ImportJob]:
        return list[Any](
            self.db.execute(
                select(ImportJob)
                .where(ImportJob.company_id == company_id)
                .where(ImportJob.is_deleted == False)  # noqa: E712
                .order_by(ImportJob.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

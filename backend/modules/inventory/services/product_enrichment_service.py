"""ProductEnrichmentService — application service for Phase 3 enrichment operations.

Covers: Tags, CustomFieldValues, InternalNotes, ProductImages.

Business rules:
  - Tag assignment is idempotent (assigning same tag twice is a no-op)
  - Notes are append-only — no edit or delete
  - Custom field values are upserted (set = create or update)
  - Image primary flag: setting one image primary clears others for the product
  - All operations are company-scoped

Spec ref: specs/005-inventory-management/spec.md §14, §35
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.inventory.exceptions import ProductNotFoundError, TagNotFoundError
from modules.inventory.models.product import Product, ProductImage
from modules.inventory.models.product_enrichment import (
    ProductCustomFieldValue,
    ProductInternalNote,
    ProductTag,
)
from modules.inventory.models.tag import Tag
from modules.inventory.repositories.product_enrichment_repository import (
    ProductCustomFieldValueRepository,
    ProductInternalNoteRepository,
    ProductTagRepository,
)
from modules.inventory.repositories.product_repository import ProductRepository

logger = logging.getLogger(__name__)


class ProductEnrichmentService:
    """Orchestrates enrichment operations (tags, custom fields, notes, images)."""

    def __init__(
        self,
        db: Session,
        product_repo: ProductRepository,
        tag_repo: ProductTagRepository,
        cfv_repo: ProductCustomFieldValueRepository,
        note_repo: ProductInternalNoteRepository,
    ) -> None:
        self.db = db
        self._product_repo = product_repo
        self._tag_repo = tag_repo
        self._cfv_repo = cfv_repo
        self._note_repo = note_repo

    # ── helpers ──────────────────────────────────────────────────────────────

    def _require_product(self, company_id: UUID, product_id: UUID) -> Product:
        try:
            return self._product_repo.get_by_id(company_id=company_id, id=product_id)
        except Exception:
            raise ProductNotFoundError()

    def _require_tag(self, company_id: UUID, tag_id: UUID) -> Tag:
        tag = (
            self.db.execute(
                select(Tag)
                .where(Tag.company_id == company_id)
                .where(Tag.id == tag_id)
                .where(Tag.is_deleted == False)  # noqa: E712
            )
            .scalars()
            .one_or_none()
        )
        if not tag:
            raise TagNotFoundError()
        return tag

    # ── Tags ─────────────────────────────────────────────────────────────────

    def assign_tag(
        self, company_id: UUID, product_id: UUID, tag_id: UUID
    ) -> ProductTag:
        self._require_product(company_id, product_id)
        self._require_tag(company_id, tag_id)
        pt = self._tag_repo.assign(
            company_id=company_id,
            product_id=str(product_id),
            tag_id=str(tag_id),
        )
        self.db.commit()
        logger.info("Tag %s assigned to product %s", tag_id, product_id)
        return pt

    def remove_tag(self, company_id: UUID, product_id: UUID, tag_id: UUID) -> bool:
        self._require_product(company_id, product_id)
        removed = self._tag_repo.remove(
            company_id=company_id,
            product_id=str(product_id),
            tag_id=str(tag_id),
        )
        self.db.commit()
        return removed

    def list_tags(self, company_id: UUID, product_id: UUID) -> list[ProductTag]:
        self._require_product(company_id, product_id)
        return self._tag_repo.list_for_product(
            company_id=company_id, product_id=str(product_id)
        )

    # ── Custom Field Values ───────────────────────────────────────────────────

    def set_custom_field_value(
        self,
        company_id: UUID,
        product_id: UUID,
        field_key: str,
        value_text: str | None = None,
        value_number: str | None = None,
        value_bool: bool | None = None,
        value_json: dict[str, Any] | None = None,
    ) -> ProductCustomFieldValue:
        self._require_product(company_id, product_id)
        cfv = self._cfv_repo.set_value(
            company_id=company_id,
            product_id=str(product_id),
            field_key=field_key,
            value_text=value_text,
            value_number=value_number,
            value_bool=value_bool,
            value_json=value_json,
        )
        self.db.commit()
        return cfv

    def list_custom_field_values(
        self, company_id: UUID, product_id: UUID
    ) -> list[ProductCustomFieldValue]:
        self._require_product(company_id, product_id)
        return self._cfv_repo.list_values(
            company_id=company_id, product_id=str(product_id)
        )

    def delete_custom_field_value(
        self, company_id: UUID, product_id: UUID, field_key: str
    ) -> bool:
        self._require_product(company_id, product_id)
        removed = self._cfv_repo.delete_value(
            company_id=company_id,
            product_id=str(product_id),
            field_key=field_key,
        )
        self.db.commit()
        return removed

    # ── Internal Notes ────────────────────────────────────────────────────────

    def add_note(
        self,
        company_id: UUID,
        product_id: UUID,
        note_text: str,
        author_id: UUID | None = None,
    ) -> ProductInternalNote:
        self._require_product(company_id, product_id)
        note = self._note_repo.add_note(
            company_id=company_id,
            product_id=str(product_id),
            note_text=note_text,
            author_id=str(author_id) if author_id else None,
        )
        self.db.commit()
        logger.info("Note added to product %s", product_id)
        return note

    def list_notes(
        self, company_id: UUID, product_id: UUID
    ) -> list[ProductInternalNote]:
        self._require_product(company_id, product_id)
        return self._note_repo.list_notes(
            company_id=company_id, product_id=str(product_id)
        )

    # ── Images ────────────────────────────────────────────────────────────────

    def add_image(
        self,
        company_id: UUID,
        product_id: UUID,
        s3_key: str,
        url: str,
        thumbnail_url: str | None = None,
        is_primary: bool = False,
        sort_order: int = 0,
        variant_id: UUID | None = None,
    ) -> ProductImage:
        """Store image metadata after upload to S3."""
        self._require_product(company_id, product_id)

        if is_primary:
            # Clear existing primary flag for this product
            existing_images = (
                self.db.execute(
                    select(ProductImage)
                    .where(ProductImage.company_id == company_id)
                    .where(ProductImage.product_id == str(product_id))
                    .where(ProductImage.is_primary == True)  # noqa: E712
                    .where(ProductImage.is_deleted == False)  # noqa: E712
                )
                .scalars()
                .all()
            )
            for img in existing_images:
                img.is_primary = False

        image = ProductImage(
            company_id=company_id,
            product_id=str(product_id),
            variant_id=str(variant_id) if variant_id else None,
            s3_key=s3_key,
            url=url,
            thumbnail_url=thumbnail_url,
            is_primary=is_primary,
            sort_order=sort_order,
        )
        self.db.add(image)
        self.db.commit()
        return image

    def list_images(self, company_id: UUID, product_id: UUID) -> list[ProductImage]:
        self._require_product(company_id, product_id)
        return list[Any](
            self.db.execute(
                select(ProductImage)
                .where(ProductImage.company_id == company_id)
                .where(ProductImage.product_id == str(product_id))
                .where(ProductImage.is_deleted == False)  # noqa: E712
                .order_by(ProductImage.sort_order, ProductImage.created_at)
            )
            .scalars()
            .all()
        )

    def delete_image(self, company_id: UUID, product_id: UUID, image_id: UUID) -> bool:
        image = (
            self.db.execute(
                select(ProductImage)
                .where(ProductImage.company_id == company_id)
                .where(ProductImage.product_id == str(product_id))
                .where(ProductImage.id == image_id)
                .where(ProductImage.is_deleted == False)  # noqa: E712
            )
            .scalars()
            .one_or_none()
        )
        if not image:
            return False
        image.is_deleted = True
        self.db.commit()
        return True

    def set_primary_image(
        self, company_id: UUID, product_id: UUID, image_id: UUID
    ) -> ProductImage | None:
        # Clear all primaries
        all_images = (
            self.db.execute(
                select(ProductImage)
                .where(ProductImage.company_id == company_id)
                .where(ProductImage.product_id == str(product_id))
                .where(ProductImage.is_deleted == False)  # noqa: E712
            )
            .scalars()
            .all()
        )
        target = None
        for img in all_images:
            img.is_primary = str(img.id) == str(image_id)
            if str(img.id) == str(image_id):
                target = img
        self.db.commit()
        return target

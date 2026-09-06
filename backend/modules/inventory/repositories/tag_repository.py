"""TagRepository — product tag data access.

Spec ref: specs/005-inventory-management/spec.md §14
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.inventory.models.tag import Tag


class TagRepository(BaseRepository[Tag]):
    """Data-access layer for ``inventory_tags`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=Tag)

    def get_by_name(self, company_id: UUID, name: str) -> Tag | None:
        """Return the tag with this name for the company (case-sensitive), or None."""
        stmt = (
            select(Tag)
            .where(Tag.company_id == company_id)
            .where(Tag.name == name)
            .where(Tag.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_all(self, company_id: UUID) -> list[Tag]:
        """Return all active tags for a company, ordered by name."""
        stmt = (
            select(Tag)
            .where(Tag.company_id == company_id)
            .where(Tag.is_deleted == False)  # noqa: E712
            .order_by(Tag.name)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_ids(self, company_id: UUID, ids: list[UUID]) -> list[Tag]:
        """Return tags matching the given UUIDs for the company."""
        if not ids:
            return []
        stmt = (
            select(Tag)
            .where(Tag.company_id == company_id)
            .where(Tag.id.in_(ids))
            .where(Tag.is_deleted == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())

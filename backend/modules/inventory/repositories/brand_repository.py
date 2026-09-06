"""BrandRepository — brand master data access.

Spec ref: specs/005-inventory-management/spec.md §14
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.inventory.models.brand import Brand


class BrandRepository(BaseRepository[Brand]):
    """Data-access layer for ``inventory_brands`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=Brand)

    def get_by_code(self, company_id: UUID, code: str) -> Brand | None:
        """Return the brand with this code for the company, or None."""
        stmt = (
            select(Brand)
            .where(Brand.company_id == company_id)
            .where(Brand.code == code)
            .where(Brand.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_active(self, company_id: UUID) -> list[Brand]:
        """Return all active brands for a company."""
        stmt = (
            select(Brand)
            .where(Brand.company_id == company_id)
            .where(Brand.status == "active")
            .where(Brand.is_deleted == False)  # noqa: E712
            .order_by(Brand.name)
        )
        return list(self.db.execute(stmt).scalars().all())

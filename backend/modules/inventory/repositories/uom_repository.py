"""UOMRepository and UOMConversionRepository — unit of measure data access.

Spec ref: specs/005-inventory-management/spec.md §14
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.inventory.models.uom import UOM, UOMConversion


class UOMRepository(BaseRepository[UOM]):
    """Data-access layer for ``inventory_uoms`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=UOM)

    def get_by_code(self, company_id: UUID, code: str) -> UOM | None:
        """Return the UOM with this code for the company, or None."""
        stmt = (
            select(UOM)
            .where(UOM.company_id == company_id)
            .where(UOM.code == code)
            .where(UOM.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_by_type(self, company_id: UUID, uom_type: str) -> list[UOM]:
        """Return all UOMs of a given type for a company."""
        stmt = (
            select(UOM)
            .where(UOM.company_id == company_id)
            .where(UOM.uom_type == uom_type)
            .where(UOM.is_deleted == False)  # noqa: E712
            .order_by(UOM.name)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_active(self, company_id: UUID) -> list[UOM]:
        """Return all active UOMs for a company."""
        stmt = (
            select(UOM)
            .where(UOM.company_id == company_id)
            .where(UOM.status == "active")
            .where(UOM.is_deleted == False)  # noqa: E712
            .order_by(UOM.uom_type, UOM.name)
        )
        return list(self.db.execute(stmt).scalars().all())


class UOMConversionRepository(BaseRepository[UOMConversion]):
    """Data-access layer for ``inventory_uom_conversions`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=UOMConversion)

    def get_by_pair(
        self, company_id: UUID, source_uom_id: UUID, target_uom_id: UUID
    ) -> UOMConversion | None:
        """Return the conversion record for a source→target pair, or None."""
        stmt = (
            select(UOMConversion)
            .where(UOMConversion.company_id == company_id)
            .where(UOMConversion.source_uom_id == str(source_uom_id))
            .where(UOMConversion.target_uom_id == str(target_uom_id))
            .where(UOMConversion.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_for_uom(self, company_id: UUID, uom_id: UUID) -> list[UOMConversion]:
        """Return all conversions where ``uom_id`` is source or target."""
        stmt = (
            select(UOMConversion)
            .where(UOMConversion.company_id == company_id)
            .where(UOMConversion.is_deleted == False)  # noqa: E712
            .where(
                (UOMConversion.source_uom_id == str(uom_id))
                | (UOMConversion.target_uom_id == str(uom_id))
            )
        )
        return list(self.db.execute(stmt).scalars().all())

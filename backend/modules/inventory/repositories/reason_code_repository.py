"""ReasonCodeRepository — adjustment reason code data access.

Spec ref: specs/005-inventory-management/spec.md §15 / §23
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.inventory.models.reason_code import ReasonCode


class ReasonCodeRepository(BaseRepository[ReasonCode]):
    """Data-access layer for ``inventory_reason_codes`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=ReasonCode)

    def get_by_code(self, company_id: UUID, code: str) -> ReasonCode | None:
        """Return the reason code with this code for the company, or None."""
        stmt = (
            select(ReasonCode)
            .where(ReasonCode.company_id == company_id)
            .where(ReasonCode.code == code)
            .where(ReasonCode.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_by_applies_to(
        self, company_id: UUID, applies_to: str, active_only: bool = True
    ) -> list[ReasonCode]:
        """Return reason codes filtered by ``applies_to`` type."""
        stmt = (
            select(ReasonCode)
            .where(ReasonCode.company_id == company_id)
            .where(ReasonCode.applies_to == applies_to)
            .where(ReasonCode.is_deleted == False)  # noqa: E712
        )
        if active_only:
            stmt = stmt.where(ReasonCode.is_active == True)  # noqa: E712
        stmt = stmt.order_by(ReasonCode.code)
        return list(self.db.execute(stmt).scalars().all())

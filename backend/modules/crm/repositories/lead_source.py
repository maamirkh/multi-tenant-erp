"""LeadSourceRepository — data access for the ``crm_lead_sources`` table.

Spec ref: specs/009-crm/plan.md §8.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.crm.models.lead_source import LeadSource


class LeadSourceRepository(BaseRepository[LeadSource]):
    """Data-access layer for ``crm_lead_sources``."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=LeadSource)

    def list_for_company(
        self, company_id: UUID, *, is_active: bool | None = None
    ) -> list[LeadSource]:
        """Return all (non-deleted) lead sources for a company, optionally
        filtered by ``is_active``."""
        stmt = (
            select(LeadSource)
            .where(LeadSource.company_id == company_id)
            .where(LeadSource.is_deleted == False)  # noqa: E712
        )
        if is_active is not None:
            stmt = stmt.where(LeadSource.is_active == is_active)
        stmt = stmt.order_by(LeadSource.name)
        return list(self.db.execute(stmt).scalars().all())

"""PipelineRepository — data access for the ``crm_pipelines`` table.

``get_default_for_company`` was pulled forward in Phase 4 as an explicit
dependency of ``CrmProvisioningService`` (T034); ``list_for_company`` is
Phase 5's own addition (T043) backing ``GET /crm/pipelines``.

Spec ref: specs/009-crm/plan.md §8.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.crm.models.pipeline import Pipeline


class PipelineRepository(BaseRepository[Pipeline]):
    """Data-access layer for ``crm_pipelines``."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=Pipeline)

    def get_default_for_company(self, company_id: UUID) -> Pipeline | None:
        """Return the company's default Pipeline (BR-008: at most one), or
        None if none has been provisioned yet."""
        stmt = (
            select(Pipeline)
            .where(Pipeline.company_id == company_id)
            .where(Pipeline.is_deleted == False)  # noqa: E712
            .where(Pipeline.is_default == True)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_for_company(self, company_id: UUID) -> list[Pipeline]:
        """Return all (non-deleted) Pipelines for a company, default first."""
        stmt = (
            select(Pipeline)
            .where(Pipeline.company_id == company_id)
            .where(Pipeline.is_deleted == False)  # noqa: E712
            .order_by(Pipeline.is_default.desc(), Pipeline.name)
        )
        return list(self.db.execute(stmt).scalars().all())

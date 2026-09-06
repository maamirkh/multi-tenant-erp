"""PipelineStageRepository — data access for the ``crm_pipeline_stages`` table.

``get_first_stage_for_pipeline`` was pulled forward in Phase 4 as an
explicit dependency of ``LeadConversionService`` (T037 step 4).
``count_open_opportunities_on_stage`` (BR-007 deactivation guard),
``list_for_pipeline``, and ``get_flagged_stage`` (win()/lose()'s
Closed-Won/Closed-Lost stage lookup, spec.md §17.2) are Phase 5's own
additions (T043).

Spec ref: specs/009-crm/plan.md §8, §12.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.crm.models.opportunity import Opportunity
from modules.crm.models.pipeline_stage import PipelineStage


class PipelineStageRepository(BaseRepository[PipelineStage]):
    """Data-access layer for ``crm_pipeline_stages``."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=PipelineStage)

    def get_first_stage_for_pipeline(
        self, pipeline_id: UUID, company_id: UUID
    ) -> PipelineStage | None:
        """Return the lowest-``sequence`` active stage of a Pipeline, or
        None if the Pipeline has no active stages."""
        stmt = (
            select(PipelineStage)
            .where(PipelineStage.company_id == company_id)
            .where(PipelineStage.pipeline_id == pipeline_id)
            .where(PipelineStage.is_deleted == False)  # noqa: E712
            .where(PipelineStage.is_active == True)  # noqa: E712
            .order_by(PipelineStage.sequence.asc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_for_pipeline(
        self, pipeline_id: UUID, company_id: UUID
    ) -> list[PipelineStage]:
        """Return all (non-deleted) stages of a Pipeline, in sequence order."""
        stmt = (
            select(PipelineStage)
            .where(PipelineStage.company_id == company_id)
            .where(PipelineStage.pipeline_id == pipeline_id)
            .where(PipelineStage.is_deleted == False)  # noqa: E712
            .order_by(PipelineStage.sequence.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_flagged_stage(
        self,
        pipeline_id: UUID,
        company_id: UUID,
        *,
        is_won_stage: bool = False,
        is_lost_stage: bool = False,
    ) -> PipelineStage | None:
        """Return the Pipeline's designated Closed-Won or Closed-Lost stage
        (spec.md §17.2 win()/lose()'s automatic stage placement), or None
        if the Pipeline has no such stage configured."""
        stmt = (
            select(PipelineStage)
            .where(PipelineStage.company_id == company_id)
            .where(PipelineStage.pipeline_id == pipeline_id)
            .where(PipelineStage.is_deleted == False)  # noqa: E712
        )
        if is_won_stage:
            stmt = stmt.where(PipelineStage.is_won_stage == True)  # noqa: E712
        if is_lost_stage:
            stmt = stmt.where(PipelineStage.is_lost_stage == True)  # noqa: E712
        return self.db.execute(stmt).scalars().one_or_none()

    def count_open_opportunities_on_stage(
        self, company_id: UUID, stage_id: UUID
    ) -> int:
        """Count OPEN Opportunities currently positioned on a stage — backs
        BR-007's deactivation guard (``PipelineService.update_stage()``)."""
        stmt = (
            select(func.count())
            .select_from(Opportunity)
            .where(Opportunity.company_id == company_id)
            .where(Opportunity.stage_id == stage_id)
            .where(Opportunity.status == "OPEN")
            .where(Opportunity.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalar_one()

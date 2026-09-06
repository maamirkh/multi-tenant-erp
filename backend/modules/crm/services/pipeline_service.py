"""PipelineService — application service for Pipeline/PipelineStage.

``create_pipeline()``/``create_stage()`` were pulled forward in Phase 4 as
an explicit dependency of ``CrmProvisioningService`` (T034).
``update_pipeline()`` and ``update_stage()`` (with its BR-007 deactivation
guard) are Phase 5's own additions (T044).

Spec ref: specs/009-crm/spec.md §18; plan.md §9, §12.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from modules.crm.exceptions import PipelineNotFoundError, PipelineStageInUseError
from modules.crm.models.pipeline import Pipeline
from modules.crm.models.pipeline_stage import PipelineStage
from modules.crm.repositories.pipeline import PipelineRepository
from modules.crm.repositories.pipeline_stage import PipelineStageRepository


class PipelineService:
    """Application service for Pipeline/PipelineStage management."""

    def __init__(
        self,
        db: Session,
        repo: PipelineRepository,
        stage_repo: PipelineStageRepository,
    ) -> None:
        self.db = db
        self._repo = repo
        self._stage_repo = stage_repo

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_pipeline(self, pipeline_id: UUID, company_id: UUID) -> Pipeline:
        return self._get_pipeline_or_raise(pipeline_id, company_id)

    def list_pipelines(self, company_id: UUID) -> list[Pipeline]:
        return self._repo.list_for_company(company_id)

    def list_stages(self, pipeline_id: UUID, company_id: UUID) -> list[PipelineStage]:
        self._get_pipeline_or_raise(pipeline_id, company_id)
        return self._stage_repo.list_for_pipeline(pipeline_id, company_id)

    def get_stage(self, stage_id: UUID, company_id: UUID) -> PipelineStage:
        return self._get_stage_or_raise(stage_id, company_id)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_pipeline(
        self,
        company_id: UUID,
        *,
        name: str,
        is_default: bool = False,
        is_active: bool = True,
        created_by: UUID | None = None,
    ) -> Pipeline:
        pipeline = Pipeline(
            company_id=company_id,
            name=name,
            is_default=is_default,
            is_active=is_active,
            created_by=created_by,
        )
        return self._repo.create(pipeline)

    def create_stage(
        self,
        pipeline_id: UUID,
        company_id: UUID,
        *,
        name: str,
        sequence: int,
        probability: int,
        is_won_stage: bool = False,
        is_lost_stage: bool = False,
        is_active: bool = True,
        created_by: UUID | None = None,
    ) -> PipelineStage:
        self._get_pipeline_or_raise(pipeline_id, company_id)
        stage = PipelineStage(
            company_id=company_id,
            pipeline_id=pipeline_id,
            name=name,
            sequence=sequence,
            probability=probability,
            is_won_stage=is_won_stage,
            is_lost_stage=is_lost_stage,
            is_active=is_active,
            created_by=created_by,
        )
        return self._stage_repo.create(stage)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_pipeline(
        self,
        pipeline_id: UUID,
        company_id: UUID,
        *,
        name: str | None = None,
        is_default: bool | None = None,
        is_active: bool | None = None,
    ) -> Pipeline:
        pipeline = self._get_pipeline_or_raise(pipeline_id, company_id)
        if name is not None:
            pipeline.name = name
        if is_default is not None:
            pipeline.is_default = is_default
        if is_active is not None:
            pipeline.is_active = is_active
        return self._repo.update(pipeline)

    def update_stage(
        self,
        stage_id: UUID,
        company_id: UUID,
        *,
        name: str | None = None,
        sequence: int | None = None,
        probability: int | None = None,
        is_won_stage: bool | None = None,
        is_lost_stage: bool | None = None,
        is_active: bool | None = None,
    ) -> PipelineStage:
        stage = self._get_stage_or_raise(stage_id, company_id)

        # BR-007: a stage cannot be deactivated while any OPEN Opportunity
        # currently occupies it.
        if is_active is False and stage.is_active:
            open_count = self._stage_repo.count_open_opportunities_on_stage(
                company_id, stage_id
            )
            if open_count > 0:
                raise PipelineStageInUseError(str(stage_id), open_count)

        if name is not None:
            stage.name = name
        if sequence is not None:
            stage.sequence = sequence
        if probability is not None:
            stage.probability = probability
        if is_won_stage is not None:
            stage.is_won_stage = is_won_stage
        if is_lost_stage is not None:
            stage.is_lost_stage = is_lost_stage
        if is_active is not None:
            stage.is_active = is_active
        return self._stage_repo.update(stage)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_pipeline_or_raise(self, pipeline_id: UUID, company_id: UUID) -> Pipeline:
        pipeline = self._repo.get_by_id_or_none(id=pipeline_id, company_id=company_id)
        if pipeline is None:
            raise PipelineNotFoundError(str(pipeline_id))
        return pipeline

    def _get_stage_or_raise(self, stage_id: UUID, company_id: UUID) -> PipelineStage:
        stage = self._stage_repo.get_by_id_or_none(id=stage_id, company_id=company_id)
        if stage is None:
            raise PipelineNotFoundError(str(stage_id))
        return stage

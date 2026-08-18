"""CrmProvisioningService — auto-provisions CRM defaults for a company.

Implementation-layer addition (plan.md §10.3 RECOMMENDATION) to satisfy
spec.md §54's assumption that a default Pipeline exists before Lead
conversion needs one. Provisions, idempotently:

  1. A default Pipeline (``is_default=true``) with a representative stage
     set (Qualification / Proposal Sent / Negotiation / Closed Won /
     Closed Lost), via ``PipelineService`` — not a second implementation
     of pipeline creation.
  2. A "CRM-Converted" Sales `CustomerCategory`, via Sales' existing
     ``CustomerCategoryService.create()`` (unmodified, reused) — needed
     because ``Customer.category_id`` is a required FK and Lead conversion
     has no natural category to supply otherwise (plan.md §10.3).

Both checks happen every call (idempotent) rather than being guarded by a
one-time flag, so a company that somehow lost its default Pipeline (never
expected in normal operation, but not structurally prevented) self-heals
on the next call rather than permanently blocking conversion.

Spec ref: specs/009-crm/spec.md §54; plan.md §10.3, §33 R-12.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from modules.crm.models.pipeline import Pipeline
from modules.crm.repositories.pipeline import PipelineRepository
from modules.crm.services.pipeline_service import PipelineService
from modules.sales.models.master import CustomerCategory
from modules.sales.repositories.master import CustomerCategoryRepository
from modules.sales.services.master_data_service import CustomerCategoryService

CRM_CONVERTED_CATEGORY_CODE = "CRM-CONVERTED"

#: (name, sequence, probability, is_won_stage, is_lost_stage)
_DEFAULT_STAGES: tuple[tuple[str, int, int, bool, bool], ...] = (
    ("Qualification", 1, 20, False, False),
    ("Proposal Sent", 2, 50, False, False),
    ("Negotiation", 3, 75, False, False),
    ("Closed Won", 4, 100, True, False),
    ("Closed Lost", 5, 0, False, True),
)


@dataclass(frozen=True)
class ProvisioningResult:
    pipeline: Pipeline
    category: CustomerCategory


class CrmProvisioningService:
    """Auto-provisions the default Pipeline and CRM-Converted Customer
    Category a company needs before Lead conversion can run."""

    def __init__(
        self,
        db: Session,
        pipeline_repo: PipelineRepository,
        pipeline_service: PipelineService,
        category_repo: CustomerCategoryRepository,
        category_service: CustomerCategoryService,
    ) -> None:
        self.db = db
        self._pipeline_repo = pipeline_repo
        self._pipeline_service = pipeline_service
        self._category_repo = category_repo
        self._category_service = category_service

    def ensure_defaults(
        self, company_id: UUID, *, created_by: UUID | None = None
    ) -> ProvisioningResult:
        """Idempotent — calling this twice for the same company produces
        exactly one default Pipeline and one CRM-Converted category."""
        pipeline = self._ensure_default_pipeline(company_id, created_by)
        category = self._ensure_crm_converted_category(company_id, created_by)
        return ProvisioningResult(pipeline=pipeline, category=category)

    def _ensure_default_pipeline(
        self, company_id: UUID, created_by: UUID | None
    ) -> Pipeline:
        existing = self._pipeline_repo.get_default_for_company(company_id)
        if existing is not None:
            return existing

        pipeline = self._pipeline_service.create_pipeline(
            company_id,
            name="Standard Sales Pipeline",
            is_default=True,
            created_by=created_by,
        )
        for name, sequence, probability, is_won, is_lost in _DEFAULT_STAGES:
            self._pipeline_service.create_stage(
                pipeline.id,
                company_id,
                name=name,
                sequence=sequence,
                probability=probability,
                is_won_stage=is_won,
                is_lost_stage=is_lost,
                created_by=created_by,
            )
        return pipeline

    def _ensure_crm_converted_category(
        self, company_id: UUID, created_by: UUID | None
    ) -> CustomerCategory:
        existing = self._category_repo.get_by_code(
            company_id=company_id, code=CRM_CONVERTED_CATEGORY_CODE
        )
        if existing is not None:
            return existing

        return self._category_service.create(
            company_id=company_id,
            code=CRM_CONVERTED_CATEGORY_CODE,
            name="CRM-Converted",
            description=(
                "Auto-provisioned default category for customers created "
                "via CRM lead conversion."
            ),
            created_by=created_by,
        )

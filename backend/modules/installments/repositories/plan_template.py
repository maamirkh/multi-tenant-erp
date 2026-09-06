"""Repository for Installments plan templates.

Spec ref: specs/010-installments/data-model.md "InstallmentPlanTemplate".
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.installments.models.plan_template import InstallmentPlanTemplate


class InstallmentPlanTemplateRepository(BaseRepository[InstallmentPlanTemplate]):
    """Data-access layer for ``installment_plan_templates``."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=InstallmentPlanTemplate)

    def get_by_name(
        self, company_id: UUID, name: str
    ) -> InstallmentPlanTemplate | None:
        """Return the active (non-deleted) template with this name, or
        ``None`` — used to enforce unique-name-per-company at the service
        layer before the DB partial unique index provides the final
        backstop."""
        stmt = (
            select(InstallmentPlanTemplate)
            .where(InstallmentPlanTemplate.company_id == company_id)
            .where(InstallmentPlanTemplate.name == name)
            .where(InstallmentPlanTemplate.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_active(self, company_id: UUID) -> list[InstallmentPlanTemplate]:
        """Return every active (``is_active=True``, non-deleted) template
        for this company — excludes deactivated templates from the
        template-picker (FR-INST-013)."""
        stmt = (
            select(InstallmentPlanTemplate)
            .where(InstallmentPlanTemplate.company_id == company_id)
            .where(InstallmentPlanTemplate.is_active == True)  # noqa: E712
            .where(InstallmentPlanTemplate.is_deleted == False)  # noqa: E712
            .order_by(InstallmentPlanTemplate.name)
        )
        return list(self.db.execute(stmt).scalars().all())

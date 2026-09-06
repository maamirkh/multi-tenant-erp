"""Repository for Installments tenant/branch configuration.

Extends ``BaseRepository`` with ``get_effective_config`` — branch
override then company-fallback resolution (plan.md §18: ``branch_id``
reserved on ``InstallmentConfiguration`` for future branch-scoped policy,
no ``Branch`` entity exists platform-wide yet).

Spec ref: specs/010-installments/data-model.md "InstallmentConfiguration".
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.installments.models.configuration import InstallmentConfiguration


class InstallmentConfigurationRepository(BaseRepository[InstallmentConfiguration]):
    """Data-access layer for ``installment_configurations``."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=InstallmentConfiguration)

    def get_company_default(self, company_id: UUID) -> InstallmentConfiguration | None:
        """Return the company-level default row (``branch_id IS NULL``), or
        ``None`` if the company has never configured Installments."""
        stmt = (
            select(InstallmentConfiguration)
            .where(InstallmentConfiguration.company_id == company_id)
            .where(InstallmentConfiguration.branch_id.is_(None))
            .where(InstallmentConfiguration.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_branch_override(
        self, company_id: UUID, branch_id: UUID
    ) -> InstallmentConfiguration | None:
        """Return the branch-specific override row, or ``None`` if this
        branch has no override (company default applies instead)."""
        stmt = (
            select(InstallmentConfiguration)
            .where(InstallmentConfiguration.company_id == company_id)
            .where(InstallmentConfiguration.branch_id == branch_id)
            .where(InstallmentConfiguration.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_effective_config(
        self, company_id: UUID, branch_id: UUID | None
    ) -> InstallmentConfiguration | None:
        """Resolve the effective configuration for ``branch_id``: a
        branch-specific override wins if one exists, otherwise the
        company-level default row, otherwise ``None`` (never configured).
        """
        if branch_id is not None:
            override = self.get_branch_override(company_id, branch_id)
            if override is not None:
                return override
        return self.get_company_default(company_id)

"""Repository for Reports feature flag overrides.

Mirrors ``CrmFeatureFlagRepository``/``InstallmentsFeatureFlagRepository``
exactly.

Spec ref: specs/011-reports-analytics/plan.md §12.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.reports.models.feature_flag import ReportsFeatureFlag


class ReportsFeatureFlagRepository(BaseRepository[ReportsFeatureFlag]):
    """Data-access layer for ``reports_feature_flags`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=ReportsFeatureFlag)

    def get_by_key(self, company_id: UUID, flag_key: str) -> ReportsFeatureFlag | None:
        """Return the feature flag override for this company and key, or None."""
        stmt = (
            select(ReportsFeatureFlag)
            .where(ReportsFeatureFlag.company_id == company_id)
            .where(ReportsFeatureFlag.flag_key == flag_key)
            .where(ReportsFeatureFlag.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def upsert(
        self,
        company_id: UUID,
        flag_key: str,
        is_enabled: bool,
        created_by: UUID | None = None,
        description: str | None = None,
    ) -> ReportsFeatureFlag:
        """Create or update a feature flag override.

        If an override already exists for (company_id, flag_key) it is
        updated in-place. Otherwise a new record is created.
        """
        existing = self.get_by_key(company_id=company_id, flag_key=flag_key)
        if existing is not None:
            existing.is_enabled = is_enabled
            if description is not None:
                existing.description = description
            return self.update(existing)

        flag = ReportsFeatureFlag(
            company_id=company_id,
            flag_key=flag_key,
            is_enabled=is_enabled,
            created_by=created_by,
            description=description,
        )
        return self.create(flag)

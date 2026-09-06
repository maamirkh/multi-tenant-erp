"""Repository for Installments feature flag overrides.

Mirrors ``CrmFeatureFlagRepository`` exactly.

Spec ref: specs/010-installments/plan.md §15.4.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.installments.models.feature_flag import InstallmentsFeatureFlag


class InstallmentsFeatureFlagRepository(BaseRepository[InstallmentsFeatureFlag]):
    """Data-access layer for ``installments_feature_flags`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=InstallmentsFeatureFlag)

    def get_by_key(
        self, company_id: UUID, flag_key: str
    ) -> InstallmentsFeatureFlag | None:
        """Return the feature flag override for this company and key, or None."""
        stmt = (
            select(InstallmentsFeatureFlag)
            .where(InstallmentsFeatureFlag.company_id == company_id)
            .where(InstallmentsFeatureFlag.flag_key == flag_key)
            .where(InstallmentsFeatureFlag.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def upsert(
        self,
        company_id: UUID,
        flag_key: str,
        is_enabled: bool,
        created_by: UUID | None = None,
        description: str | None = None,
    ) -> InstallmentsFeatureFlag:
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

        flag = InstallmentsFeatureFlag(
            company_id=company_id,
            flag_key=flag_key,
            is_enabled=is_enabled,
            created_by=created_by,
            description=description,
        )
        return self.create(flag)

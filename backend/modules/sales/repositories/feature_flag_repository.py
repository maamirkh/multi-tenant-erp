"""Repository for sales feature flag overrides.

Extends ``BaseSalesRepository`` with feature-flag-specific queries:
  - ``get_by_key``          — fetch a single flag override by (company_id, flag_key)
  - ``upsert``              — create-or-update a flag override
  - ``get_all_for_company`` — fetch all overrides for a company

Spec ref: specs/007-sales-management/spec.md §30 Feature Matrix
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.sales.models.feature_flag import SalesFeatureFlag
from modules.sales.repositories import BaseSalesRepository


class SalesFeatureFlagRepository(BaseSalesRepository[SalesFeatureFlag]):
    """Data-access layer for ``sales_feature_flags`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SalesFeatureFlag)

    def get_by_key(self, company_id: UUID, flag_key: str) -> SalesFeatureFlag | None:
        """Return the feature flag override for this company and key, or None."""
        stmt = (
            select(SalesFeatureFlag)
            .where(SalesFeatureFlag.company_id == company_id)
            .where(SalesFeatureFlag.flag_key == flag_key)
            .where(SalesFeatureFlag.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_all_for_company(self, company_id: UUID) -> list[SalesFeatureFlag]:
        """Return all active feature flag overrides for a company."""
        stmt = (
            select(SalesFeatureFlag)
            .where(SalesFeatureFlag.company_id == company_id)
            .where(SalesFeatureFlag.is_deleted == False)  # noqa: E712
            .order_by(SalesFeatureFlag.flag_key)
        )
        return list(self.db.execute(stmt).scalars().all())

    def upsert(
        self,
        company_id: UUID,
        flag_key: str,
        is_enabled: bool,
        created_by: UUID | None = None,
        description: str | None = None,
    ) -> SalesFeatureFlag:
        """Create or update a feature flag override.

        If an override already exists for (company_id, flag_key) it is updated
        in-place. Otherwise a new record is created.
        """
        existing = self.get_by_key(company_id=company_id, flag_key=flag_key)
        if existing is not None:
            existing.is_enabled = is_enabled
            if description is not None:
                existing.description = description
            return self.update(existing)

        flag = SalesFeatureFlag(
            company_id=company_id,
            flag_key=flag_key,
            is_enabled=is_enabled,
            created_by=created_by,
            description=description,
        )
        return self.create(flag)

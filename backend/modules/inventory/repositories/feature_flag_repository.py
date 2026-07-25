"""Repository for inventory feature flag overrides.

Extends ``BaseRepository`` with feature-flag-specific queries:
  - ``get_by_key``       — fetch a single flag override by (company_id, flag_key)
  - ``upsert``           — create-or-update a flag override
  - ``get_all_for_company`` — fetch all overrides for a company

Spec ref: specs/005-inventory-management/spec.md §27 Feature Matrix
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.inventory.models.feature_flag import InventoryFeatureFlag


class FeatureFlagRepository(BaseRepository[InventoryFeatureFlag]):
    """Data-access layer for ``inventory_feature_flags`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=InventoryFeatureFlag)

    def get_by_key(
        self, company_id: UUID, flag_key: str
    ) -> InventoryFeatureFlag | None:
        """Return the feature flag override for this company and key, or None.

        Args:
            company_id: Tenant identifier.
            flag_key:   Flag key (e.g. ``"inventory.product_variants"``).

        Returns:
            The override record, or ``None`` if no override is configured.
        """
        stmt = (
            select(InventoryFeatureFlag)
            .where(InventoryFeatureFlag.company_id == company_id)
            .where(InventoryFeatureFlag.flag_key == flag_key)
            .where(InventoryFeatureFlag.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_all_for_company(self, company_id: UUID) -> list[InventoryFeatureFlag]:
        """Return all active feature flag overrides for a company.

        Args:
            company_id: Tenant identifier.

        Returns:
            List of all override records for this company (active only).
        """
        stmt = (
            select(InventoryFeatureFlag)
            .where(InventoryFeatureFlag.company_id == company_id)
            .where(InventoryFeatureFlag.is_deleted == False)  # noqa: E712
            .order_by(InventoryFeatureFlag.flag_key)
        )
        return list(self.db.execute(stmt).scalars().all())

    def upsert(
        self,
        company_id: UUID,
        flag_key: str,
        is_enabled: bool,
        created_by: UUID | None = None,
        description: str | None = None,
    ) -> InventoryFeatureFlag:
        """Create or update a feature flag override.

        If an override already exists for (company_id, flag_key) it is updated
        in-place. Otherwise a new record is created.

        Args:
            company_id:  Tenant identifier.
            flag_key:    Flag key (e.g. ``"inventory.product_variants"``).
            is_enabled:  New enabled state.
            created_by:  UUID of the acting user (for audit trail).
            description: Optional override reason.

        Returns:
            The created or updated ``InventoryFeatureFlag`` instance.
        """
        existing = self.get_by_key(company_id=company_id, flag_key=flag_key)
        if existing is not None:
            existing.is_enabled = is_enabled
            if description is not None:
                existing.description = description
            return self.update(existing)

        flag = InventoryFeatureFlag(
            company_id=company_id,
            flag_key=flag_key,
            is_enabled=is_enabled,
            created_by=created_by,
            description=description,
        )
        return self.create(flag)

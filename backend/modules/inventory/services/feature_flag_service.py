"""FeatureFlagService — company-scoped inventory feature flag management.

Business rules:
  1. When no override exists for a (company_id, flag_key) pair, the system
     default (``FeatureFlagDefinition.default_enabled``) applies.
  2. A company may override any flag in ``INVENTORY_FEATURE_FLAGS``.
  3. Requesting a flag with an unknown key raises ``ValueError``.
  4. All mutations are auditable — ``created_by`` is recorded on the row.

Spec ref: specs/005-inventory-management/spec.md §27 Feature Matrix
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from modules.inventory.constants import (
    INVENTORY_FEATURE_FLAGS,
    INVENTORY_FLAG_BY_KEY,
)
from modules.inventory.repositories.feature_flag_repository import FeatureFlagRepository

logger = logging.getLogger(__name__)


class FeatureFlagService:
    """Service layer for inventory feature flag management.

    Args:
        db:          SQLAlchemy session (used only to wire the repository).
        flag_repo:   ``FeatureFlagRepository`` instance (injected).
    """

    def __init__(self, db: Session, flag_repo: FeatureFlagRepository) -> None:
        self.db = db
        self._flag_repo = flag_repo

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def is_enabled(self, company_id: UUID, flag_key: str) -> bool:
        """Return True if the feature is enabled for this company.

        Resolution order:
          1. Company-specific override in ``inventory_feature_flags`` table.
          2. System default from ``INVENTORY_FLAG_BY_KEY``.
          3. ``False`` if the key is entirely unknown (defensive default).

        Args:
            company_id: Tenant identifier.
            flag_key:   Feature flag key (e.g. ``"inventory.product_variants"``).

        Returns:
            ``True`` if the feature is active for this company.
        """
        override = self._flag_repo.get_by_key(company_id=company_id, flag_key=flag_key)
        if override is not None:
            return override.is_enabled

        definition = INVENTORY_FLAG_BY_KEY.get(flag_key)
        if definition is None:
            logger.warning("Unknown feature flag key requested: '%s'", flag_key)
            return False

        return definition.default_enabled

    def get_all(self, company_id: UUID) -> list[dict[str, object]]:
        """Return a merged list of all flags with their effective state.

        For each known flag key, the company override (if any) takes
        precedence over the system default.

        Args:
            company_id: Tenant identifier.

        Returns:
            List of dicts with keys: ``flag_key``, ``label``, ``description``,
            ``is_enabled``, ``is_overridden``.
        """
        overrides_by_key = {
            f.flag_key: f
            for f in self._flag_repo.get_all_for_company(company_id=company_id)
        }

        result = []
        for definition in INVENTORY_FEATURE_FLAGS:
            override = overrides_by_key.get(definition.key)
            is_enabled = override.is_enabled if override else definition.default_enabled
            result.append(
                {
                    "flag_key": definition.key,
                    "label": definition.label,
                    "description": definition.description,
                    "is_enabled": is_enabled,
                    "is_overridden": override is not None,
                    "default_enabled": definition.default_enabled,
                }
            )

        return result

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def enable(
        self,
        company_id: UUID,
        flag_key: str,
        actor_id: UUID | None = None,
        description: str | None = None,
    ) -> None:
        """Enable a feature flag for a company.

        Args:
            company_id:  Tenant identifier.
            flag_key:    Feature flag key to enable.
            actor_id:    UUID of the user performing the action (audit).
            description: Optional override reason.

        Raises:
            ValueError: If ``flag_key`` is not a recognised inventory flag.
        """
        self._validate_key(flag_key)
        self._flag_repo.upsert(
            company_id=company_id,
            flag_key=flag_key,
            is_enabled=True,
            created_by=actor_id,
            description=description,
        )
        logger.info(
            "Feature flag enabled: key=%s company=%s actor=%s",
            flag_key,
            company_id,
            actor_id,
        )

    def disable(
        self,
        company_id: UUID,
        flag_key: str,
        actor_id: UUID | None = None,
        description: str | None = None,
    ) -> None:
        """Disable a feature flag for a company.

        Args:
            company_id:  Tenant identifier.
            flag_key:    Feature flag key to disable.
            actor_id:    UUID of the user performing the action (audit).
            description: Optional override reason.

        Raises:
            ValueError: If ``flag_key`` is not a recognised inventory flag.
        """
        self._validate_key(flag_key)
        self._flag_repo.upsert(
            company_id=company_id,
            flag_key=flag_key,
            is_enabled=False,
            created_by=actor_id,
            description=description,
        )
        logger.info(
            "Feature flag disabled: key=%s company=%s actor=%s",
            flag_key,
            company_id,
            actor_id,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate_key(self, flag_key: str) -> None:
        if flag_key not in INVENTORY_FLAG_BY_KEY:
            raise ValueError(
                f"Unknown inventory feature flag key: '{flag_key}'. "
                f"Valid keys: {sorted(INVENTORY_FLAG_BY_KEY)}"
            )

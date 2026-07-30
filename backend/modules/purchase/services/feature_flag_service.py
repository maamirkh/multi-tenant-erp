"""PurchaseFeatureFlagService — company-scoped purchase feature flag management.

Business rules:
  1. When no override exists for a (company_id, flag_key) pair, the system
     default (``FeatureFlagDefinition.default_enabled``) applies.
  2. A company may override any flag in ``PURCHASE_FEATURE_FLAGS``.
  3. Requesting a flag with an unknown key raises ``ValueError``.
  4. All mutations are auditable — ``created_by`` is recorded on the row.

Spec ref: specs/006-purchase-management/spec.md §29 Feature Matrix
Research ref: specs/006-purchase-management/research.md §Decision 7
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from modules.purchase.constants import (
    PURCHASE_FEATURE_FLAGS,
    PURCHASE_FLAG_BY_KEY,
)
from modules.purchase.repositories.feature_flag_repository import (
    PurchaseFeatureFlagRepository,
)

logger = logging.getLogger(__name__)


class PurchaseFeatureFlagService:
    """Service layer for purchase feature flag management.

    Args:
        db:          SQLAlchemy session.
        flag_repo:   ``PurchaseFeatureFlagRepository`` instance (injected).
    """

    def __init__(self, db: Session, flag_repo: PurchaseFeatureFlagRepository) -> None:
        self.db = db
        self._flag_repo = flag_repo

    def is_enabled(self, company_id: UUID, flag_key: str) -> bool:
        """Return True if the feature is enabled for this company.

        Resolution order:
          1. Company-specific override in ``purchase_feature_flags`` table.
          2. System default from ``PURCHASE_FLAG_BY_KEY``.
          3. ``False`` if the key is entirely unknown (defensive default).
        """
        override = self._flag_repo.get_by_key(company_id=company_id, flag_key=flag_key)
        if override is not None:
            return override.is_enabled

        definition = PURCHASE_FLAG_BY_KEY.get(flag_key)
        if definition is None:
            logger.warning(
                "Unknown purchase feature flag key requested: '%s'", flag_key
            )
            return False

        return definition.default_enabled

    def get_all(self, company_id: UUID) -> list[dict[str, object]]:
        """Return a merged list of all purchase flags with their effective state."""
        overrides_by_key = {
            f.flag_key: f
            for f in self._flag_repo.get_all_for_company(company_id=company_id)
        }

        result = []
        for definition in PURCHASE_FEATURE_FLAGS:
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

    def enable(
        self,
        company_id: UUID,
        flag_key: str,
        actor_id: UUID | None = None,
        description: str | None = None,
    ) -> None:
        """Enable a purchase feature flag for a company."""
        self._validate_key(flag_key)
        self._flag_repo.upsert(
            company_id=company_id,
            flag_key=flag_key,
            is_enabled=True,
            created_by=actor_id,
            description=description,
        )
        logger.info(
            "Purchase feature flag enabled: key=%s company=%s actor=%s",
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
        """Disable a purchase feature flag for a company."""
        self._validate_key(flag_key)
        self._flag_repo.upsert(
            company_id=company_id,
            flag_key=flag_key,
            is_enabled=False,
            created_by=actor_id,
            description=description,
        )
        logger.info(
            "Purchase feature flag disabled: key=%s company=%s actor=%s",
            flag_key,
            company_id,
            actor_id,
        )

    def _validate_key(self, flag_key: str) -> None:
        if flag_key not in PURCHASE_FLAG_BY_KEY:
            raise ValueError(
                f"Unknown purchase feature flag key: '{flag_key}'. "
                f"Valid keys: {sorted(PURCHASE_FLAG_BY_KEY)}"
            )

"""InstallmentsFeatureFlagService — company-scoped Installments module gate.

Mirrors ``CrmFeatureFlagService`` exactly, minus its optional provisioning
step (no equivalent "ensure default records" concept exists for
Installments — plan.md §15.4 names only ``is_enabled()``/``enable()``/
``disable()``). When no override row exists for a company, the module
defaults to **disabled**.

Spec ref: specs/010-installments/plan.md §15.4.
"""

from __future__ import annotations

import logging
from uuid import UUID

from modules.installments.repositories.feature_flag import (
    InstallmentsFeatureFlagRepository,
)

logger = logging.getLogger(__name__)

INSTALLMENTS_ENABLED_FLAG_KEY = "feature.installments.enabled"


class InstallmentsFeatureFlagService:
    """Service layer for the Installments module feature flag."""

    def __init__(self, flag_repo: InstallmentsFeatureFlagRepository) -> None:
        self._flag_repo = flag_repo

    def is_enabled(self, company_id: UUID) -> bool:
        """Return True if the Installments module is enabled for this
        company. Defaults to ``False`` when no override row exists yet."""
        override = self._flag_repo.get_by_key(
            company_id=company_id, flag_key=INSTALLMENTS_ENABLED_FLAG_KEY
        )
        return override.is_enabled if override is not None else False

    def enable(
        self,
        company_id: UUID,
        actor_id: UUID | None = None,
        description: str | None = None,
    ) -> None:
        """Enable the Installments module for a company."""
        self._flag_repo.upsert(
            company_id=company_id,
            flag_key=INSTALLMENTS_ENABLED_FLAG_KEY,
            is_enabled=True,
            created_by=actor_id,
            description=description,
        )
        logger.info(
            "Installments feature flag enabled: company=%s actor=%s",
            company_id,
            actor_id,
        )

    def disable(
        self,
        company_id: UUID,
        actor_id: UUID | None = None,
        description: str | None = None,
    ) -> None:
        """Disable the Installments module for a company. Existing
        contracts remain fully serviceable (FR-INST-356) — this flag only
        gates ORIGINATION-class operations."""
        self._flag_repo.upsert(
            company_id=company_id,
            flag_key=INSTALLMENTS_ENABLED_FLAG_KEY,
            is_enabled=False,
            created_by=actor_id,
            description=description,
        )
        logger.info(
            "Installments feature flag disabled: company=%s actor=%s",
            company_id,
            actor_id,
        )

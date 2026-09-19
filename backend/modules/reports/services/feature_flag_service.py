"""ReportsFeatureFlagService — company-scoped Reports module gate.

Mirrors ``CrmFeatureFlagService``/``InstallmentsFeatureFlagService``
exactly (module-wide toggle only, no per-sub-feature flags). When no
override row exists for a company, the module defaults to **disabled**
(spec §18/FR-RPT-255).

Spec ref: specs/011-reports-analytics/plan.md §12.
"""

from __future__ import annotations

import logging
from uuid import UUID

from modules.reports.repositories.feature_flag import ReportsFeatureFlagRepository

logger = logging.getLogger(__name__)

REPORTS_ENABLED_FLAG_KEY = "feature.reports.enabled"


class ReportsFeatureFlagService:
    """Service layer for the Reports module feature flag."""

    def __init__(self, flag_repo: ReportsFeatureFlagRepository) -> None:
        self._flag_repo = flag_repo

    def is_enabled(self, company_id: UUID) -> bool:
        """Return True if the Reports module is enabled for this company.
        Defaults to ``False`` when no override row exists yet."""
        override = self._flag_repo.get_by_key(
            company_id=company_id, flag_key=REPORTS_ENABLED_FLAG_KEY
        )
        return override.is_enabled if override is not None else False

    def enable(
        self,
        company_id: UUID,
        actor_id: UUID | None = None,
        description: str | None = None,
    ) -> None:
        """Enable the Reports module for a company."""
        self._flag_repo.upsert(
            company_id=company_id,
            flag_key=REPORTS_ENABLED_FLAG_KEY,
            is_enabled=True,
            created_by=actor_id,
            description=description,
        )
        logger.info(
            "Reports feature flag enabled: company=%s actor=%s",
            company_id,
            actor_id,
        )

    def disable(
        self,
        company_id: UUID,
        actor_id: UUID | None = None,
        description: str | None = None,
    ) -> None:
        """Disable the Reports module for a company."""
        self._flag_repo.upsert(
            company_id=company_id,
            flag_key=REPORTS_ENABLED_FLAG_KEY,
            is_enabled=False,
            created_by=actor_id,
            description=description,
        )
        logger.info(
            "Reports feature flag disabled: company=%s actor=%s",
            company_id,
            actor_id,
        )

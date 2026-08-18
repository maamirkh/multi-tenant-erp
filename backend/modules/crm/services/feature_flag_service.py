"""CrmFeatureFlagService — company-scoped CRM module gate.

Business rules:
  1. When no override row exists for a company, the module defaults to
     **disabled** (unlike Sales/Accounting/Inventory's per-capability
     registry, CRM has exactly one flag and no "system default enabled"
     concept — a brand-new module ships off by default).
  2. All mutations are auditable — ``created_by`` is recorded on the row.
  3. ``enable()`` synchronously triggers ``CrmProvisioningService.ensure_defaults()``
     (tasks.md T036, plan.md §10.3 / §33 R-12) — a missing default Pipeline
     or CRM-Converted category becomes a visible failure at flag-enable
     time, not a confusing error buried inside a later Lead-conversion
     transaction. ``provisioning_service`` is optional (defaults to
     ``None``) purely so this service's own unit tests (predating Phase 4)
     can keep constructing it without a full provisioning dependency
     chain; the real DI factory (``dependencies.py``) always supplies one.

Deliberately simpler than ``SalesFeatureFlagService``/
``AccountingFeatureFlagService``: ``is_enabled(company_id)`` takes no
``flag_key`` argument because CRM has exactly one module-wide gate
(``constants.CRM_ENABLED_FLAG_KEY``), not a registry of independently
togglable capabilities. See plan.md §17.2/§21.5.

Spec ref: specs/009-crm/plan.md §17 (Feature Flag), §10.3.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.orm import Session

from modules.crm.constants import CRM_ENABLED_FLAG_KEY
from modules.crm.repositories.feature_flag_repository import CrmFeatureFlagRepository

if TYPE_CHECKING:
    from modules.crm.services.provisioning_service import CrmProvisioningService

logger = logging.getLogger(__name__)


class CrmFeatureFlagService:
    """Service layer for the CRM module feature flag.

    Args:
        db:                   SQLAlchemy session.
        flag_repo:            ``CrmFeatureFlagRepository`` instance (injected).
        provisioning_service: ``CrmProvisioningService`` instance (injected).
                               Triggered synchronously by ``enable()``.
    """

    def __init__(
        self,
        db: Session,
        flag_repo: CrmFeatureFlagRepository,
        provisioning_service: CrmProvisioningService | None = None,
    ) -> None:
        self.db = db
        self._flag_repo = flag_repo
        self._provisioning_service = provisioning_service

    def is_enabled(self, company_id: UUID) -> bool:
        """Return True if the CRM module is enabled for this company.

        Defaults to ``False`` when no override row exists yet.
        """
        override = self._flag_repo.get_by_key(
            company_id=company_id, flag_key=CRM_ENABLED_FLAG_KEY
        )
        return override.is_enabled if override is not None else False

    def enable(
        self,
        company_id: UUID,
        actor_id: UUID | None = None,
        description: str | None = None,
    ) -> None:
        """Enable the CRM module for a company, then synchronously
        provision its default Pipeline and CRM-Converted Customer
        Category (tasks.md T036).

        Not wrapped in a single transaction with the flag upsert:
        ``BaseRepository`` (and every repository built on it, across this
        entire codebase) already commits per call — genuine single-
        transaction semantics here would mean deviating from that
        established, codebase-wide convention for a flow that, unlike
        Lead conversion, has no duplicate-creation risk (provisioning is
        itself idempotent). The goal this satisfies — a missing default
        surfaces immediately at enable-time, not buried inside a later
        conversion — holds regardless, since both calls happen
        synchronously within the same request.
        """
        self._flag_repo.upsert(
            company_id=company_id,
            flag_key=CRM_ENABLED_FLAG_KEY,
            is_enabled=True,
            created_by=actor_id,
            description=description,
        )
        if self._provisioning_service is not None:
            self._provisioning_service.ensure_defaults(company_id, created_by=actor_id)
        logger.info(
            "CRM feature flag enabled: company=%s actor=%s", company_id, actor_id
        )

    def disable(
        self,
        company_id: UUID,
        actor_id: UUID | None = None,
        description: str | None = None,
    ) -> None:
        """Disable the CRM module for a company."""
        self._flag_repo.upsert(
            company_id=company_id,
            flag_key=CRM_ENABLED_FLAG_KEY,
            is_enabled=False,
            created_by=actor_id,
            description=description,
        )
        logger.info(
            "CRM feature flag disabled: company=%s actor=%s", company_id, actor_id
        )

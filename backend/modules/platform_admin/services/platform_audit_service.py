"""PlatformAuditService — the reusable audited-mutation helper (ADR-5).

Mirrors ``modules.accounting.services.audit_service.AuditLogService``
exactly: ``record()`` builds a ``PlatformAuditEvent`` and stages it via
``PlatformAuditRepository.record()`` (flush-only) — it does **not**
commit. The calling domain service (e.g. ``PlatformAdministratorService``)
is responsible for the single service-level ``db.commit()`` that finalizes
its own state change together with this audit row in one transaction
(plan.md §3.5, §20): if the audit write were ever to fail, the caller's
own `db.flush()`'d state change has not been committed either, so nothing
partially persists.

Every audited task in Phases 3-12 depends on this helper.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.logging.setup import REQUEST_ID_CONTEXT
from modules.platform_admin.models.platform_audit_event import PlatformAuditEvent
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)

logger = logging.getLogger(__name__)


class PlatformAuditService:
    """Records immutable audit entries for privileged Platform actions."""

    def __init__(self, db: Session, audit_repo: PlatformAuditRepository) -> None:
        self.db = db
        self._repo = audit_repo

    def record(
        self,
        *,
        action: str,
        target_type: str,
        actor_platform_administrator_id: UUID | None = None,
        target_id: UUID | None = None,
        company_id: UUID | None = None,
        reason: str | None = None,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        support_access_grant_id: UUID | None = None,
    ) -> PlatformAuditEvent:
        """Stage an audit record for insert. Caller MUST commit.

        Args:
            action:       Dot-notation action code, e.g. "admin.deactivate".
            target_type:  The entity type this action targeted.
            actor_platform_administrator_id: Acting administrator; None only
                for rare system-initiated events.
            target_id:    The target entity's primary key.
            company_id:   Populated for tenant-scoped actions.
            reason:       Free-text reason, where required.
            before_state: Entity snapshot before the change.
            after_state:  Entity snapshot after the change.
            context:      Additional structured context (e.g. request_id).
            support_access_grant_id: Links to an owning support session
                (Phase 12 onward).
        """
        try:
            return self._repo.record(
                action=action,
                target_type=target_type,
                actor_platform_administrator_id=actor_platform_administrator_id,
                target_id=target_id,
                company_id=company_id,
                reason=reason,
                before_state=before_state,
                after_state=after_state,
                context=context,
                support_access_grant_id=support_access_grant_id,
            )
        except Exception:
            # Fail-closed (ADR-5): logged here for operational visibility,
            # then always re-raised unchanged so the caller's own
            # domain-mutation flush/commit is rolled back too — never
            # swallowed, never partially persisted.
            logger.error(
                "Platform audit write failed",
                extra={
                    "request_id": REQUEST_ID_CONTEXT.get("-"),
                    "action": action,
                    "target_type": target_type,
                    "actor_platform_administrator_id": (
                        str(actor_platform_administrator_id)
                        if actor_platform_administrator_id
                        else None
                    ),
                },
                exc_info=True,
            )
            raise

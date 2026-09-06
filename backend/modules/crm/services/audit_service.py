"""CrmAuditService — append-only audit recording for CRM entities.

Same signature shape as ``CompanyAuditService.record()``, generalized
with an ``entity_type`` discriminator (LEAD / OPPORTUNITY / ACTIVITY) so
one table serves all three CRM auditable entities rather than three
near-identical tables (plan.md §44/§18).

Deliberately does NOT call ``db.commit()`` itself — it participates in
the calling service's own transaction (``flush()`` only), matching the
established "caller controls the commit" pattern already proven safe by
``AuditLogService``'s own usage inside ``PostingEngine`` (plan.md §18.3:
the audit row and the state change commit together, atomically).

Spec ref: specs/009-crm/spec.md §44; plan.md §18.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from modules.crm.models.audit import CrmAuditLog
from modules.crm.repositories.audit_log import CrmAuditLogRepository


class CrmAuditService:
    """Records immutable audit entries for CRM entity mutations."""

    def __init__(self, repo: CrmAuditLogRepository) -> None:
        self._repo = repo

    def record(
        self,
        *,
        company_id: UUID,
        actor_user_id: UUID | None,
        entity_type: str,
        entity_id: UUID,
        action: str,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
    ) -> CrmAuditLog:
        """Stage one audit log entry. Caller MUST commit (within the same
        transaction as the state change it documents).

        Args:
            company_id:    Tenant identifier.
            actor_user_id: User who triggered the action; ``None`` for
                            system-initiated events.
            entity_type:   ``"LEAD"`` / ``"OPPORTUNITY"`` / ``"ACTIVITY"``.
            entity_id:     The entity's primary key.
            action:        E.g. ``"LEAD_CREATED"``, ``"LEAD_CONVERTED"``,
                            ``"OPPORTUNITY_WON"`` (spec.md §44's action list).
            before_state:  Entity snapshot before the change.
            after_state:   Entity snapshot after the change.
        """
        log = CrmAuditLog(
            company_id=company_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_user_id=str(actor_user_id) if actor_user_id is not None else None,
            before_state=before_state,
            after_state=after_state,
        )
        return self._repo.create(log)

    def find_latest_after_state(
        self, company_id: UUID, entity_type: str, entity_id: UUID, action: str
    ) -> dict[str, Any] | None:
        """Return the most recent ``after_state`` recorded for this
        entity+action, or ``None`` if none exists.

        Lets an idempotent-retry code path (e.g. repeat Lead conversion)
        recall a fact from the *original* mutation — such as whether an
        existing Customer was matched vs newly created — without adding a
        redundant persisted column just to answer that one question on
        retry.
        """
        logs = self._repo.list_for_entity(company_id, entity_type, entity_id)
        for log in reversed(logs):
            if log.action == action:
                return log.after_state
        return None

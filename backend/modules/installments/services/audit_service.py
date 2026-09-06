"""InstallmentAuditService — synchronous audit trail writer.

Every write goes through ``InstallmentAuditLogRepository.create()``, which
only ``flush()``es (never commits) — the caller commits the audit record
together with the business mutation it documents, in the same database
transaction (plan.md §17's fail-closed discipline: audit failure and
business failure are the same failure by construction). Mirrors
``AuditLogService`` (accounting) exactly.

Spec ref: specs/010-installments/plan.md §17.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from modules.installments.models.audit import InstallmentAuditLog
from modules.installments.repositories.audit import InstallmentAuditLogRepository


class InstallmentAuditService:
    """Records immutable audit entries for Installments state changes."""

    def __init__(self, db: Session, audit_repo: InstallmentAuditLogRepository) -> None:
        self.db = db
        self._repo = audit_repo

    def record(
        self,
        company_id: UUID,
        entity_type: str,
        entity_id: UUID,
        action: str,
        actor_id: UUID | None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        reason: str | None = None,
        session_context: dict[str, Any] | None = None,
    ) -> InstallmentAuditLog:
        """Stage an audit record for insert. Caller MUST commit.

        Args:
            company_id:  Tenant identifier.
            entity_type: E.g. ``"InstallmentContract"``.
            entity_id:   The entity's primary key.
            action:      One of the values enumerated in plan.md §17
                         (``"CREATED"``, ``"SUBMITTED"``, ``"APPROVED"``,
                         ``"REJECTED"``, ``"ACTIVATED"``, ``"COLLECTED"``,
                         etc.).
            actor_id:    User who triggered the action; ``None`` for
                         system-initiated events.
            before:      Entity snapshot before the change (JSON-serialisable).
            after:       Entity snapshot after the change (JSON-serialisable).
            reason:      Free-text reason, when applicable.
            session_context: Additional structured context (request id, etc.).
        """
        log = InstallmentAuditLog(
            company_id=company_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_user_id=actor_id,
            before_state=before,
            after_state=after,
            reason=reason,
            session_context=session_context,
        )
        return self._repo.create(log)

    def list_for_entity(
        self, company_id: UUID, entity_type: str, entity_id: UUID
    ) -> list[InstallmentAuditLog]:
        return self._repo.list_for_entity(company_id, entity_type, entity_id)

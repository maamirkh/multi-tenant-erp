"""AuditLogService — synchronous audit trail writer — Phase 4.

Every write goes through ``AccountingAuditLogRepository.create()``, which
only ``flush()``es (never commits) — the caller (``PostingEngine``) commits
the audit record together with the financial action it records, in the
same database transaction. This is research.md Decision 11: an audit entry
either commits with the action or the entire action rolls back; there is no
async audit queue.

Spec ref: specs/008-accounting-finance/tasks.md T098
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from modules.accounting.models.gl import AccountingAuditLog
from modules.accounting.repositories.gl import AccountingAuditLogRepository


class AuditLogService:
    """Records immutable audit entries for accounting financial state changes."""

    def __init__(self, db: Session, audit_repo: AccountingAuditLogRepository) -> None:
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
    ) -> AccountingAuditLog:
        """Stage an audit record for insert. Caller MUST commit.

        Args:
            company_id:  Tenant identifier.
            entity_type: E.g. ``"JournalEntry"``.
            entity_id:   The entity's primary key.
            action:      E.g. ``"CREATED"``, ``"SUBMITTED"``, ``"APPROVED"``,
                         ``"REJECTED"``, ``"POSTED"``, ``"REVERSED"``.
            actor_id:    User who triggered the action; ``None`` for
                         system-initiated events (e.g. integration handlers).
            before:      Entity snapshot before the change (JSON-serialisable).
            after:       Entity snapshot after the change (JSON-serialisable).
            reason:      Free-text reason, when applicable (e.g. rejection).
            session_context: Additional structured context (request id, etc.).
        """
        log = AccountingAuditLog(
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

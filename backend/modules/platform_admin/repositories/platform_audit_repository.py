"""PlatformAuditRepository — flush-only, append-only data access.

Mirrors ``AccountingAuditLogRepository`` exactly (the codebase's only
existing fail-closed audit precedent, plan.md §3.4/§3.5): ``record()``
stages the row via ``db.add()`` + ``db.flush()`` and never
``db.commit()``s — the caller (a domain service, via
``PlatformAuditService``) commits the audit row together with the state
change it records, in the same transaction (ADR-5).

Deliberately does **not** inherit ``BaseRepository`` — that class mandates
``company_id`` filtering on every method (tenant-isolation contract for
tenant-scoped tables), which is wrong here: `platform_audit_events` is
platform-scoped, and `company_id` is an optional column on individual
rows, not a repository-wide isolation key.

No update or delete method exists at all — append-only (BR-9A-023).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from modules.platform_admin.models.platform_audit_event import PlatformAuditEvent


class PlatformAuditRepository:
    """Append-only data access for the ``platform_audit_events`` table."""

    def __init__(self, db: Session) -> None:
        self.db = db

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
        """Stage a new audit record for insert. Caller commits."""
        event = PlatformAuditEvent(
            actor_platform_administrator_id=actor_platform_administrator_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            company_id=company_id,
            reason=reason,
            before_state=before_state,
            after_state=after_state,
            context=context,
            support_access_grant_id=support_access_grant_id,
        )
        self.db.add(event)
        self.db.flush()
        return event

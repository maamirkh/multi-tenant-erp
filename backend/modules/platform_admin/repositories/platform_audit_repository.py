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

``list_filtered()`` (T078, FR-9A-200) is a read-only addition — it does
not weaken append-only-ness, since reading is not mutation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import func, select
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

    def list_filtered(
        self,
        *,
        actor_platform_administrator_id: UUID | None = None,
        company_id: UUID | None = None,
        action: str | None = None,
        target_type: str | None = None,
        target_id: UUID | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        outcome: Literal["success", "denied"] | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[PlatformAuditEvent], int]:
        """Filtered, paginated read of the audit trail (FR-9A-200).

        Filters correspond to spec.md's "administrator, tenant, action,
        resource, date/time, result/status" set:
          - administrator -> actor_platform_administrator_id
          - tenant        -> company_id
          - action        -> action (exact match)
          - resource      -> target_type / target_id
          - date/time     -> created_after / created_before (inclusive)
          - result/status -> outcome

        ``outcome`` is derived, not a stored column — no such column
        exists on ``PlatformAuditEvent`` (data-model.md/plan.md §20 list
        the full field set; there is no status field). Every denial this
        module records uses an ``action`` ending in ``.denied`` (T065's
        ``platform_rbac.role.assign.denied``, T066's
        ``platform_rbac.last_owner_removal.denied``) — a convention
        established in Phase 5, not invented here.

        Uses the T014 indexes (``actor_platform_administrator_id``,
        ``company_id``, ``action``, ``created_at``) — no other column is
        filtered without also being covered by one of those four, so this
        never table-scans on the indexed dimensions.
        """
        stmt = select(PlatformAuditEvent)

        if actor_platform_administrator_id is not None:
            stmt = stmt.where(
                PlatformAuditEvent.actor_platform_administrator_id
                == actor_platform_administrator_id
            )
        if company_id is not None:
            stmt = stmt.where(PlatformAuditEvent.company_id == company_id)
        if action is not None:
            stmt = stmt.where(PlatformAuditEvent.action == action)
        if target_type is not None:
            stmt = stmt.where(PlatformAuditEvent.target_type == target_type)
        if target_id is not None:
            stmt = stmt.where(PlatformAuditEvent.target_id == target_id)
        if created_after is not None:
            stmt = stmt.where(PlatformAuditEvent.created_at >= created_after)
        if created_before is not None:
            stmt = stmt.where(PlatformAuditEvent.created_at <= created_before)
        if outcome == "denied":
            stmt = stmt.where(PlatformAuditEvent.action.like("%.denied"))
        elif outcome == "success":
            stmt = stmt.where(~PlatformAuditEvent.action.like("%.denied"))

        total = self.db.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()

        rows_stmt = (
            stmt.order_by(PlatformAuditEvent.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list(self.db.execute(rows_stmt).scalars().all())
        return items, total

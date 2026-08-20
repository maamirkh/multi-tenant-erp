"""PlatformAuditEvent ORM model — append-only Platform audit trail.

Persistence for `platform_audit_events` (migration 057, data-model.md
"Identity & Session"). Inherits `BaseModel` only (id/created_at/updated_at)
— never `TenantBaseModel` — since this table is platform-scoped, tracking
tenant-affecting actions via an explicit nullable `company_id` FK rather
than implicit tenant-scoping inheritance (data-model.md line 3).

Fail-closed atomicity (ADR-5): this model is written via
`PlatformAuditRepository`, which only `flush()`s — the caller commits the
audit row together with the state change it records, in the same
transaction, mirroring `AccountingAuditLog`'s established pattern
(plan.md §3.4/§3.5).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.base_model import BaseModel


class PlatformAuditEvent(BaseModel):
    """Append-only record of a privileged Platform action.

    Validation: append-only — no update/delete method exists anywhere in
    this module (BR-9A-023); no UPDATE/DELETE route will ever be added to
    the router.
    """

    __tablename__ = "platform_audit_events"
    __table_args__ = (
        Index("ix_platform_audit_events_actor_id", "actor_platform_administrator_id"),
        Index("ix_platform_audit_events_company_id", "company_id"),
        Index("ix_platform_audit_events_action", "action"),
        Index("ix_platform_audit_events_created_at", "created_at"),
    )

    actor_platform_administrator_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("platform_administrators.id"),
        nullable=True,
        doc="Acting Platform Administrator. Null only for rare "
        "system-initiated events.",
    )

    action: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        doc="Dot-notation action code, e.g. 'tenant.suspend', 'plan.publish'.",
    )

    target_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="The entity type this action targeted, e.g. 'Company', 'Plan'.",
    )

    target_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="The target entity's primary key.",
    )

    company_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id"),
        nullable=True,
        doc="Populated for tenant-scoped actions; null for platform-global ones.",
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Free-text reason supplied by the actor, where required.",
    )

    before_state: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Entity snapshot before the change (JSON-serialisable).",
    )

    after_state: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Entity snapshot after the change (JSON-serialisable).",
    )

    context: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Additional structured context, incl. request_id for correlation.",
    )

    # NOT a ForeignKey() at the ORM level yet: support_access_grants has no
    # ORM model until Phase 12 creates it, though migration 057 already adds
    # this nullable column and migration 061 adds the DB-level FK once that
    # table exists (the same deferred-FK technique applied at the ORM layer
    # — see migrations 057/061). Populated from Phase 12 onward.
    support_access_grant_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="Links this entry to its owning support-access session, once "
        "Phase 12 exists.",
    )

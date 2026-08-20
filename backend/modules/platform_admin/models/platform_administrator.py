"""PlatformAdministrator ORM model — the Platform principal.

Persistence for `platform_administrators` (migration 057, data-model.md
"Identity & Session"). First-class Platform principal, 1:1 with the
existing `User` (shared credential identity, plan.md §3.1) — never
`TenantBaseModel` (no `company_id`; a Platform Administrator is not
scoped to any tenant, BR-9A-010).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.base_model import BaseModel


class PlatformAdministrator(BaseModel):
    """The Platform Administrator principal.

    Validation: a `User` row may have at most one `PlatformAdministrator`
    row (UNIQUE on `user_id`, migration 057). Lifecycle: created only via
    the out-of-band bootstrap (first row, Phase 4) or a
    `platform.admins.manage`-gated API (all subsequent rows, Phase 5) —
    never implicitly.
    """

    __tablename__ = "platform_administrators"

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
        doc="FK to users.id; reuses existing credentials, never a second "
        "password system.",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        doc="Deactivation immediately invalidates active platform sessions "
        "(BR-9A-011, wired in Phase 4's T054).",
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Updated on successful Platform login (Phase 4).",
    )

    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when this administrator was deactivated.",
    )

    deactivated_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("platform_administrators.id"),
        nullable=True,
        doc="The Platform Administrator who performed the deactivation.",
    )

"""PlatformSession ORM model — structurally separate Platform session.

Persistence for `platform_sessions` (migration 057, data-model.md
"Identity & Session"). Mirrors the tenant `sessions` table's shape, but is
a genuinely separate table — tenant sessions must never double as platform
sessions (BR-9A-003, ADR-1). `ip_address` uses `INET` (data-model.md's
explicit choice for this table, unlike the tenant `sessions.ip_address`
`String(45)` convention).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.base_model import BaseModel


class PlatformSession(BaseModel):
    """Platform authentication session — one row per Platform login.

    State transitions: `active` -> `revoked` (deactivation, logout, or
    admin-initiated revocation) — one-way, never un-revoked.
    """

    __tablename__ = "platform_sessions"
    __table_args__ = (
        Index("ix_platform_sessions_admin_id", "platform_administrator_id"),
    )

    platform_administrator_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("platform_administrators.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to platform_administrators.id.",
    )

    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="True once revoked (logout, deactivation, or admin action).",
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when this session was revoked. NULL while active.",
    )

    ip_address: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
        doc="Client IP address at login time.",
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Raw User-Agent header from the login request.",
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="UTC time after which this session is no longer valid.",
    )

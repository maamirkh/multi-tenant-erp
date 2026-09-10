"""Session ORM model — tracks active authenticated sessions.

A session is created on every successful login and groups all refresh tokens
issued during that session.  Revoking a session invalidates all its refresh
tokens, implementing a clean "logout all devices" capability.

One user may have multiple concurrent active sessions (e.g., browser + mobile).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.models.base_model import BaseModel

if TYPE_CHECKING:
    from modules.auth.models.refresh_token import RefreshToken
    from modules.auth.models.user import User


class Session(BaseModel):
    """Authenticated session grouping one or more refresh token rotations.

    Inherits ``id``, ``created_at``, ``updated_at`` from ``BaseModel``.
    """

    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_is_revoked", "is_revoked"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to users.id; the owner of this session.",
    )

    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="True when the session has been explicitly revoked (logout).",
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when the session was revoked.  NULL while active.",
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        doc="IP address of the client at login time (supports IPv6).",
    )

    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Raw User-Agent header from the login request.",
    )

    device_info: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Parsed device metadata (OS, browser, device type) for display in UI.",
    )

    # ── Relationships ──────────────────────────────────────────────────────
    user: Mapped[User] = relationship(
        "User",
        back_populates="sessions",
        lazy="select",
    )

    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="select",
    )

"""PlatformRefreshToken ORM model — opaque, hashed refresh token storage.

Persistence for `platform_refresh_tokens` (migration 057, data-model.md
"Identity & Session"). Only a SHA-256 hash of the token is stored; the raw
token is delivered to the client once and never persisted (mirrors tenant
`refresh_tokens` exactly). Rotation is a repository/service-level
behaviour — on every use, the old row is revoked and a new one created
within the same `PlatformSession` (data-model.md deliberately carries no
`user_id`/`ip_address`/`user_agent`/`remember_me` fields here, unlike the
tenant table).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.base_model import BaseModel


class PlatformRefreshToken(BaseModel):
    """Single-use opaque Platform refresh token entry."""

    __tablename__ = "platform_refresh_tokens"
    __table_args__ = (Index("ix_platform_refresh_tokens_session_id", "session_id"),)

    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("platform_sessions.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to platform_sessions.id; the session this token belongs to.",
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc=(
            "SHA-256 hex digest of the raw refresh token. "
            "The raw token is never stored."
        ),
    )

    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="True when this token has been used (rotated) or explicitly revoked.",
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when this token was revoked. NULL while active.",
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="UTC time after which this token is no longer valid.",
    )

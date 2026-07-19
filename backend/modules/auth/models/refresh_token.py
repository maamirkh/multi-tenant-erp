"""RefreshToken ORM model — opaque refresh token storage.

Only a SHA-256 hash of the token is stored; the raw token value is
delivered to the client once and never persisted.  This means a database
breach does not expose usable refresh tokens.

Token rotation:
    On every use, the old token is revoked (``is_revoked=True``) and a new
    token is issued within the same session.  Presenting a revoked token is
    treated as a potential replay attack and triggers session revocation.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.models.base_model import BaseModel

if TYPE_CHECKING:
    from modules.auth.models.session import Session
    from modules.auth.models.user import User


class RefreshToken(BaseModel):
    """Single-use opaque refresh token entry.

    Inherits ``id``, ``created_at``, ``updated_at`` from ``BaseModel``.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_token_hash", "token_hash", unique=True),
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_session_id", "session_id"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to users.id; the owner of this token.",
    )

    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to sessions.id; the session this token belongs to.",
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        doc=(
            "SHA-256 hex digest of the raw refresh token. "
            "The raw token is never stored."
        ),
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="UTC time after which this token is no longer valid.",
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
        doc="UTC timestamp when this token was revoked.  NULL while active.",
    )

    remember_me: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc=(
            "True when issued with the 'Remember Me' option; "
            "controls extended expiry (JWT_REMEMBER_ME_EXPIRE_DAYS)."
        ),
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        doc="IP address of the client that requested this token (supports IPv6).",
    )

    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Raw User-Agent header from the token-request.",
    )

    # ── Relationships ──────────────────────────────────────────────────────
    user: Mapped[User] = relationship(
        "User",
        back_populates="refresh_tokens",
        lazy="select",
    )

    session: Mapped[Session] = relationship(
        "Session",
        back_populates="refresh_tokens",
        lazy="select",
    )

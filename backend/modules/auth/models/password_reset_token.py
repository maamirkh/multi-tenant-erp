"""PasswordResetToken ORM model — one-time password reset tokens.

A short-lived, single-use token is emailed to the user when they request
a password reset.  Only a SHA-256 hash of the token is stored; the raw
value is embedded in the reset URL and never persisted.

A user may have multiple outstanding reset tokens (e.g., if they request
the email multiple times), but only the most-recent, unconsumed, unexpired
token is accepted by the service layer.  Older tokens are not explicitly
revoked at issue time — they expire or are ignored.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.models.base_model import BaseModel

if TYPE_CHECKING:
    from modules.auth.models.user import User


class PasswordResetToken(BaseModel):
    """Single-use password reset token entry.

    Inherits ``id``, ``created_at``, ``updated_at`` from ``BaseModel``.
    """

    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        Index("ix_password_reset_tokens_token_hash", "token_hash", unique=True),
        Index("ix_password_reset_tokens_user_id", "user_id"),
        Index("ix_password_reset_tokens_expires_at", "expires_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to users.id; the account whose password is being reset.",
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        doc=(
            "SHA-256 hex digest of the raw reset token. "
            "The raw token is delivered via email and never stored."
        ),
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="UTC time after which this token is no longer valid.",
    )

    is_consumed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="True once this token has been used to reset the password.",
    )

    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when this token was consumed.  NULL until used.",
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        doc="IP address of the client that requested the reset (supports IPv6).",
    )

    # ── Relationships ──────────────────────────────────────────────────────
    user: Mapped[User] = relationship(
        "User",
        back_populates="password_reset_tokens",
        lazy="select",
    )

"""EmailVerificationToken ORM model — one-time email verification tokens.

A short-lived, single-use token is emailed to new users (and when they
change their email address) to prove inbox ownership.  Only a SHA-256 hash
is stored; the raw token is embedded in the verification URL.

Once consumed, ``users.is_email_verified`` is set to ``True`` and this
record is marked ``is_consumed=True``.
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


class EmailVerificationToken(BaseModel):
    """Single-use email address verification token.

    Inherits ``id``, ``created_at``, ``updated_at`` from ``BaseModel``.
    """

    __tablename__ = "email_verification_tokens"
    __table_args__ = (
        Index("ix_email_verification_tokens_token_hash", "token_hash", unique=True),
        Index("ix_email_verification_tokens_user_id", "user_id"),
        Index("ix_email_verification_tokens_expires_at", "expires_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to users.id; the account whose email is being verified.",
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        doc=(
            "SHA-256 hex digest of the raw verification token. "
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
        doc="True once this token has been used to verify the email address.",
    )

    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when this token was consumed.  NULL until used.",
    )

    # ── Relationships ──────────────────────────────────────────────────────
    user: Mapped[User] = relationship(
        "User",
        back_populates="email_verification_tokens",
        lazy="select",
    )

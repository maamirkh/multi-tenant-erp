"""UserCredentials ORM model — hashed password storage.

Stored in a separate 1-to-1 table (not embedded in ``users``) so that
credential data can be queried independently and access can be
tightly restricted at the database permission level.

Security invariants:
    - ``password_hash``  stores the Argon2id hash; never the plaintext.
    - ``password_history`` stores a JSONB list of previous Argon2id hashes
      to enforce the password-reuse policy.  It MUST NOT contain plaintext
      passwords.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.models.base_model import BaseModel

if TYPE_CHECKING:
    from modules.auth.models.user import User


class UserCredentials(BaseModel):
    """Hashed credentials for a single user account.

    One row per user; enforced by the ``UNIQUE`` constraint on ``user_id``.
    Inherits ``id``, ``created_at``, ``updated_at`` from ``BaseModel``.
    """

    __tablename__ = "user_credentials"
    __table_args__ = (Index("ix_user_credentials_user_id", "user_id", unique=True),)

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        doc="FK to users.id; one credentials row per user.",
    )

    password_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Argon2id hash of the current password.  Never store plaintext.",
    )

    password_history: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        doc=(
            "Ordered list of previous Argon2id hashes (oldest first). "
            "Used to enforce password-reuse policy.  Never store plaintext."
        ),
    )

    last_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="UTC timestamp when the password was last changed.",
    )

    # ── Relationships ──────────────────────────────────────────────────────
    user: Mapped[User] = relationship(
        "User",
        back_populates="credentials",
        lazy="select",
    )

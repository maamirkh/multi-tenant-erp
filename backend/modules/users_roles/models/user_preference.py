"""UserPreference ORM model — personal display/UX preferences.

User preferences are user-scoped (not company-scoped).  Each user has
at most one preference record (1:1 relationship with ``users``).

Spec reference: data-model.md Section 2.5.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class UserPreference(Base):
    """User display and UX preference record.

    Uses its own columns (not inheriting from ``BaseModel`` because this
    is a user-scoped entity, not tenant-scoped). Has its own ``id``,
    ``created_at``, ``updated_at``.
    """

    __tablename__ = "user_preferences"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        doc="Primary key; UUID generated server-side.",
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id", name="fk_user_preferences_user_id_users", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
        doc="Owning user (1:1 relationship).",
    )

    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="'en'",
        doc="Preferred UI language (BCP-47 tag).",
    )

    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="'UTC'",
        doc="IANA timezone identifier.",
    )

    date_format: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="'YYYY-MM-DD'",
        doc="Date display format.",
    )

    number_format: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="'en-US'",
        doc="Number formatting locale.",
    )

    theme: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="'system'",
        doc="UI theme: light, dark, or system.",
    )

    notification_preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'"),
        doc="Future notification settings (extensible JSONB).",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Record creation timestamp.",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Last modification timestamp.",
    )

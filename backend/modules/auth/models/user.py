"""User ORM model — core identity record.

The ``users`` table is the root of the authentication domain.  Every other
auth entity (credentials, sessions, tokens, audit log) references a row here
via ``user_id`` foreign key.

Multi-tenancy note:
    ``company_id`` is defined as a *nullable* UUID placeholder so that the
    column exists in the schema from this epic.  The Epic 003 (Companies)
    migration will:
      1. Populate the column for all existing users.
      2. Add the NOT NULL constraint.
      3. Add the FK constraint to ``companies.id``.
    This deferred approach avoids a breaking schema change in a later epic.

RBAC note:
    Role assignments live in a separate join table introduced in Epic 004.
    No ``role`` column is added here to avoid a premature schema assumption.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.models.base_model import BaseModel
from modules.auth.models.enums import AccountStatus

if TYPE_CHECKING:
    from modules.auth.models.email_verification_token import EmailVerificationToken
    from modules.auth.models.password_reset_token import PasswordResetToken
    from modules.auth.models.refresh_token import RefreshToken
    from modules.auth.models.session import Session
    from modules.auth.models.user_credential import UserCredentials


class User(BaseModel):
    """Authenticated identity record.

    Inherits ``id``, ``created_at``, ``updated_at`` from ``BaseModel``.
    """

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email", "email", unique=True),
        Index("ix_users_account_status", "account_status"),
        Index("ix_users_company_id", "company_id"),
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        doc="User's email address; used as the login identifier.",
    )

    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Human-readable name shown in the UI.",
    )

    account_status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="accountstatus", create_type=True),
        nullable=False,
        default=AccountStatus.ACTIVE,
        server_default=AccountStatus.ACTIVE.value,
        doc="Lifecycle state of this account.",
    )

    is_email_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="True once the user has clicked their email verification link.",
    )

    failed_login_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        doc="Consecutive failed login attempts; reset to 0 on successful login.",
    )

    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc=(
            "UTC time after which the account auto-unlocks. "
            "NULL when the account is not locked."
        ),
    )

    company_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc=(
            "Tenant identifier; nullable until Epic 003 adds companies table "
            "and populates existing rows.  FK constraint added in Epic 003 migration."
        ),
    )

    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Personal phone number. Added in Epic 004.",
    )

    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Current avatar S3 URL. Added in Epic 004.",
    )

    avatar_previous_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Previous avatar URL retained for AVATAR_RETENTION_DAYS. Added in Epic 004.",
    )

    # ── Relationships ──────────────────────────────────────────────────────
    credentials: Mapped[UserCredentials] = relationship(
        "UserCredentials",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

    sessions: Mapped[list[Session]] = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    password_reset_tokens: Mapped[list[PasswordResetToken]] = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    email_verification_tokens: Mapped[list[EmailVerificationToken]] = relationship(
        "EmailVerificationToken",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

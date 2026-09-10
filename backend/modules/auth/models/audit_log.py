"""AuditLog ORM model — immutable security event log.

This table is intentionally **append-only**.  Rows are never updated or
hard-deleted (only purged by a background job after ``AUDIT_LOG_RETENTION_DAYS``
have elapsed).  Because rows are immutable, there is no ``updated_at`` column —
inheriting from ``BaseModel`` is deliberately avoided here to prevent that
column from appearing in the schema.

``user_id`` is stored as a plain UUID value **without** a FK constraint so
that audit records survive even if the associated user row is deleted.  This
is required for forensic integrity.

No relationships are declared because this model is write-mostly and should
not be navigated from other models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Enum, Index, String, Text, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from modules.auth.models.enums import AuditEventType


class AuditLog(Base):
    """Immutable security event record.

    Inherits from ``Base`` directly (not ``BaseModel``) to omit
    ``updated_at`` — audit records must never be modified after insert.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_event_type", "event_type"),
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_outcome", "outcome"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        doc="Primary key; UUID generated server-side on INSERT.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp of the event; immutable after INSERT.",
    )

    event_type: Mapped[AuditEventType] = mapped_column(
        Enum(AuditEventType, name="auditeventtype", create_type=True),
        nullable=False,
        doc="Type of security event being recorded.",
    )

    user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc=(
            "UUID of the user associated with this event.  Nullable to "
            "accommodate pre-authentication failures (unknown email).  "
            "Stored as a plain value — no FK constraint — so records "
            "survive user deletion."
        ),
    )

    outcome: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        doc="High-level result of the event: 'SUCCESS' or 'FAILURE'.",
    )

    reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Human-readable explanation for the outcome, e.g. 'INVALID_PASSWORD'.",
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        doc="IP address of the client that triggered the event (supports IPv6).",
    )

    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Raw User-Agent header from the triggering request.",
    )

    request_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        doc="X-Request-ID header value for correlating with application logs.",
    )

    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        doc="Arbitrary event-specific context (e.g., token_id, device_info).",
    )

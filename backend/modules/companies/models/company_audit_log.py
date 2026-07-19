"""CompanyAuditLog ORM model — immutable audit trail for company events.

This model intentionally does NOT inherit ``BaseModel`` because audit records
must never have an ``updated_at`` column — they are append-only by convention.
All writes go through ``CompanyAuditLogRepository.create()``; no update or
delete path exists.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, func, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.base import Base

if TYPE_CHECKING:
    from modules.companies.models.company import Company


class CompanyAuditLog(Base):
    """Immutable audit record for a company state-change event.

    Does NOT inherit ``BaseModel`` — no ``updated_at`` column is permitted.
    """

    __tablename__ = "company_audit_logs"

    __table_args__ = (
        Index("ix_company_audit_logs_company_id", "company_id"),
        Index(
            "ix_company_audit_logs_company_id_created_at", "company_id", "created_at"
        ),
        Index("ix_company_audit_logs_actor_user_id", "actor_user_id"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        doc="Immutable UUID primary key generated server-side on INSERT.",
    )
    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
        doc="Company this audit event belongs to. ON DELETE RESTRICT preserves history.",
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="User who triggered the event. NULL for system-initiated events.",
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Event type label (e.g. COMPANY_CREATED, COMPANY_ACTIVATED).",
    )
    before_state: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Company snapshot before the change.",
    )
    after_state: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Company snapshot after the change.",
    )
    ip_address: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
        doc="Requester IP address (IPv4 or IPv6).",
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Requester User-Agent header value.",
    )
    request_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="Correlation ID from the originating HTTP request.",
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        doc="Additional event context (JSONB).",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp of event creation. Immutable after INSERT.",
    )

    # ── Relationship ──────────────────────────────────────────────────────────

    company: Mapped[Company] = relationship(
        "Company",
        back_populates="audit_logs",
        lazy="select",
    )

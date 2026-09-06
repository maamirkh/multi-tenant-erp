"""InstallmentAuditLog ORM model.

Append-only Installments audit sink — plain ``Base`` with an explicit
``company_id`` column, matching ``AccountingAuditLog``'s richer shape over
CRM's minimal one (plan.md §17), since Installments actions are
financially sensitive and frequently carry a mandatory reason. Does not
inherit ``TenantBaseModel``/``BaseModel`` (no ``updated_at``, no
soft-delete) — append-only by convention, repository exposes ``create``
and ``list_*`` only, never ``update``/``delete``.

Spec ref: specs/010-installments/plan.md §17.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class InstallmentAuditLog(Base):
    """Immutable audit record for every Installments state change."""

    __tablename__ = "installment_audit_log"
    __table_args__ = ({"comment": "Append-only Installments audit trail"},)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    session_context: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

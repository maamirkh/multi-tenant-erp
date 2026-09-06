"""CrmAuditLog ORM model.

Append-only CRM audit sink — module-local, continuing the established
per-module audit-table pattern (``CompanyAuditLog``, ``AccountingAuditLog``)
rather than a shared platform-wide table (none exists today). No
``update``/``delete`` repository method is ever defined against this
table (plan.md §18.2) — genuinely absent, not merely unused.

Spec ref: specs/009-crm/spec.md §44, plan.md §18.1.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Index, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class CrmAuditLog(TenantBaseModel):
    """Append-only audit trail entry for a CRM entity mutation."""

    __tablename__ = "crm_audit_log"
    __table_args__ = (
        Index(
            "ix_crm_audit_log_company_entity",
            "company_id",
            "entity_type",
            "entity_id",
        ),
        {"comment": "Append-only CRM audit trail"},
    )

    entity_type: Mapped[str] = mapped_column(
        String(20), nullable=False, doc="LEAD / OPPORTUNITY / ACTIVITY"
    )

    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    action: Mapped[str] = mapped_column(String(50), nullable=False)

    actor_user_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False), nullable=True
    )

    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

"""Activity ORM model.

A single, unified Activity entity (not one table per activity type) per
the input brief's explicit instruction — calls, emails, meetings, tasks,
notes, and follow-ups all share this one table, distinguished by
``activity_type``.

Uses explicit nullable FK columns (``lead_id``, ``customer_id``,
``opportunity_id``), not a polymorphic ``(related_type, related_id)``
pair — matching how ``InvoiceLine.delivery_note_line_id``/``order_line_id``
are modeled elsewhere in this codebase (plan.md §19.1/§6.6 note).

Spec ref: specs/009-crm/spec.md §37.6 / §19, plan.md §6.6.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

_ACTIVITY_TYPES = "('CALL', 'EMAIL', 'MEETING', 'TASK', 'NOTE', 'FOLLOW_UP')"
_ACTIVITY_STATUSES = "('PLANNED', 'COMPLETED', 'CANCELLED')"
_ACTIVITY_PRIORITIES = "('LOW', 'MEDIUM', 'HIGH')"


class Activity(TenantBaseModel):
    """A single, dated interaction or task, optionally linked to a Lead,
    Customer, and/or Opportunity (at least one required — BR-006)."""

    __tablename__ = "crm_activities"
    __table_args__ = (
        CheckConstraint(
            f"activity_type IN {_ACTIVITY_TYPES}", name="ck_crm_activities_type"
        ),
        CheckConstraint(
            f"status IN {_ACTIVITY_STATUSES}", name="ck_crm_activities_status"
        ),
        CheckConstraint(
            f"priority IN {_ACTIVITY_PRIORITIES}", name="ck_crm_activities_priority"
        ),
        CheckConstraint(
            "lead_id IS NOT NULL OR customer_id IS NOT NULL "
            "OR opportunity_id IS NOT NULL",
            name="ck_crm_activities_has_relation",
        ),
        Index(
            "ix_crm_activities_company_assigned_status",
            "company_id",
            "assigned_to",
            "status",
        ),
        Index("ix_crm_activities_company_due_date", "company_id", "due_date"),
        Index("ix_crm_activities_company_lead", "company_id", "lead_id"),
        Index("ix_crm_activities_company_customer", "company_id", "customer_id"),
        Index("ix_crm_activities_company_opportunity", "company_id", "opportunity_id"),
        {"comment": "CRM Activity — a single dated interaction or task"},
    )

    activity_type: Mapped[str] = mapped_column(
        String(15),
        nullable=False,
        doc="CALL / EMAIL / MEETING / TASK / NOTE / FOLLOW_UP",
    )

    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(15),
        nullable=False,
        server_default=text("'PLANNED'"),
        doc="PLANNED / COMPLETED / CANCELLED",
    )

    priority: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default=text("'MEDIUM'"),
        doc="LOW / MEDIUM / HIGH",
    )

    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Set automatically by the complete transition, never client-supplied",
    )

    assigned_to: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="Plain UUID, same convention as Lead.owner_id",
    )

    lead_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("crm_leads.id"), nullable=True
    )

    customer_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="References sales.customers.id — no enforced FK across module boundary",
    )

    opportunity_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("crm_opportunities.id"), nullable=True
    )

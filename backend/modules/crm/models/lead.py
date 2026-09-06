"""Lead ORM model.

An unqualified prospect captured with contact info, source, and status.
Converts into a Sales Customer + a new Opportunity (spec.md §16).

``converted_opportunity_id`` and ``Opportunity.source_lead_id`` form a
same-module circular reference (``crm_leads`` is created before
``crm_opportunities`` in migration table order, per plan.md §7.1's
dependency ordering). ``ForeignKey(..., use_alter=True)`` tells SQLAlchemy
to defer that specific constraint to an ``ALTER TABLE`` issued after both
tables exist — the standard technique for a two-table cycle, applied here
rather than dropping the FK's enforcement or reordering the tables (which
would just move the cycle to `Opportunity.source_lead_id` instead).

Spec ref: specs/009-crm/spec.md §37.2 / §14, plan.md §6.2.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

_LEAD_STATUSES = "('NEW', 'CONTACTED', 'QUALIFIED', 'UNQUALIFIED', 'CONVERTED', 'LOST')"


class Lead(TenantBaseModel):
    """An unqualified prospect — see spec.md §7 CRM Terminology.

    Lifecycle (spec.md §14.2): NEW -> CONTACTED -> QUALIFIED -> CONVERTED,
    with UNQUALIFIED/LOST as terminal off-ramps (UNQUALIFIED is reopenable
    to NEW by a manager — the one explicit non-terminal exception).
    """

    __tablename__ = "crm_leads"
    __table_args__ = (
        CheckConstraint(f"status IN {_LEAD_STATUSES}", name="ck_crm_leads_status"),
        CheckConstraint(
            "score IS NULL OR score BETWEEN 0 AND 100", name="ck_crm_leads_score"
        ),
        CheckConstraint(
            "first_name IS NOT NULL OR last_name IS NOT NULL "
            "OR lead_company_name IS NOT NULL",
            name="ck_crm_leads_name_or_company",
        ),
        CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL",
            name="ck_crm_leads_email_or_phone",
        ),
        CheckConstraint("version >= 1", name="ck_crm_leads_version"),
        Index("ix_crm_leads_company_status", "company_id", "status"),
        Index("ix_crm_leads_company_owner", "company_id", "owner_id"),
        Index("ix_crm_leads_company_follow_up", "company_id", "next_follow_up_date"),
        Index("ix_crm_leads_company_email", "company_id", "email"),
        {"comment": "CRM Lead aggregate root — an unqualified prospect"},
    )

    # ---- Contact identity ----

    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lead_company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # ---- Address (optional capture) ----

    address_line1: Mapped[str | None] = mapped_column(String(300), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(300), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # ---- Source & classification ----

    source_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("crm_lead_sources.id"),
        nullable=True,
        doc="FK to LeadSource — nullable, source may be unknown at capture time",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'NEW'"),
        doc="NEW / CONTACTED / QUALIFIED / UNQUALIFIED / CONVERTED / LOST",
    )

    score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="0-100, manually or (future) AI-assigned",
    )

    owner_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="Assigned salesperson — plain UUID, same convention as SalesOrder.sales_rep_id",
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- Follow-up tracking ----

    last_contact_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_follow_up_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ---- Qualification / disqualification ----

    qualification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    disqualification_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- Conversion outcome (spec.md §16) ----

    converted_customer_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="References sales.customers.id — no enforced FK across module boundary",
    )

    converted_opportunity_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "crm_opportunities.id",
            use_alter=True,
            name="fk_crm_leads_converted_opportunity_id",
        ),
        nullable=True,
        doc="Real same-module FK — added via ALTER after crm_opportunities exists",
    )

    converted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ---- Optimistic locking ----

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        doc="Optimistic lock, matching Customer.version",
    )

"""Opportunity ORM model.

A trackable, in-progress sales pursuit against a known Customer, with a
monetary value, pipeline position, and win/loss outcome. Aggregate root
with no line-item child (plan.md §35) — line detail belongs to the
eventual Sales Quotation, not to CRM.

``weighted_value`` (``value * probability / 100``) is intentionally NOT a
column here — computed at read time in the service/schema layer, per
BR-010 and plan.md §6.5/§26. A future generated-column migration is the
pre-identified fallback if a load test ever proves read-time computation
too slow (plan.md §26/§33 R-...), not something to pre-build speculatively.

Spec ref: specs/009-crm/spec.md §37.5 / §17, plan.md §6.5.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

_OPPORTUNITY_STATUSES = "('OPEN', 'WON', 'LOST')"


class Opportunity(TenantBaseModel):
    """A trackable sales pursuit against a known Customer.

    Lifecycle (spec.md §17.2): OPEN -> WON | LOST, both terminal — no
    stage/value edits permitted once WON or LOST (BR-003).
    """

    __tablename__ = "crm_opportunities"
    __table_args__ = (
        CheckConstraint("value >= 0", name="ck_crm_opportunities_value"),
        CheckConstraint(
            "probability BETWEEN 0 AND 100", name="ck_crm_opportunities_probability"
        ),
        CheckConstraint(
            f"status IN {_OPPORTUNITY_STATUSES}", name="ck_crm_opportunities_status"
        ),
        Index("ix_crm_opportunities_company_status", "company_id", "status"),
        Index("ix_crm_opportunities_company_owner", "company_id", "owner_id"),
        Index("ix_crm_opportunities_company_customer", "company_id", "customer_id"),
        Index(
            "ix_crm_opportunities_company_pipeline_stage",
            "company_id",
            "pipeline_id",
            "stage_id",
        ),
        Index(
            "ix_crm_opportunities_company_close_date",
            "company_id",
            "expected_close_date",
        ),
        {"comment": "CRM Opportunity aggregate root — a trackable sales pursuit"},
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="e.g. 'Acme Corp — Q3 Equipment Order'",
    )

    customer_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="References sales.customers.id — required, immutable after creation (BR-002)",
    )

    owner_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="Assigned salesperson — plain UUID, same convention as SalesOrder.sales_rep_id",
    )

    pipeline_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("crm_pipelines.id"), nullable=False
    )

    stage_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("crm_pipeline_stages.id"), nullable=False
    )

    value: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default=text("0"),
        doc="Monetary value estimate",
    )

    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        doc="ISO 4217, matching Customer.currency_code / SalesOrder.currency_code",
    )

    probability: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="0-100; defaults from the current stage but independently overridable",
    )

    expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    source_lead_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("crm_leads.id"),
        nullable=True,
        doc="Set when this Opportunity originated from a Lead conversion (spec.md §16)",
    )

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default=text("'OPEN'"),
        doc="OPEN / WON / LOST",
    )

    lost_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Required when status=LOST (BR-004)"
    )

    won_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lost_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    quotation_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="References sales.sales_quotations.id — set once a Quotation is created (spec.md §21.1)",
    )

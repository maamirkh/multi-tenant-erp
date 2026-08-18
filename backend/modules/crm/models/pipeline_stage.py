"""PipelineStage ORM model.

A single step within a Pipeline, carrying a default win probability. At
most one stage per pipeline may be flagged ``is_won_stage=true``, and at
most one ``is_lost_stage=true`` — both enforced at the database level via
partial unique indexes (dual ``postgresql_where``/``sqlite_where``, same
pattern as ``Pipeline``'s own default-flag constraint).

Spec ref: specs/009-crm/spec.md §37.4 / §18.2, plan.md §6.4.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

_WON_STAGE_WHERE = text("is_won_stage = true AND is_deleted = false")
_LOST_STAGE_WHERE = text("is_lost_stage = true AND is_deleted = false")


class PipelineStage(TenantBaseModel):
    """A single ordered step within a Pipeline.

    Aggregate child of Pipeline — created/updated only through the
    Pipeline's own management endpoints (plan.md §35 aggregate roots).
    """

    __tablename__ = "crm_pipeline_stages"
    __table_args__ = (
        CheckConstraint("sequence >= 1", name="ck_crm_pipeline_stages_sequence"),
        CheckConstraint(
            "probability BETWEEN 0 AND 100",
            name="ck_crm_pipeline_stages_probability",
        ),
        Index(
            "ix_crm_pipeline_stages_company_pipeline_seq",
            "company_id",
            "pipeline_id",
            "sequence",
        ),
        Index(
            "uq_crm_pipeline_stages_won",
            "pipeline_id",
            unique=True,
            postgresql_where=_WON_STAGE_WHERE,
            sqlite_where=_WON_STAGE_WHERE,
        ),
        Index(
            "uq_crm_pipeline_stages_lost",
            "pipeline_id",
            unique=True,
            postgresql_where=_LOST_STAGE_WHERE,
            sqlite_where=_LOST_STAGE_WHERE,
        ),
        {"comment": "Ordered stages within a CRM Pipeline"},
    )

    pipeline_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("crm_pipelines.id"),
        nullable=False,
        doc="Parent Pipeline",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="e.g. 'Qualification', 'Proposal Sent', 'Closed Won'",
    )

    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Display/progression order within the pipeline (>= 1)",
    )

    probability: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Default win probability (0-100) an Opportunity inherits on entering this stage",
    )

    is_won_stage: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="At most one per pipeline may be true",
    )

    is_lost_stage: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="At most one per pipeline may be true",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Soft-disable without deleting; blocked while any OPEN opportunity occupies it (BR-007)",
    )

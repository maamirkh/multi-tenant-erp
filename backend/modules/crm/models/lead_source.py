"""LeadSource ORM model.

A company-configurable lookup value describing how a Lead was acquired
(e.g. "WEBSITE", "REFERRAL"). Referenced by ``Lead.source_id`` for source
attribution reporting (spec.md §41).

Spec ref: specs/009-crm/spec.md §37.1, plan.md §6.1.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class LeadSource(TenantBaseModel):
    """Company-configurable lead-source lookup value.

    Uniqueness on ``(company_id, code)`` is a plain constraint, not a
    partial index filtered on ``is_deleted`` — a soft-deleted source's code
    being reused is an acceptable edge case at this table's low cardinality
    (plan.md §6.1 note).
    """

    __tablename__ = "crm_lead_sources"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_crm_lead_sources_company_code"),
        Index("ix_crm_lead_sources_company_active", "company_id", "is_active"),
        {"comment": "Company-configurable CRM lead-source lookup values"},
    )

    code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Short code, e.g. 'WEBSITE', 'REFERRAL'",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Display name",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Soft-disable without deleting",
    )

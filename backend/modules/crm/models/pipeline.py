"""Pipeline ORM model.

A named, company-configurable ordered sequence of Stages that an
Opportunity moves through. Exactly one active-and-default Pipeline per
company is enforced at the database level (BR-008) via a partial unique
index — using the dual ``postgresql_where``/``sqlite_where`` pattern
already established by ``inventory_low_stock_alerts.uq_inv_alert_open_dedup``
(``modules/inventory/models/alerts.py``) so the constraint is genuinely
enforced in both PostgreSQL (production) and SQLite (the unit/integration
test suite), not PostgreSQL-only.

Spec ref: specs/009-crm/spec.md §37.3 / §18.1, plan.md §6.3.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

_DEFAULT_PIPELINE_WHERE = text("is_default = true AND is_deleted = false")


class Pipeline(TenantBaseModel):
    """Company-configurable named sequence of Stages (BR-008: at most one
    default pipeline per company, enforced by the partial unique index
    below)."""

    __tablename__ = "crm_pipelines"
    __table_args__ = (
        Index(
            "uq_crm_pipelines_company_default",
            "company_id",
            unique=True,
            postgresql_where=_DEFAULT_PIPELINE_WHERE,
            sqlite_where=_DEFAULT_PIPELINE_WHERE,
        ),
        {"comment": "Company-configurable CRM sales pipelines"},
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="e.g. 'Standard Sales Pipeline'",
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Exactly one active default pipeline per company (BR-008)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Soft-disable without deleting",
    )

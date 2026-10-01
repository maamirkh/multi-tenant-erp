"""SavedReportView ORM model (spec §29, plan.md §15, data-model.md).

Private, user-owned reporting configuration. Not FK'd to the Report
Registry (the registry is code, not a table) — `report_key` is a soft
reference, validated at write/load time instead (FR-RPT-201/203/204).

No uniqueness constraint on ``(company_id, user_id, name)`` — the spec
does not require preventing duplicate names (Constitution §7 YAGNI).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Index, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel
from modules.reports.schemas.common import JsonValue


class SavedReportView(TenantBaseModel):
    """Per-user, per-company saved reporting configuration."""

    __tablename__ = "saved_report_views"
    __table_args__ = (
        Index("ix_saved_report_views_company_user", "company_id", "user_id"),
        Index("ix_saved_report_views_company_report_key", "company_id", "report_key"),
        {"comment": "Private, user-owned saved report view configurations"},
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        doc="Owner — FK to users.id (unconstrained, matching platform convention).",
    )

    report_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Soft reference to the code-defined Report Registry — not FK'd.",
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)

    schema_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        doc="Saved-view storage schema version — Epic 11 ships only 1.",
    )

    filter_config: Mapped[dict[str, JsonValue]] = mapped_column(
        JSONB,
        nullable=False,
        doc="Validated against FilterConfigV1 before persist (FR-RPT-201).",
    )

    grouping: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    sorting: Mapped[str | None] = mapped_column(String(100), nullable=True)

    visible_columns: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    date_preset: Mapped[str | None] = mapped_column(String(30), nullable=True)

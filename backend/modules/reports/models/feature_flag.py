"""ReportsFeatureFlag ORM model.

Stores per-company overrides for the single Reports module gate,
``feature.reports.enabled`` (services.feature_flag_service module). When
no row exists for a company, the module defaults to **disabled**
(spec §18/FR-RPT-255, plan.md §12).

Follows the exact per-module convention established by
``CrmFeatureFlag``/``InstallmentsFeatureFlag`` — there is no shared
``company_feature_flags`` table in this codebase. The ``flag_key`` column
is retained for structural parity with those tables (and to leave room for
a future per-capability flag without a schema change), even though Reports
currently defines exactly one key.

Spec ref: specs/011-reports-analytics/plan.md §12.
"""

from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class ReportsFeatureFlag(TenantBaseModel):
    """Per-company feature flag override for the Reports module.

    Unique constraint on (company_id, flag_key) ensures each company can
    have at most one override per flag.
    """

    __tablename__ = "reports_feature_flags"
    __table_args__ = (
        UniqueConstraint("company_id", "flag_key", name="uq_reports_ff_company_key"),
        {"comment": "Per-company feature flag overrides for the Reports module"},
    )

    flag_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Feature flag key, e.g. 'feature.reports.enabled'",
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="True if the feature is enabled for this company",
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Optional description or override reason",
    )

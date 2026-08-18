"""CrmFeatureFlag ORM model.

Stores per-company overrides for the single CRM module gate,
``feature.crm.enabled`` (constants.CRM_ENABLED_FLAG_KEY). When no row
exists for a company, the module defaults to disabled.

Follows the exact per-module convention established by
``SalesFeatureFlag``/``AccountingFeatureFlag`` — there is no shared
``company_feature_flags`` table in this codebase. The ``flag_key`` column
is retained for structural parity with those tables (and to leave room for
a future per-capability flag without a schema change), even though CRM
currently defines exactly one key.

Spec ref: specs/009-crm/plan.md §17 (Feature Flag), §6.8.
"""

from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class CrmFeatureFlag(TenantBaseModel):
    """Per-company feature flag override for the CRM module.

    Unique constraint on (company_id, flag_key) ensures each company can
    have at most one override per flag.
    """

    __tablename__ = "crm_feature_flags"
    __table_args__ = (
        UniqueConstraint("company_id", "flag_key", name="uq_crm_ff_company_key"),
        {"comment": "Per-company feature flag overrides for the CRM module"},
    )

    flag_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Feature flag key, e.g. 'feature.crm.enabled'",
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

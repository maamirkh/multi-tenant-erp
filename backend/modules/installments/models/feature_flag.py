"""InstallmentsFeatureFlag ORM model.

Stores per-company overrides for the single Installments module gate,
``feature.installments.enabled``. When no row exists for a company, the
module defaults to disabled. Mirrors ``CrmFeatureFlag`` exactly.

Spec ref: specs/010-installments/plan.md §15.4.
"""

from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class InstallmentsFeatureFlag(TenantBaseModel):
    """Per-company feature flag override for the Installments module.

    Unique constraint on (company_id, flag_key) ensures each company can
    have at most one override per flag.
    """

    __tablename__ = "installments_feature_flags"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "flag_key", name="uq_installments_feature_flags_company_key"
        ),
        {"comment": "Per-company feature flag overrides for the Installments module"},
    )

    flag_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="feature.installments.enabled",
        index=True,
        doc="Feature flag key, e.g. 'feature.installments.enabled'",
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

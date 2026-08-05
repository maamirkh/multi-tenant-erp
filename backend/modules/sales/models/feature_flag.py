"""SalesFeatureFlag ORM model.

Stores per-company feature flag overrides for the Sales module.
When no override exists for a company, the system falls back to the
``default_enabled`` value defined in ``constants.SALES_FEATURE_FLAGS``.

This table is the data-persistence layer for the sales ``FeatureFlagService``.

Spec ref: specs/007-sales-management/spec.md §30 Feature Matrix
"""

from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class SalesFeatureFlag(TenantBaseModel):
    """Per-company feature flag override for the Sales module.

    Unique constraint on (company_id, flag_key) ensures each company
    can have at most one override per flag.
    """

    __tablename__ = "sales_feature_flags"
    __table_args__ = (
        UniqueConstraint("company_id", "flag_key", name="uq_sales_ff_company_key"),
        {"comment": "Per-company feature flag overrides for the Sales module"},
    )

    flag_key: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
        doc="Feature flag key, e.g. 'sales.approval_required_so'",
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        doc="True if the feature is enabled for this company",
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Optional description or override reason",
    )

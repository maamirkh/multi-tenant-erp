"""AccountingFeatureFlag ORM model.

Stores per-company feature flag overrides for the Accounting module.
When no override exists for a company, the system falls back to the
``default_enabled`` value defined in ``constants.ACCOUNTING_FEATURE_FLAGS``.

This table is the data-persistence layer for the accounting
``AccountingFeatureFlagService``. Follows the exact per-module convention
established by ``SalesFeatureFlag``/``PurchaseFeatureFlag``/
``InventoryFeatureFlag`` — there is no shared ``company_feature_flags``
table in this codebase (see quickstart.md "Phase 0 Verification Findings").

Spec ref: specs/008-accounting-finance/quickstart.md §Feature Flags
"""

from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class AccountingFeatureFlag(TenantBaseModel):
    """Per-company feature flag override for the Accounting module.

    Unique constraint on (company_id, flag_key) ensures each company
    can have at most one override per flag.
    """

    __tablename__ = "accounting_feature_flags"
    __table_args__ = (
        UniqueConstraint("company_id", "flag_key", name="uq_accounting_ff_company_key"),
        {"comment": "Per-company feature flag overrides for the Accounting module"},
    )

    flag_key: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
        doc="Feature flag key, e.g. 'accounting.bankreconciliation.enabled'",
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

"""InventoryFeatureFlag ORM model.

Stores per-company feature flag overrides for the Inventory module.
When no override exists for a company, the system falls back to the
``default_enabled`` value defined in ``constants.INVENTORY_FEATURE_FLAGS``.

This table is the data-persistence layer for ``FeatureFlagService``.

Spec ref: specs/005-inventory-management/spec.md §27 Feature Matrix
"""

from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class InventoryFeatureFlag(TenantBaseModel):
    """Per-company feature flag override for the Inventory module.

    Unique constraint on (company_id, flag_key) ensures each company
    can have at most one override per flag.
    """

    __tablename__ = "inventory_feature_flags"
    __table_args__ = (
        UniqueConstraint("company_id", "flag_key", name="uq_inventory_ff_company_key"),
        {"comment": "Per-company feature flag overrides for the Inventory module"},
    )

    flag_key: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
        doc="Feature flag key, e.g. 'inventory.product_variants'",
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

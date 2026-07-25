"""CustomFieldDefinition ORM model — configurable entity extension fields.

Allows companies to define their own fields on Inventory entities (Products,
Warehouses, etc.) without schema changes. Values are stored in Phase 2+.

Multi-tenancy: Inherits ``company_id`` from ``TenantBaseModel``.

Spec ref: specs/005-inventory-management/spec.md §14
Data model: specs/005-inventory-management/data-model.md §2
"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Index, String, UniqueConstraint, false
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class CustomFieldDefinition(TenantBaseModel):
    """Definition of a company-configured custom field for an inventory entity.

    ``entity_type`` determines which entity this field applies to:
      PRODUCT, WAREHOUSE, CATEGORY, BRAND

    ``data_type`` determines the value format:
      TEXT, NUMBER, BOOLEAN, DATE, DROPDOWN

    Invariants:
    - field_key unique per company per entity_type
    - entity_type must be one of the defined enum values
    - data_type must be one of the defined enum values
    """

    __tablename__ = "inventory_custom_field_definitions"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "entity_type",
            "field_key",
            name="uq_inv_cf_def_company_entity_key",
        ),
        Index("ix_inv_cf_def_company_id", "company_id"),
        Index("ix_inv_cf_def_company_entity_type", "company_id", "entity_type"),
        CheckConstraint(
            "entity_type IN ('PRODUCT', 'WAREHOUSE', 'CATEGORY', 'BRAND')",
            name="ck_inv_cf_def_entity_type",
        ),
        CheckConstraint(
            "data_type IN ('TEXT', 'NUMBER', 'BOOLEAN', 'DATE', 'DROPDOWN')",
            name="ck_inv_cf_def_data_type",
        ),
        {"comment": "Company-defined custom field schemas for inventory entities"},
    )

    entity_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Entity this field applies to: PRODUCT / WAREHOUSE / CATEGORY / BRAND",
    )

    field_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Machine-readable key, unique per company per entity_type",
    )

    field_label: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Human-readable label shown in the UI",
    )

    data_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Value type: TEXT / NUMBER / BOOLEAN / DATE / DROPDOWN",
    )

    options: Mapped[dict | list | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="For DROPDOWN type: list of allowed option strings",
    )

    is_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=false(),
        doc="True if this field is mandatory when creating the entity",
    )

    sort_order: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
        doc="Display order in the custom fields section (ascending)",
    )

    placeholder: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        doc="Optional UI placeholder text",
    )

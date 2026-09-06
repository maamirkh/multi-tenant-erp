"""Attribute ORM models — AttributeDefinition, AttributeSet, AttributeSetMembership.

These models form the foundation for configurable product variant attributes
(e.g. Size, Colour, Material) used in Phase 2 Product Master.

Multi-tenancy: All models inherit ``company_id`` from ``TenantBaseModel``.

Spec ref: specs/005-inventory-management/spec.md §14
Data model: specs/005-inventory-management/data-model.md §1.5
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class AttributeDefinition(TenantBaseModel):
    """Definition of a product attribute (e.g. 'Colour', 'Size').

    ``data_type`` determines the allowed values format:
      TEXT, NUMBER, BOOLEAN, DATE, DROPDOWN, MULTISELECT

    For DROPDOWN and MULTISELECT types, ``options`` contains the list of
    allowed values as a JSON array: ``["Red", "Blue", "Green"]``.

    Invariants:
    - name unique per company
    - data_type must be one of the defined enum values
    """

    __tablename__ = "inventory_attribute_definitions"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "name",
            name="uq_inv_attr_def_company_name",
        ),
        Index("ix_inv_attr_def_company_id", "company_id"),
        CheckConstraint(
            "data_type IN ('TEXT', 'NUMBER', 'BOOLEAN', 'DATE', 'DROPDOWN', 'MULTISELECT')",
            name="ck_inv_attr_def_data_type",
        ),
        {"comment": "Product attribute definitions, scoped per company"},
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Attribute name, unique per company (e.g. 'Colour', 'Size')",
    )

    data_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Value type: TEXT / NUMBER / BOOLEAN / DATE / DROPDOWN / MULTISELECT",
    )

    options: Mapped[dict | list | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="For DROPDOWN/MULTISELECT: list of allowed option strings",
    )

    is_required: Mapped[bool] = mapped_column(
        nullable=False,
        server_default="false",
        doc="True if this attribute must be set on all products/variants",
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Optional description of what this attribute represents",
    )


class AttributeSet(TenantBaseModel):
    """A named group of AttributeDefinitions applied to a product type or category.

    Invariants:
    - name unique per company
    - scope must be 'PRODUCT_TYPE' or 'CATEGORY'
    """

    __tablename__ = "inventory_attribute_sets"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "name",
            name="uq_inv_attr_set_company_name",
        ),
        Index("ix_inv_attr_sets_company_id", "company_id"),
        CheckConstraint(
            "scope IN ('PRODUCT_TYPE', 'CATEGORY')",
            name="ck_inv_attr_set_scope",
        ),
        {
            "comment": "Attribute sets that group attribute definitions, scoped per company"
        },
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Attribute set name, unique per company",
    )

    scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="'PRODUCT_TYPE' or 'CATEGORY'",
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Optional description",
    )


class AttributeSetMembership(TenantBaseModel):
    """Association between an AttributeSet and an AttributeDefinition.

    Determines which attributes belong to which set, and their display order.
    """

    __tablename__ = "inventory_attribute_set_memberships"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "attribute_set_id",
            "attribute_definition_id",
            name="uq_inv_attr_set_member",
        ),
        Index("ix_inv_attr_set_mem_set_id", "attribute_set_id"),
        Index("ix_inv_attr_set_mem_def_id", "attribute_definition_id"),
        CheckConstraint(
            "sort_order >= 0",
            name="ck_inv_attr_set_mem_sort",
        ),
        {
            "comment": "AttributeSet ↔ AttributeDefinition membership, scoped per company"
        },
    )

    attribute_set_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_attribute_sets.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to AttributeSet",
    )

    attribute_definition_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_attribute_definitions.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to AttributeDefinition",
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        doc="Display order within the set (ascending)",
    )

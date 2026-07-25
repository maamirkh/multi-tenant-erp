"""Epic 005 — Inventory Management Phase 1: master data tables.

Creates the following tables in FK-dependency order:
  1. inventory_categories         — hierarchical category tree
  2. inventory_brands             — brand master data
  3. inventory_uoms               — unit of measure definitions
  4. inventory_uom_conversions    — UOM conversion factors
  5. inventory_attribute_definitions — attribute type definitions
  6. inventory_attribute_sets     — attribute grouping
  7. inventory_attribute_set_memberships — set ↔ definition links
  8. inventory_tags               — product tags
  9. inventory_reason_codes       — adjustment/damage/return reason codes
 10. inventory_custom_field_definitions — company-defined entity fields

All tables follow the platform convention:
  - UUID primary key with gen_random_uuid() server default
  - created_at / updated_at with now() server default
  - company_id FK to companies.id
  - is_deleted / deleted_at for soft delete
  - VARCHAR status fields with CHECK constraints (no ENUM types)
  - JSONB columns for flexible option lists

Revision ID: 006
Revises:     005
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ── Revision identifiers ───────────────────────────────────────────────────

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all Phase 1 master data tables."""

    # ── 1. inventory_categories ───────────────────────────────────────────
    op.create_table(
        "inventory_categories",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_inv_categories_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["inventory_categories.id"],
            name="fk_inv_categories_parent",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "company_id", "code", name="uq_inv_categories_company_code"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')", name="ck_inv_categories_status"
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_inv_categories_sort_order"),
        comment="Hierarchical product category tree, scoped per company",
    )
    op.create_index(
        "ix_inv_categories_company_id", "inventory_categories", ["company_id"]
    )
    op.create_index(
        "ix_inv_categories_parent_id", "inventory_categories", ["parent_id"]
    )
    op.create_index(
        "ix_inv_categories_company_status",
        "inventory_categories",
        ["company_id", "status"],
    )

    # ── 2. inventory_brands ───────────────────────────────────────────────
    op.create_table(
        "inventory_brands",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("country_of_origin", sa.String(100), nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("website", sa.String(300), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_inv_brands_company",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("company_id", "code", name="uq_inv_brands_company_code"),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')", name="ck_inv_brands_status"
        ),
        comment="Product brand master data, scoped per company",
    )
    op.create_index("ix_inv_brands_company_id", "inventory_brands", ["company_id"])
    op.create_index(
        "ix_inv_brands_company_status", "inventory_brands", ["company_id", "status"]
    )

    # ── 3. inventory_uoms ─────────────────────────────────────────────────
    op.create_table(
        "inventory_uoms",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("uom_type", sa.String(20), nullable=False),
        sa.Column("symbol", sa.String(10), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_inv_uoms_company",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("company_id", "code", name="uq_inv_uoms_company_code"),
        sa.CheckConstraint(
            "uom_type IN ('UNIT', 'WEIGHT', 'VOLUME', 'LENGTH', 'AREA')",
            name="ck_inv_uoms_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')", name="ck_inv_uoms_status"
        ),
        comment="Unit of Measure definitions, scoped per company",
    )
    op.create_index("ix_inv_uoms_company_id", "inventory_uoms", ["company_id"])
    op.create_index(
        "ix_inv_uoms_company_status", "inventory_uoms", ["company_id", "status"]
    )

    # ── 4. inventory_uom_conversions ──────────────────────────────────────
    op.create_table(
        "inventory_uom_conversions",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_uom_id", sa.Uuid(), nullable=False),
        sa.Column("target_uom_id", sa.Uuid(), nullable=False),
        sa.Column("conversion_factor", sa.Numeric(18, 6), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_inv_uom_conv_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_uom_id"],
            ["inventory_uoms.id"],
            name="fk_inv_uom_conv_source",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_uom_id"],
            ["inventory_uoms.id"],
            name="fk_inv_uom_conv_target",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "company_id",
            "source_uom_id",
            "target_uom_id",
            name="uq_inv_uom_conv_company_pair",
        ),
        sa.CheckConstraint(
            "conversion_factor > 0", name="ck_inv_uom_conv_factor_positive"
        ),
        comment="Unit of Measure conversion factors, scoped per company",
    )
    op.create_index(
        "ix_inv_uom_conversions_company_id", "inventory_uom_conversions", ["company_id"]
    )
    op.create_index(
        "ix_inv_uom_conversions_source",
        "inventory_uom_conversions",
        ["company_id", "source_uom_id"],
    )

    # ── 5. inventory_attribute_definitions ───────────────────────────────
    op.create_table(
        "inventory_attribute_definitions",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("data_type", sa.String(20), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("description", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_inv_attr_def_company",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("company_id", "name", name="uq_inv_attr_def_company_name"),
        sa.CheckConstraint(
            "data_type IN ('TEXT', 'NUMBER', 'BOOLEAN', 'DATE', 'DROPDOWN', 'MULTISELECT')",
            name="ck_inv_attr_def_data_type",
        ),
        comment="Product attribute definitions, scoped per company",
    )
    op.create_index(
        "ix_inv_attr_def_company_id", "inventory_attribute_definitions", ["company_id"]
    )

    # ── 6. inventory_attribute_sets ───────────────────────────────────────
    op.create_table(
        "inventory_attribute_sets",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_inv_attr_set_company",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("company_id", "name", name="uq_inv_attr_set_company_name"),
        sa.CheckConstraint(
            "scope IN ('PRODUCT_TYPE', 'CATEGORY')", name="ck_inv_attr_set_scope"
        ),
        comment="Attribute sets that group attribute definitions, scoped per company",
    )
    op.create_index(
        "ix_inv_attr_sets_company_id", "inventory_attribute_sets", ["company_id"]
    )

    # ── 7. inventory_attribute_set_memberships ────────────────────────────
    op.create_table(
        "inventory_attribute_set_memberships",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attribute_set_id", sa.Uuid(), nullable=False),
        sa.Column("attribute_definition_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_inv_attr_set_mem_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["attribute_set_id"],
            ["inventory_attribute_sets.id"],
            name="fk_inv_attr_set_mem_set",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["attribute_definition_id"],
            ["inventory_attribute_definitions.id"],
            name="fk_inv_attr_set_mem_def",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "company_id",
            "attribute_set_id",
            "attribute_definition_id",
            name="uq_inv_attr_set_member",
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_inv_attr_set_mem_sort"),
        comment="AttributeSet to AttributeDefinition membership, scoped per company",
    )
    op.create_index(
        "ix_inv_attr_set_mem_set_id",
        "inventory_attribute_set_memberships",
        ["attribute_set_id"],
    )
    op.create_index(
        "ix_inv_attr_set_mem_def_id",
        "inventory_attribute_set_memberships",
        ["attribute_definition_id"],
    )

    # ── 8. inventory_tags ─────────────────────────────────────────────────
    op.create_table(
        "inventory_tags",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_inv_tags_company",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("company_id", "name", name="uq_inv_tags_company_name"),
        comment="Product tags for flexible grouping, scoped per company",
    )
    op.create_index("ix_inv_tags_company_id", "inventory_tags", ["company_id"])

    # ── 9. inventory_reason_codes ─────────────────────────────────────────
    op.create_table(
        "inventory_reason_codes",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("applies_to", sa.String(20), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_inv_reason_codes_company",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "company_id", "code", name="uq_inv_reason_codes_company_code"
        ),
        sa.CheckConstraint(
            "applies_to IN ('ADJUSTMENT', 'DAMAGE', 'RETURN')",
            name="ck_inv_reason_codes_applies_to",
        ),
        comment="Approved reason codes for stock operations, scoped per company",
    )
    op.create_index(
        "ix_inv_reason_codes_company_id", "inventory_reason_codes", ["company_id"]
    )
    op.create_index(
        "ix_inv_reason_codes_company_applies_to",
        "inventory_reason_codes",
        ["company_id", "applies_to"],
    )

    # ── 10. inventory_custom_field_definitions ───────────────────────────
    op.create_table(
        "inventory_custom_field_definitions",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("field_key", sa.String(100), nullable=False),
        sa.Column("field_label", sa.String(200), nullable=False),
        sa.Column("data_type", sa.String(20), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("placeholder", sa.String(200), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_inv_cf_def_company",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "company_id",
            "entity_type",
            "field_key",
            name="uq_inv_cf_def_company_entity_key",
        ),
        sa.CheckConstraint(
            "entity_type IN ('PRODUCT', 'WAREHOUSE', 'CATEGORY', 'BRAND')",
            name="ck_inv_cf_def_entity_type",
        ),
        sa.CheckConstraint(
            "data_type IN ('TEXT', 'NUMBER', 'BOOLEAN', 'DATE', 'DROPDOWN')",
            name="ck_inv_cf_def_data_type",
        ),
        comment="Company-defined custom field schemas for inventory entities",
    )
    op.create_index(
        "ix_inv_cf_def_company_id", "inventory_custom_field_definitions", ["company_id"]
    )
    op.create_index(
        "ix_inv_cf_def_company_entity_type",
        "inventory_custom_field_definitions",
        ["company_id", "entity_type"],
    )


def downgrade() -> None:
    """Drop all Phase 1 master data tables in reverse FK-dependency order."""
    op.drop_table("inventory_custom_field_definitions")
    op.drop_table("inventory_reason_codes")
    op.drop_table("inventory_tags")
    op.drop_table("inventory_attribute_set_memberships")
    op.drop_table("inventory_attribute_sets")
    op.drop_table("inventory_attribute_definitions")
    op.drop_table("inventory_uom_conversions")
    op.drop_table("inventory_uoms")
    op.drop_table("inventory_brands")
    op.drop_table("inventory_categories")

"""027_sales_pricing

Create Pricing aggregate tables for Sales Phase 2:
  - price_lists
  - price_entries
  - customer_specific_prices
  - discount_rules

Revision ID: 027_sales_pricing
Revises: 026_sales_customers
Create Date: 2026-08-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "027_sales_pricing"
down_revision: str = "026_sales_customers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # price_lists
    # ------------------------------------------------------------------ #
    op.create_table(
        "price_lists",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("effective_from", sa.String(10), nullable=False),
        sa.Column("effective_to", sa.String(10), nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("customer_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("customer_category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_price_lists_company_name"),
        sa.CheckConstraint("priority >= 0", name="ck_price_lists_priority"),
        sa.CheckConstraint("version >= 1", name="ck_price_lists_version"),
        comment="Sales price lists — pricing aggregate root",
    )
    op.create_index("ix_price_lists_company_id", "price_lists", ["company_id"])
    op.create_index(
        "ix_price_lists_company_active", "price_lists", ["company_id", "is_active"]
    )
    op.create_index(
        "ix_price_lists_company_default", "price_lists", ["company_id", "is_default"]
    )
    op.create_index(
        "ix_price_lists_company_group",
        "price_lists",
        ["company_id", "customer_group_id"],
    )
    op.create_index(
        "ix_price_lists_company_category",
        "price_lists",
        ["company_id", "customer_category_id"],
    )

    # ------------------------------------------------------------------ #
    # price_entries
    # ------------------------------------------------------------------ #
    op.create_table(
        "price_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("price_list_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_price", sa.Numeric(15, 4), nullable=False),
        sa.Column(
            "minimum_quantity", sa.Numeric(12, 3), nullable=False, server_default="1"
        ),
        sa.Column(
            "unit_of_measure", sa.String(20), nullable=False, server_default="EA"
        ),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["price_list_id"], ["price_lists.id"], name="fk_price_entries_price_list"
        ),
        sa.CheckConstraint("unit_price >= 0", name="ck_price_entries_unit_price"),
        sa.CheckConstraint("minimum_quantity > 0", name="ck_price_entries_min_qty"),
        comment="Product prices within a price list",
    )
    op.create_index("ix_price_entries_company_id", "price_entries", ["company_id"])
    op.create_index(
        "ix_price_entries_lookup",
        "price_entries",
        ["company_id", "price_list_id", "product_id"],
    )

    # ------------------------------------------------------------------ #
    # customer_specific_prices
    # ------------------------------------------------------------------ #
    op.create_table(
        "customer_specific_prices",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_price", sa.Numeric(15, 4), nullable=False),
        sa.Column(
            "minimum_quantity", sa.Numeric(12, 3), nullable=False, server_default="1"
        ),
        sa.Column("effective_from", sa.String(10), nullable=False),
        sa.Column("effective_to", sa.String(10), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_customer_specific_prices_customer",
        ),
        sa.CheckConstraint("unit_price >= 0", name="ck_customer_specific_prices_price"),
        sa.CheckConstraint(
            "minimum_quantity > 0", name="ck_customer_specific_prices_min_qty"
        ),
        comment="Per-customer product price overrides",
    )
    op.create_index(
        "ix_customer_specific_prices_company_id",
        "customer_specific_prices",
        ["company_id"],
    )
    op.create_index(
        "ix_customer_specific_prices_lookup",
        "customer_specific_prices",
        ["company_id", "customer_id", "product_id"],
    )

    # ------------------------------------------------------------------ #
    # discount_rules
    # ------------------------------------------------------------------ #
    op.create_table(
        "discount_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("rule_type", sa.String(20), nullable=False),
        sa.Column(
            "applicability",
            sa.String(30),
            nullable=False,
            server_default="ALL_CUSTOMERS",
        ),
        sa.Column("applicability_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "product_scope",
            sa.String(25),
            nullable=False,
            server_default="ALL_PRODUCTS",
        ),
        sa.Column("product_scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("minimum_quantity", sa.Numeric(12, 3), nullable=True),
        sa.Column("minimum_order_value", sa.Numeric(15, 2), nullable=True),
        sa.Column("discount_value", sa.Numeric(15, 4), nullable=False),
        sa.Column("effective_from", sa.String(10), nullable=False),
        sa.Column("effective_to", sa.String(10), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_stackable", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "rule_type IN ('PERCENTAGE', 'FIXED_AMOUNT', 'VOLUME', 'PROMOTIONAL')",
            name="ck_discount_rules_rule_type",
        ),
        sa.CheckConstraint(
            "applicability IN ('ALL_CUSTOMERS', 'SPECIFIC_CATEGORY', 'SPECIFIC_GROUP', 'SPECIFIC_CUSTOMER')",
            name="ck_discount_rules_applicability",
        ),
        sa.CheckConstraint(
            "product_scope IN ('ALL_PRODUCTS', 'SPECIFIC_CATEGORY', 'SPECIFIC_PRODUCT')",
            name="ck_discount_rules_product_scope",
        ),
        sa.CheckConstraint("discount_value >= 0", name="ck_discount_rules_value"),
        sa.CheckConstraint("priority >= 0", name="ck_discount_rules_priority"),
        comment="Discount rules for automated discount application",
    )
    op.create_index("ix_discount_rules_company_id", "discount_rules", ["company_id"])
    op.create_index(
        "ix_discount_rules_company_active",
        "discount_rules",
        ["company_id", "is_active"],
    )
    op.create_index(
        "ix_discount_rules_company_active_from",
        "discount_rules",
        ["company_id", "is_active", "effective_from"],
    )


def downgrade() -> None:
    op.drop_table("discount_rules")
    op.drop_table("customer_specific_prices")
    op.drop_table("price_entries")
    op.drop_table("price_lists")

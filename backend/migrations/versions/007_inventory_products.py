"""Epic 005 — Inventory Management Phase 2: product tables.

Creates the following tables in FK-dependency order:
  1. inventory_products        — product aggregate root
  2. inventory_product_variants — variant child entities (own SKU)
  3. inventory_product_barcodes — barcode value objects (unique per company)
  4. inventory_product_images   — image references (S3 keys + URLs)

Indexes:
  - GIN index on search_vector using pg_trgm for fast ILIKE searches
  - B-tree composite on (company_id, product_code) for SKU lookup
  - B-tree composite on (company_id, variant_code) for variant SKU lookup
  - B-tree composite on (company_id, barcode_value) for barcode lookup

All tables follow the platform convention:
  - UUID primary key with gen_random_uuid() server default
  - created_at / updated_at with now() server default
  - company_id FK to companies.id
  - is_deleted / deleted_at for soft delete
  - VARCHAR status fields with CHECK constraints (no ENUM types)

Revision ID: 007
Revises:     006
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ── Revision identifiers ───────────────────────────────────────────────────

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all Phase 2 product tables."""

    # ── 1. inventory_products ─────────────────────────────────────────────
    op.create_table(
        "inventory_products",
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
        # Core
        sa.Column("product_code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column(
            "product_type", sa.String(20), nullable=False, server_default="STANDARD"
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("short_description", sa.String(500), nullable=True),
        # Foreign keys to master data
        sa.Column("base_uom_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=False), nullable=True),
        # Procurement / physical metadata (13 fields)
        sa.Column("hs_code", sa.String(20), nullable=True),
        sa.Column("country_of_origin", sa.String(100), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("min_order_qty", sa.Numeric(14, 4), nullable=True),
        sa.Column("max_order_qty", sa.Numeric(14, 4), nullable=True),
        sa.Column("reorder_point", sa.Numeric(14, 4), nullable=True),
        sa.Column("weight_kg", sa.Numeric(10, 4), nullable=True),
        sa.Column("width_cm", sa.Numeric(10, 4), nullable=True),
        sa.Column("height_cm", sa.Numeric(10, 4), nullable=True),
        sa.Column("depth_cm", sa.Numeric(10, 4), nullable=True),
        sa.Column(
            "is_serialized", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "is_batch_tracked", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("cost_price", sa.Numeric(14, 4), nullable=True),
        # Full-text search support
        sa.Column("search_vector", sa.Text(), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
            name="fk_inv_products_company",
        ),
        sa.ForeignKeyConstraint(
            ["base_uom_id"],
            ["inventory_uoms.id"],
            ondelete="RESTRICT",
            name="fk_inv_products_base_uom",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["inventory_categories.id"],
            ondelete="SET NULL",
            name="fk_inv_products_category",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"],
            ["inventory_brands.id"],
            ondelete="SET NULL",
            name="fk_inv_products_brand",
        ),
        sa.UniqueConstraint(
            "company_id", "product_code", name="uq_inv_products_company_code"
        ),
        sa.CheckConstraint(
            "product_type IN ('STANDARD', 'VARIANT', 'SERVICE', 'BUNDLE', 'RAW_MATERIAL')",
            name="ck_inv_products_type",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'INACTIVE', 'DISCONTINUED', 'ARCHIVED')",
            name="ck_inv_products_status",
        ),
        comment="Product catalogue entries, scoped per company",
    )

    # B-tree indexes
    op.create_index("ix_inv_products_company_id", "inventory_products", ["company_id"])
    op.create_index(
        "ix_inv_products_company_status", "inventory_products", ["company_id", "status"]
    )
    op.create_index(
        "ix_inv_products_company_type",
        "inventory_products",
        ["company_id", "product_type"],
    )
    op.create_index(
        "ix_inv_products_category", "inventory_products", ["company_id", "category_id"]
    )
    op.create_index(
        "ix_inv_products_brand", "inventory_products", ["company_id", "brand_id"]
    )
    op.create_index(
        "ix_inv_products_search_vector", "inventory_products", ["search_vector"]
    )

    # GIN index for pg_trgm fast full-text search on search_vector
    # Note: cannot use CONCURRENTLY inside Alembic's transaction block;
    # use standard CREATE INDEX instead (equivalent performance after migration completes).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_inv_products_search_gin "
        "ON inventory_products USING GIN (search_vector gin_trgm_ops)"
    )

    # ── 2. inventory_product_variants ─────────────────────────────────────
    op.create_table(
        "inventory_product_variants",
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
        sa.Column("product_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("variant_code", sa.String(100), nullable=False),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "is_stock_tracked", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
            name="fk_inv_variants_company",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["inventory_products.id"],
            ondelete="CASCADE",
            name="fk_inv_variants_product",
        ),
        sa.UniqueConstraint(
            "company_id", "variant_code", name="uq_inv_variants_company_sku"
        ),
        comment="Product variants with own SKU and attributes, per company",
    )
    op.create_index(
        "ix_inv_variants_product_id", "inventory_product_variants", ["product_id"]
    )
    op.create_index(
        "ix_inv_variants_company_id", "inventory_product_variants", ["company_id"]
    )

    # ── 3. inventory_product_barcodes ─────────────────────────────────────
    op.create_table(
        "inventory_product_barcodes",
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
        sa.Column("product_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("barcode_value", sa.String(100), nullable=False),
        sa.Column("barcode_type", sa.String(20), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
            name="fk_inv_barcodes_company",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["inventory_products.id"],
            ondelete="CASCADE",
            name="fk_inv_barcodes_product",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["inventory_product_variants.id"],
            ondelete="CASCADE",
            name="fk_inv_barcodes_variant",
        ),
        sa.UniqueConstraint(
            "company_id", "barcode_value", name="uq_inv_barcodes_company_value"
        ),
        sa.CheckConstraint(
            "barcode_type IN ('EAN13', 'EAN8', 'QR', 'CODE128', 'CUSTOM')",
            name="ck_inv_barcodes_type",
        ),
        comment="Product barcodes (EAN13, QR, CODE128, CUSTOM), unique per company",
    )
    op.create_index(
        "ix_inv_barcodes_product_id", "inventory_product_barcodes", ["product_id"]
    )
    op.create_index(
        "ix_inv_barcodes_variant_id", "inventory_product_barcodes", ["variant_id"]
    )
    op.create_index(
        "ix_inv_barcodes_company_value",
        "inventory_product_barcodes",
        ["company_id", "barcode_value"],
    )

    # ── 4. inventory_product_images ───────────────────────────────────────
    op.create_table(
        "inventory_product_images",
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
        sa.Column("product_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("thumbnail_url", sa.String(1000), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
            name="fk_inv_images_company",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["inventory_products.id"],
            ondelete="CASCADE",
            name="fk_inv_images_product",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["inventory_product_variants.id"],
            ondelete="CASCADE",
            name="fk_inv_images_variant",
        ),
        comment="Product images referencing S3 objects, per product or variant",
    )
    op.create_index(
        "ix_inv_images_product_id", "inventory_product_images", ["product_id"]
    )
    op.create_index(
        "ix_inv_images_variant_id", "inventory_product_images", ["variant_id"]
    )


def downgrade() -> None:
    """Drop all Phase 2 product tables in reverse FK order."""
    op.drop_table("inventory_product_images")
    op.drop_table("inventory_product_barcodes")
    op.drop_table("inventory_product_variants")
    op.execute("DROP INDEX IF EXISTS ix_inv_products_search_gin")
    op.drop_table("inventory_products")

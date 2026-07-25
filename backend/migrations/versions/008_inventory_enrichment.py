"""Epic 005 — Inventory Management Phase 3: product enrichment tables.

Creates the following tables in FK-dependency order:
  1. inventory_product_tags              — many-to-many product↔tag join
  2. inventory_product_custom_field_values — per-product custom field values
  3. inventory_product_internal_notes    — append-only product notes
  4. inventory_import_jobs               — bulk CSV/Excel import state tracking

All tables follow the platform convention:
  - UUID primary key with gen_random_uuid() server default
  - created_at / updated_at with now() server default
  - company_id FK to companies.id
  - is_deleted / deleted_at for soft delete

Revision ID: 008
Revises:     007
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ── Revision identifiers ───────────────────────────────────────────────────

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all Phase 3 product enrichment tables."""

    # ── 1. inventory_product_tags ──────────────────────────────────────────
    op.create_table(
        "inventory_product_tags",
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
        sa.Column("tag_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
            name="fk_inv_product_tags_company",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["inventory_products.id"],
            ondelete="CASCADE",
            name="fk_inv_product_tags_product",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["inventory_tags.id"],
            ondelete="CASCADE",
            name="fk_inv_product_tags_tag",
        ),
        sa.UniqueConstraint(
            "company_id",
            "product_id",
            "tag_id",
            name="uq_inv_product_tags_product_tag",
        ),
        comment="Many-to-many join between inventory_products and inventory_tags",
    )
    op.create_index(
        "ix_inv_product_tags_product_id", "inventory_product_tags", ["product_id"]
    )
    op.create_index("ix_inv_product_tags_tag_id", "inventory_product_tags", ["tag_id"])

    # ── 2. inventory_product_custom_field_values ───────────────────────────
    op.create_table(
        "inventory_product_custom_field_values",
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
        sa.Column("field_key", sa.String(100), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_number", sa.String(50), nullable=True),
        sa.Column("value_bool", sa.Boolean(), nullable=True),
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
            name="fk_inv_product_cfv_company",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["inventory_products.id"],
            ondelete="CASCADE",
            name="fk_inv_product_cfv_product",
        ),
        sa.UniqueConstraint(
            "company_id",
            "product_id",
            "field_key",
            name="uq_inv_product_cfv_product_field",
        ),
        comment="Per-product values for company-defined custom fields",
    )
    op.create_index(
        "ix_inv_product_cfv_product_id",
        "inventory_product_custom_field_values",
        ["product_id"],
    )

    # ── 3. inventory_product_internal_notes ───────────────────────────────
    op.create_table(
        "inventory_product_internal_notes",
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
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
            name="fk_inv_product_notes_company",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["inventory_products.id"],
            ondelete="CASCADE",
            name="fk_inv_product_notes_product",
        ),
        comment="Append-only internal notes for products (no edit/delete)",
    )
    op.create_index(
        "ix_inv_product_notes_product_id",
        "inventory_product_internal_notes",
        ["product_id"],
    )

    # ── 4. inventory_import_jobs ───────────────────────────────────────────
    op.create_table(
        "inventory_import_jobs",
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
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_rows", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
            name="fk_inv_import_jobs_company",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'FAILED_WITH_ERRORS')",
            name="ck_inv_import_jobs_status",
        ),
        comment="Bulk product import job tracking table",
    )
    op.create_index(
        "ix_inv_import_jobs_company_id", "inventory_import_jobs", ["company_id"]
    )


def downgrade() -> None:
    """Drop all Phase 3 enrichment tables in reverse FK order."""
    op.drop_table("inventory_import_jobs")
    op.drop_table("inventory_product_internal_notes")
    op.drop_table("inventory_product_custom_field_values")
    op.drop_table("inventory_product_tags")

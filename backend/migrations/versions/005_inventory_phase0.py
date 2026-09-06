"""Epic 005 — Inventory Management Phase 0: module scaffold tables.

Creates the following tables:
  1. inventory_feature_flags — per-company feature flag overrides

Also enables the ``pg_trgm`` extension for future full-text search
(required for product name/SKU/barcode trigram indexes in Phase 2).

No PostgreSQL ENUM types — status values use VARCHAR with CHECK constraints
for forward compatibility.

Revision ID: 005
Revises:     004
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# ── Revision identifiers ───────────────────────────────────────────────────

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create inventory phase 0 tables and enable pg_trgm."""

    # Enable pg_trgm for future full-text / trigram search on products
    # (IF NOT EXISTS is safe to re-run).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── inventory_feature_flags ────────────────────────────────────────
    op.create_table(
        "inventory_feature_flags",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
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
            onupdate=sa.text("now()"),
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("flag_key", sa.String(120), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_inventory_ff_company",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "company_id",
            "flag_key",
            name="uq_inventory_ff_company_key",
        ),
        sa.CheckConstraint(
            "flag_key LIKE 'inventory.%'",
            name="ck_inventory_ff_key_prefix",
        ),
        comment="Per-company feature flag overrides for the Inventory module",
    )

    # Indexes
    op.create_index(
        "ix_inventory_feature_flags_company_id",
        "inventory_feature_flags",
        ["company_id"],
    )
    op.create_index(
        "ix_inventory_feature_flags_flag_key",
        "inventory_feature_flags",
        ["flag_key"],
    )
    op.create_index(
        "ix_inventory_feature_flags_company_key",
        "inventory_feature_flags",
        ["company_id", "flag_key"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    """Drop inventory phase 0 tables."""
    op.drop_index(
        "ix_inventory_feature_flags_company_key",
        table_name="inventory_feature_flags",
    )
    op.drop_index(
        "ix_inventory_feature_flags_flag_key",
        table_name="inventory_feature_flags",
    )
    op.drop_index(
        "ix_inventory_feature_flags_company_id",
        table_name="inventory_feature_flags",
    )
    op.drop_table("inventory_feature_flags")
    # Note: we do NOT drop pg_trgm on downgrade as other extensions may use it.

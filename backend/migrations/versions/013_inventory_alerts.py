"""inventory alerts — Phase 8

Creates:
  - inventory_reorder_rules       (per-product/warehouse reorder configuration)
  - inventory_low_stock_alerts    (low-stock / overstock alerts with state machine)
  - inventory_reorder_suggestions (suggestions triggered by alerts)

Revision ID: 013
Revises: 012
Create Date: 2026-07-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ReorderRule ──────────────────────────────────────────────────────────
    op.create_table(
        "inventory_reorder_rules",
        # TenantBaseModel columns
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        # Domain columns
        sa.Column("product_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("variant_id", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("warehouse_id", PG_UUID(as_uuid=False), nullable=True),
        sa.Column(
            "reorder_level", sa.Numeric(18, 4), nullable=False, server_default="0"
        ),
        sa.Column(
            "reorder_quantity", sa.Numeric(18, 4), nullable=False, server_default="1"
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        # Constraints
        sa.CheckConstraint(
            "reorder_level >= 0", name="ck_reorder_rule_reorder_level_non_negative"
        ),
        sa.CheckConstraint(
            "reorder_quantity > 0", name="ck_reorder_rule_reorder_qty_positive"
        ),
        comment="Per-product reorder rules for automatic reorder suggestions",
    )
    op.create_index(
        "ix_inv_reorder_rules_company_product",
        "inventory_reorder_rules",
        ["company_id", "product_id"],
    )
    op.create_index(
        "ix_inv_reorder_rules_company_id", "inventory_reorder_rules", ["company_id"]
    )

    # ── LowStockAlert ────────────────────────────────────────────────────────
    op.create_table(
        "inventory_low_stock_alerts",
        # TenantBaseModel columns
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        # Domain columns
        sa.Column("product_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("variant_id", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("warehouse_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("alert_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("current_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("threshold_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # Constraints
        sa.CheckConstraint(
            "alert_type IN ('OUT_OF_STOCK', 'SAFETY_STOCK_BREACH', 'LOW_STOCK', 'OVERSTOCK')",
            name="ck_inv_alert_type",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')",
            name="ck_inv_alert_status",
        ),
        comment="Low-stock and overstock alerts raised by inventory intelligence",
    )
    op.create_index(
        "ix_inv_alert_company_status",
        "inventory_low_stock_alerts",
        ["company_id", "status"],
    )
    op.create_index(
        "ix_inv_alert_company_product",
        "inventory_low_stock_alerts",
        ["company_id", "product_id"],
    )
    # Partial unique index for deduplication — only one OPEN alert per type × product × warehouse
    op.execute(
        """
        CREATE UNIQUE INDEX uq_inv_alert_open_dedup
        ON inventory_low_stock_alerts (company_id, product_id, warehouse_id, alert_type)
        WHERE status = 'OPEN'
        """
    )

    # ── ReorderSuggestion ────────────────────────────────────────────────────
    op.create_table(
        "inventory_reorder_suggestions",
        # TenantBaseModel columns
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        # Domain columns
        sa.Column("product_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("variant_id", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("warehouse_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("suggested_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("triggered_by_alert_id", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("notes", sa.Text(), nullable=True),
        # Constraints
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACKNOWLEDGED', 'CONVERTED')",
            name="ck_inv_suggestion_status",
        ),
        comment="Reorder suggestions triggered by low-stock alerts",
    )
    op.create_index(
        "ix_inv_suggestion_company_status",
        "inventory_reorder_suggestions",
        ["company_id", "status"],
    )
    op.create_index(
        "ix_inv_suggestion_company_product",
        "inventory_reorder_suggestions",
        ["company_id", "product_id"],
    )


def downgrade() -> None:
    op.drop_table("inventory_reorder_suggestions")
    op.execute("DROP INDEX IF EXISTS uq_inv_alert_open_dedup")
    op.drop_table("inventory_low_stock_alerts")
    op.drop_table("inventory_reorder_rules")

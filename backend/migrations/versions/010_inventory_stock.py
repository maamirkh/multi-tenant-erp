"""inventory stock — Phase 5

Creates:
  - inventory_stock_positions     (mutable position per product+warehouse)
  - inventory_stock_movements     (immutable ledger)
  - inventory_fifo_cost_layers    (FIFO cost queue)
  - inventory_snapshots           (snapshot header)
  - inventory_snapshot_lines      (snapshot lines)

Also wires the archive guard: inventory_stock_positions is now queryable.

Revision ID: 010
Revises: 009
Create Date: 2026-07-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None

_MOVEMENT_TYPES = (
    "'OPENING','PURCHASE_RECEIPT','SALES_ISSUE','ADJUSTMENT_IN','ADJUSTMENT_OUT',"
    "'TRANSFER_IN','TRANSFER_OUT','RETURN_IN','RETURN_OUT','DAMAGE','WRITE_OFF','SNAPSHOT'"
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # inventory_stock_positions
    # ------------------------------------------------------------------
    op.create_table(
        "inventory_stock_positions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # FKs
        sa.Column(
            "product_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("inventory_products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "variant_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("inventory_product_variants.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "warehouse_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("inventory_warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # Quantities
        sa.Column("qty_on_hand", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column(
            "qty_reserved", sa.Numeric(18, 4), nullable=False, server_default="0"
        ),
        sa.Column("qty_damaged", sa.Numeric(18, 4), nullable=False, server_default="0"),
        # Cost
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=True),
        # Thresholds
        sa.Column(
            "safety_stock", sa.Numeric(18, 4), nullable=False, server_default="0"
        ),
        sa.Column(
            "minimum_stock", sa.Numeric(18, 4), nullable=False, server_default="0"
        ),
        sa.Column("maximum_stock", sa.Numeric(18, 4), nullable=True),
        sa.Column(
            "reorder_level", sa.Numeric(18, 4), nullable=False, server_default="0"
        ),
        # Constraints
        sa.UniqueConstraint(
            "company_id",
            "product_id",
            "warehouse_id",
            "variant_id",
            name="uq_inv_stock_pos_product_wh",
        ),
        comment="Real-time stock position per product + warehouse",
    )
    op.create_index(
        "ix_inv_stock_pos_company_id", "inventory_stock_positions", ["company_id"]
    )
    op.create_index(
        "ix_inv_stock_pos_product_id", "inventory_stock_positions", ["product_id"]
    )
    op.create_index(
        "ix_inv_stock_pos_warehouse_id", "inventory_stock_positions", ["warehouse_id"]
    )

    # ------------------------------------------------------------------
    # inventory_stock_movements (immutable ledger)
    # ------------------------------------------------------------------
    op.create_table(
        "inventory_stock_movements",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # FKs
        sa.Column(
            "product_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("inventory_products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "variant_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column(
            "warehouse_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("inventory_warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # Movement fields
        sa.Column("movement_type", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(3), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=True),
        sa.Column("total_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column(
            "reference_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
        # Constraints
        sa.CheckConstraint(
            f"movement_type IN ({_MOVEMENT_TYPES})",
            name="ck_inv_stock_mov_type",
        ),
        sa.CheckConstraint(
            "direction IN ('IN', 'OUT')", name="ck_inv_stock_mov_direction"
        ),
        comment="Immutable stock ledger — INSERT only, never UPDATE or DELETE",
    )
    op.create_index(
        "ix_inv_stock_mov_company_id", "inventory_stock_movements", ["company_id"]
    )
    op.create_index(
        "ix_inv_stock_mov_product_id", "inventory_stock_movements", ["product_id"]
    )
    op.create_index(
        "ix_inv_stock_mov_warehouse_id", "inventory_stock_movements", ["warehouse_id"]
    )
    op.create_index(
        "ix_inv_stock_mov_performed_at", "inventory_stock_movements", ["performed_at"]
    )

    # ------------------------------------------------------------------
    # inventory_fifo_cost_layers
    # ------------------------------------------------------------------
    op.create_table(
        "inventory_fifo_cost_layers",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "product_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("inventory_products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "variant_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column(
            "warehouse_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("inventory_warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("remaining_qty", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "movement_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        comment="FIFO cost queue — ordered by created_at",
    )
    op.create_index(
        "ix_inv_fifo_layers_product_wh",
        "inventory_fifo_cost_layers",
        ["product_id", "warehouse_id"],
    )
    op.create_index(
        "ix_inv_fifo_layers_company_id", "inventory_fifo_cost_layers", ["company_id"]
    )

    # ------------------------------------------------------------------
    # inventory_snapshots
    # ------------------------------------------------------------------
    op.create_table(
        "inventory_snapshots",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snapshot_name", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("total_products", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_warehouses", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'COMPLETED', 'FAILED')",
            name="ck_inv_snapshots_status",
        ),
        comment="Point-in-time inventory snapshot headers",
    )
    op.create_index(
        "ix_inv_snapshots_company_id", "inventory_snapshots", ["company_id"]
    )

    # ------------------------------------------------------------------
    # inventory_snapshot_lines
    # ------------------------------------------------------------------
    op.create_table(
        "inventory_snapshot_lines",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "snapshot_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("inventory_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False
        ),
        sa.Column(
            "variant_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column(
            "warehouse_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False
        ),
        sa.Column("qty_on_hand", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column(
            "qty_reserved", sa.Numeric(18, 4), nullable=False, server_default="0"
        ),
        sa.Column("qty_damaged", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=True),
        comment="Individual stock position lines within an inventory snapshot",
    )
    op.create_index(
        "ix_inv_snapshot_lines_snapshot_id",
        "inventory_snapshot_lines",
        ["snapshot_id"],
    )
    op.create_index(
        "ix_inv_snapshot_lines_company_id", "inventory_snapshot_lines", ["company_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inv_snapshot_lines_company_id", table_name="inventory_snapshot_lines"
    )
    op.drop_index(
        "ix_inv_snapshot_lines_snapshot_id", table_name="inventory_snapshot_lines"
    )
    op.drop_table("inventory_snapshot_lines")
    op.drop_index("ix_inv_snapshots_company_id", table_name="inventory_snapshots")
    op.drop_table("inventory_snapshots")
    op.drop_index(
        "ix_inv_fifo_layers_company_id", table_name="inventory_fifo_cost_layers"
    )
    op.drop_index(
        "ix_inv_fifo_layers_product_wh", table_name="inventory_fifo_cost_layers"
    )
    op.drop_table("inventory_fifo_cost_layers")
    op.drop_index(
        "ix_inv_stock_mov_performed_at", table_name="inventory_stock_movements"
    )
    op.drop_index(
        "ix_inv_stock_mov_warehouse_id", table_name="inventory_stock_movements"
    )
    op.drop_index("ix_inv_stock_mov_product_id", table_name="inventory_stock_movements")
    op.drop_index("ix_inv_stock_mov_company_id", table_name="inventory_stock_movements")
    op.drop_table("inventory_stock_movements")
    op.drop_index(
        "ix_inv_stock_pos_warehouse_id", table_name="inventory_stock_positions"
    )
    op.drop_index("ix_inv_stock_pos_product_id", table_name="inventory_stock_positions")
    op.drop_index("ix_inv_stock_pos_company_id", table_name="inventory_stock_positions")
    op.drop_table("inventory_stock_positions")

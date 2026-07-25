"""inventory stock transfers — Phase 7

Creates:
  - inventory_stock_transfers  (transfer header with optimistic lock)
  - inventory_stock_transfer_lines  (line items per product)

Revision ID: 012
Revises: 011
Create Date: 2026-07-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Header table ────────────────────────────────────────────────────────
    op.create_table(
        "inventory_stock_transfers",
        # TenantBaseModel columns
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "company_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # Transfer-specific columns
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "source_warehouse_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column(
            "destination_warehouse_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column("reference_no", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_reason", sa.Text(), nullable=True),
        # CHECK constraint
        sa.CheckConstraint(
            "status IN ('DRAFT', 'IN_TRANSIT', 'COMPLETED', 'CANCELLED')",
            name="ck_inv_transfer_status",
        ),
    )

    op.create_index(
        "ix_inv_transfer_company_id", "inventory_stock_transfers", ["company_id"]
    )
    op.create_index(
        "ix_inv_transfer_source_wh",
        "inventory_stock_transfers",
        ["source_warehouse_id"],
    )
    op.create_index(
        "ix_inv_transfer_dest_wh",
        "inventory_stock_transfers",
        ["destination_warehouse_id"],
    )
    op.create_index("ix_inv_transfer_status", "inventory_stock_transfers", ["status"])

    # ── Lines table ──────────────────────────────────────────────────────────
    op.create_table(
        "inventory_stock_transfer_lines",
        # TenantBaseModel columns
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "company_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # Line-specific columns
        sa.Column(
            "transfer_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("inventory_stock_transfers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column(
            "variant_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=True),
        sa.Column(
            "source_movement_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "destination_movement_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "reversal_movement_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_inv_trf_line_transfer_id", "inventory_stock_transfer_lines", ["transfer_id"]
    )
    op.create_index(
        "ix_inv_trf_line_company_id", "inventory_stock_transfer_lines", ["company_id"]
    )
    op.create_index(
        "ix_inv_trf_line_product_id", "inventory_stock_transfer_lines", ["product_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inv_trf_line_product_id", table_name="inventory_stock_transfer_lines"
    )
    op.drop_index(
        "ix_inv_trf_line_company_id", table_name="inventory_stock_transfer_lines"
    )
    op.drop_index(
        "ix_inv_trf_line_transfer_id", table_name="inventory_stock_transfer_lines"
    )
    op.drop_table("inventory_stock_transfer_lines")

    op.drop_index("ix_inv_transfer_status", table_name="inventory_stock_transfers")
    op.drop_index("ix_inv_transfer_dest_wh", table_name="inventory_stock_transfers")
    op.drop_index("ix_inv_transfer_source_wh", table_name="inventory_stock_transfers")
    op.drop_index("ix_inv_transfer_company_id", table_name="inventory_stock_transfers")
    op.drop_table("inventory_stock_transfers")

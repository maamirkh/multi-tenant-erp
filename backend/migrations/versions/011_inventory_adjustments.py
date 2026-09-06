"""inventory adjustments — Phase 6

Creates:
  - inventory_adjustments  (adjustment aggregate with optimistic lock)

Revision ID: 011
Revises: 010
Create Date: 2026-07-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_adjustments",
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
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # Product / warehouse identity
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
        sa.Column(
            "warehouse_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column(
            "reason_code_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        # Adjustment details
        sa.Column("movement_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # State machine
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        # Stock snapshot
        sa.Column("old_quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("new_quantity", sa.Numeric(18, 4), nullable=True),
        # Workflow actors
        sa.Column(
            "submitted_by",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "approved_by",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "rejected_by",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        # Ledger link
        sa.Column(
            "reference_movement_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        # Constraints
        sa.CheckConstraint(
            "status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED')",
            name="ck_inv_adj_status",
        ),
        sa.CheckConstraint(
            "movement_type IN ('ADJUSTMENT_IN', 'ADJUSTMENT_OUT')",
            name="ck_inv_adj_movement_type",
        ),
        comment="Inventory adjustment aggregate — approval workflow with optimistic lock",
    )

    op.create_index("ix_inv_adj_company_id", "inventory_adjustments", ["company_id"])
    op.create_index("ix_inv_adj_product_id", "inventory_adjustments", ["product_id"])
    op.create_index(
        "ix_inv_adj_warehouse_id", "inventory_adjustments", ["warehouse_id"]
    )
    op.create_index("ix_inv_adj_status", "inventory_adjustments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_inv_adj_status", table_name="inventory_adjustments")
    op.drop_index("ix_inv_adj_warehouse_id", table_name="inventory_adjustments")
    op.drop_index("ix_inv_adj_product_id", table_name="inventory_adjustments")
    op.drop_index("ix_inv_adj_company_id", table_name="inventory_adjustments")
    op.drop_table("inventory_adjustments")

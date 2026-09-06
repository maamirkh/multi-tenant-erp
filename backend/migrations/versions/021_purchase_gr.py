"""Purchase Goods Receiving — Phase 6.

Creates:
  goods_receipts — GR aggregate root
  gr_lines       — GR line items with PPV computation

Revision ID: 021
Revises: 020
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: str = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # goods_receipts
    # ------------------------------------------------------------------
    op.create_table(
        "goods_receipts",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("gr_number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), server_default="DRAFT", nullable=False),
        sa.Column("po_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "supplier_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False
        ),
        sa.Column(
            "received_by", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_note_number", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "warehouse_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column(
            "landed_cost_ready",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','CONFIRMED')",
            name="ck_goods_receipts_status",
        ),
        sa.UniqueConstraint(
            "company_id", "gr_number", name="uq_goods_receipts_company_number"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Goods receipt documents — physical receipt of ordered goods",
    )
    op.create_index("ix_goods_receipts_company_id", "goods_receipts", ["company_id"])
    op.create_index("ix_goods_receipts_po_id", "goods_receipts", ["po_id"])
    op.create_index("ix_goods_receipts_status", "goods_receipts", ["status"])

    # ------------------------------------------------------------------
    # gr_lines
    # ------------------------------------------------------------------
    op.create_table(
        "gr_lines",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("gr_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "po_line_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False
        ),
        sa.Column(
            "product_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column(
            "quantity_received",
            sa.Numeric(15, 3),
            server_default="0.000",
            nullable=False,
        ),
        sa.Column(
            "quantity_rejected",
            sa.Numeric(15, 3),
            server_default="0.000",
            nullable=False,
        ),
        sa.Column(
            "rejection_reason_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "unit_cost",
            sa.Numeric(15, 4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column(
            "po_unit_cost",
            sa.Numeric(15, 4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column(
            "ppv_amount",
            sa.Numeric(15, 2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column(
            "ppv_percentage",
            sa.Numeric(8, 4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "quantity_received >= 0",
            name="ck_gr_lines_quantity_received_non_negative",
        ),
        sa.CheckConstraint(
            "quantity_rejected >= 0",
            name="ck_gr_lines_quantity_rejected_non_negative",
        ),
        sa.CheckConstraint(
            "unit_cost >= 0",
            name="ck_gr_lines_unit_cost_non_negative",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Goods receipt line items with PPV computation",
    )
    op.create_index("ix_gr_lines_gr_id", "gr_lines", ["gr_id"])
    op.create_index("ix_gr_lines_po_line_id", "gr_lines", ["po_line_id"])


def downgrade() -> None:
    op.drop_table("gr_lines")
    op.drop_table("goods_receipts")

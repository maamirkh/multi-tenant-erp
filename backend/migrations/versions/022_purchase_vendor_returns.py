"""Purchase Vendor Returns — Phase 7.

Creates:
  vendor_returns — RMA aggregate root
  return_lines   — RMA line items

Revision ID: 022
Revises: 021
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: str = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # vendor_returns
    # ------------------------------------------------------------------
    op.create_table(
        "vendor_returns",
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
        # RMA fields
        sa.Column("rma_number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), server_default="DRAFT", nullable=False),
        sa.Column("gr_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "supplier_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False
        ),
        sa.Column(
            "initiated_by", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column(
            "reason_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "replacement_po_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "credit_note_pending",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','DISPATCHED','COMPLETED','CANCELLED')",
            name="ck_vendor_returns_status",
        ),
        sa.UniqueConstraint(
            "company_id", "rma_number", name="uq_vendor_returns_company_number"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Vendor Return (RMA) documents — return of goods to supplier",
    )
    op.create_index("ix_vendor_returns_company_id", "vendor_returns", ["company_id"])
    op.create_index("ix_vendor_returns_gr_id", "vendor_returns", ["gr_id"])
    op.create_index("ix_vendor_returns_status", "vendor_returns", ["status"])
    op.create_index("ix_vendor_returns_supplier_id", "vendor_returns", ["supplier_id"])

    # ------------------------------------------------------------------
    # return_lines
    # ------------------------------------------------------------------
    op.create_table(
        "return_lines",
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
        # ReturnLine fields
        sa.Column(
            "return_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False
        ),
        sa.Column(
            "gr_line_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False
        ),
        sa.Column(
            "product_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column(
            "quantity_returned",
            sa.Numeric(15, 3),
            server_default="0.000",
            nullable=False,
        ),
        sa.Column(
            "reason_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "quantity_returned >= 0",
            name="ck_return_lines_quantity_non_negative",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Vendor return line items",
    )
    op.create_index("ix_return_lines_company_id", "return_lines", ["company_id"])
    op.create_index("ix_return_lines_return_id", "return_lines", ["return_id"])
    op.create_index("ix_return_lines_gr_line_id", "return_lines", ["gr_line_id"])


def downgrade() -> None:
    op.drop_table("return_lines")
    op.drop_table("vendor_returns")

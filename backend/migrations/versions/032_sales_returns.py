"""032_sales_returns

Create Sales Return aggregate tables for Phase 7:
  - sales_returns
  - sales_return_lines

Revision ID: 032_sales_returns
Revises: 031_sales_invoices
Create Date: 2026-08-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "032_sales_returns"
down_revision: str = "031_sales_invoices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- sales_returns --------------------------------------------------------
    op.create_table(
        "sales_returns",
        # Core TenantBaseModel fields
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # Identification
        sa.Column("return_number", sa.String(30), nullable=False),
        # References
        sa.Column("customer_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column(
            "replacement_order_id", postgresql.UUID(as_uuid=False), nullable=True
        ),
        # Return details
        sa.Column("return_date", sa.String(10), nullable=False),
        sa.Column("reason_code_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("reason_description", sa.Text(), nullable=True),
        sa.Column(
            "resolution_type",
            sa.String(20),
            server_default="CREDIT_NOTE",
            nullable=False,
        ),
        # Status
        sa.Column("status", sa.String(25), server_default="DRAFT", nullable=False),
        sa.Column("approval_version", sa.Integer(), server_default="1", nullable=False),
        # Receipt
        sa.Column("received_by", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("received_at", sa.String(30), nullable=True),
        # Financial
        sa.Column("credit_note_amount", sa.Numeric(15, 2), nullable=True),
        # Notes
        sa.Column("internal_notes", sa.Text(), nullable=True),
        # Optimistic locking
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "return_number",
            name="uq_sales_returns_company_number",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', "
            "'RECEIVED', 'INSPECTED', 'COMPLETED', 'CANCELLED')",
            name="ck_sales_returns_status",
        ),
        sa.CheckConstraint(
            "resolution_type IN ('CREDIT_NOTE', 'REPLACEMENT', 'REFUND_READINESS')",
            name="ck_sales_returns_resolution_type",
        ),
    )
    op.create_index("ix_sales_returns_company_id", "sales_returns", ["company_id"])
    op.create_index("ix_sales_returns_customer_id", "sales_returns", ["customer_id"])
    op.create_index("ix_sales_returns_status", "sales_returns", ["status"])
    op.create_index(
        "ix_sales_returns_company_status", "sales_returns", ["company_id", "status"]
    )
    op.create_index("ix_sales_returns_order_id", "sales_returns", ["order_id"])

    # ---- sales_return_lines ---------------------------------------------------------
    op.create_table(
        "sales_return_lines",
        # Core TenantBaseModel fields
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # References
        sa.Column("return_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("reason_code_id", postgresql.UUID(as_uuid=False), nullable=True),
        # Item details
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity_returned", sa.Numeric(12, 3), nullable=False),
        sa.Column(
            "quantity_accepted",
            sa.Numeric(12, 3),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "quantity_rejected",
            sa.Numeric(12, 3),
            server_default="0",
            nullable=False,
        ),
        sa.Column("unit_price", sa.Numeric(15, 4), nullable=False),
        sa.Column("extended_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("condition", sa.String(20), server_default="USED", nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "quantity_returned > 0", name="ck_sales_return_lines_qty_returned_positive"
        ),
        sa.CheckConstraint(
            "quantity_accepted >= 0", name="ck_sales_return_lines_qty_accepted_nonneg"
        ),
        sa.CheckConstraint(
            "quantity_rejected >= 0", name="ck_sales_return_lines_qty_rejected_nonneg"
        ),
        sa.CheckConstraint(
            "condition IN ('NEW', 'USED', 'DAMAGED', 'DEFECTIVE')",
            name="ck_sales_return_lines_condition",
        ),
    )
    op.create_index(
        "ix_sales_return_lines_return_id", "sales_return_lines", ["return_id"]
    )
    op.create_index(
        "ix_sales_return_lines_product_id", "sales_return_lines", ["product_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_sales_return_lines_product_id", table_name="sales_return_lines")
    op.drop_index("ix_sales_return_lines_return_id", table_name="sales_return_lines")
    op.drop_table("sales_return_lines")

    op.drop_index("ix_sales_returns_order_id", table_name="sales_returns")
    op.drop_index("ix_sales_returns_company_status", table_name="sales_returns")
    op.drop_index("ix_sales_returns_status", table_name="sales_returns")
    op.drop_index("ix_sales_returns_customer_id", table_name="sales_returns")
    op.drop_index("ix_sales_returns_company_id", table_name="sales_returns")
    op.drop_table("sales_returns")

"""Purchase Requests — Phase 4.

Creates:
  purchase_requests — PR aggregate root
  pr_lines          — PR line items
  purchase_orders   — minimal PO stub (expanded in Phase 5)

Revision ID: 019
Revises: 018
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: str = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # purchase_requests
    # ------------------------------------------------------------------
    op.create_table(
        "purchase_requests",
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
        sa.Column("pr_number", sa.String(30), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("status", sa.String(20), server_default="DRAFT", nullable=False),
        sa.Column(
            "requestor_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False
        ),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("required_by_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "total_estimated_cost",
            sa.Numeric(15, 2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column("currency_code", sa.String(3), server_default="USD", nullable=False),
        sa.Column(
            "converted_to_po_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "branch_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','UNDER_REVIEW','APPROVED','REJECTED','CANCELLED')",
            name="ck_purchase_requests_status",
        ),
        sa.UniqueConstraint(
            "company_id", "pr_number", name="uq_purchase_requests_company_number"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Purchase requisition documents",
    )
    op.create_index(
        "ix_purchase_requests_company_id", "purchase_requests", ["company_id"]
    )
    op.create_index(
        "ix_purchase_requests_requestor_id", "purchase_requests", ["requestor_id"]
    )
    op.create_index("ix_purchase_requests_status", "purchase_requests", ["status"])

    # ------------------------------------------------------------------
    # pr_lines
    # ------------------------------------------------------------------
    op.create_table(
        "pr_lines",
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
        sa.Column("pr_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column(
            "product_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column("product_description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(15, 3), nullable=False),
        sa.Column("uom_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column(
            "estimated_unit_cost",
            sa.Numeric(15, 4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column(
            "estimated_line_total",
            sa.Numeric(15, 2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("quantity > 0", name="ck_pr_lines_quantity_positive"),
        sa.CheckConstraint(
            "estimated_unit_cost >= 0", name="ck_pr_lines_unit_cost_non_negative"
        ),
        sa.UniqueConstraint("pr_id", "line_number", name="uq_pr_lines_pr_line"),
        sa.PrimaryKeyConstraint("id"),
        comment="Purchase request line items",
    )
    op.create_index("ix_pr_lines_pr_id", "pr_lines", ["pr_id"])

    # ------------------------------------------------------------------
    # purchase_orders  (minimal stub — expanded in Phase 5)
    # ------------------------------------------------------------------
    op.create_table(
        "purchase_orders",
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
        sa.Column("po_number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), server_default="DRAFT", nullable=False),
        sa.Column(
            "purchase_request_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','REJECTED',"
            "'PARTIALLY_RECEIVED','FULLY_RECEIVED','CLOSED','CANCELLED')",
            name="ck_purchase_orders_status",
        ),
        sa.UniqueConstraint(
            "company_id", "po_number", name="uq_purchase_orders_company_number"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Purchase orders — stub for Phase 4, expanded in Phase 5",
    )
    op.create_index("ix_purchase_orders_company_id", "purchase_orders", ["company_id"])


def downgrade() -> None:
    op.drop_table("purchase_orders")
    op.drop_table("pr_lines")
    op.drop_table("purchase_requests")

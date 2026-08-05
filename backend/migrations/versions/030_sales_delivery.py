"""030_sales_delivery

Create Delivery Note aggregate tables for Phase 5:
  - delivery_notes
  - delivery_note_lines

Revision ID: 030_sales_delivery
Revises: 029_sales_orders
Create Date: 2026-08-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "030_sales_delivery"
down_revision: str = "029_sales_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # delivery_notes
    # ------------------------------------------------------------------ #
    op.create_table(
        "delivery_notes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delivery_number", sa.String(30), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shipping_address_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dispatch_date", sa.String(10), nullable=True),
        sa.Column("expected_delivery_date", sa.String(10), nullable=True),
        sa.Column("carrier", sa.String(200), nullable=True),
        sa.Column("tracking_number", sa.String(100), nullable=True),
        sa.Column("status", sa.String(15), nullable=False, server_default="DRAFT"),
        sa.Column("total_packages", sa.Integer, nullable=True),
        sa.Column("total_weight", sa.Numeric(10, 3), nullable=True),
        sa.Column("dispatched_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("internal_notes", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'DISPATCHED', 'DELIVERED', 'CANCELLED')",
            name="ck_delivery_notes_status",
        ),
        sa.CheckConstraint("version >= 1", name="ck_delivery_notes_version"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "delivery_number",
            name="uq_delivery_notes_company_number",
        ),
        comment="Delivery Note aggregate root — physical dispatch record",
    )
    op.create_index("ix_delivery_notes_company_id", "delivery_notes", ["company_id"])
    op.create_index(
        "ix_delivery_notes_company_order",
        "delivery_notes",
        ["company_id", "order_id"],
    )
    op.create_index(
        "ix_delivery_notes_company_status",
        "delivery_notes",
        ["company_id", "status"],
    )

    # ------------------------------------------------------------------ #
    # delivery_note_lines
    # ------------------------------------------------------------------ #
    op.create_table(
        "delivery_note_lines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delivery_note_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity_dispatched", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_of_measure", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "quantity_dispatched > 0",
            name="ck_dn_lines_quantity_positive",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Delivery Note line — quantity dispatched per order line",
    )
    op.create_index(
        "ix_delivery_note_lines_company_id",
        "delivery_note_lines",
        ["company_id"],
    )
    op.create_index(
        "ix_delivery_note_lines_dn",
        "delivery_note_lines",
        ["company_id", "delivery_note_id"],
    )
    op.create_index(
        "ix_delivery_note_lines_order_line",
        "delivery_note_lines",
        ["company_id", "order_line_id"],
    )


def downgrade() -> None:
    op.drop_table("delivery_note_lines")
    op.drop_table("delivery_notes")

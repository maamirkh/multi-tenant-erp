"""031_sales_invoices

Create Sales Invoice aggregate tables for Phase 6:
  - sales_invoices
  - invoice_lines
  - invoice_charges

Revision ID: 031_sales_invoices
Revises: 030_sales_delivery
Create Date: 2026-08-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "031_sales_invoices"
down_revision: str = "030_sales_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- sales_invoices -------------------------------------------------------
    op.create_table(
        "sales_invoices",
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
        # Invoice-specific fields
        sa.Column("invoice_number", sa.String(30), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("delivery_note_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("payment_term_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("billing_address_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("invoice_date", sa.String(10), nullable=False),
        sa.Column("due_date", sa.String(10), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("status", sa.String(25), server_default="DRAFT", nullable=False),
        sa.Column("subtotal", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column(
            "discount_amount", sa.Numeric(15, 2), server_default="0", nullable=False
        ),
        sa.Column("tax_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column(
            "charges_amount", sa.Numeric(15, 2), server_default="0", nullable=False
        ),
        sa.Column(
            "total_amount", sa.Numeric(15, 2), server_default="0", nullable=False
        ),
        sa.Column("credit_note_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("amount_in_words", sa.String(500), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("customer_notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "invoice_number",
            name="uq_sales_invoices_company_number",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ISSUED', 'PAID', 'CANCELLED', 'CREDIT_NOTE_ISSUED')",
            name="ck_sales_invoices_status",
        ),
    )
    op.create_index(
        "ix_sales_invoices_company_id",
        "sales_invoices",
        ["company_id"],
    )
    op.create_index(
        "ix_sales_invoices_company_status",
        "sales_invoices",
        ["company_id", "status"],
    )
    op.create_index(
        "ix_sales_invoices_company_customer_status",
        "sales_invoices",
        ["company_id", "customer_id", "status"],
    )
    op.create_index(
        "ix_sales_invoices_company_order",
        "sales_invoices",
        ["company_id", "order_id"],
    )

    # ---- invoice_lines --------------------------------------------------------
    op.create_table(
        "invoice_lines",
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
        # Line-specific fields
        sa.Column("invoice_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_of_measure", sa.String(20), nullable=False),
        sa.Column("unit_price", sa.Numeric(15, 4), nullable=False),
        sa.Column("discount_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column("discount_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("tax_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("tax_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("extended_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column(
            "delivery_note_line_id", postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column("order_line_id", postgresql.UUID(as_uuid=False), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("quantity > 0", name="ck_invoice_lines_quantity_positive"),
    )
    op.create_index(
        "ix_invoice_lines_company_id",
        "invoice_lines",
        ["company_id"],
    )
    op.create_index(
        "ix_invoice_lines_invoice",
        "invoice_lines",
        ["invoice_id"],
    )
    op.create_index(
        "ix_invoice_lines_order_line",
        "invoice_lines",
        ["order_line_id"],
    )

    # ---- invoice_charges ------------------------------------------------------
    op.create_table(
        "invoice_charges",
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
        # Charge-specific fields
        sa.Column("invoice_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("charge_type", sa.String(20), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column(
            "tax_applicable",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "charge_type IN ('FREIGHT', 'HANDLING', 'INSURANCE', 'OTHER')",
            name="ck_invoice_charges_type",
        ),
        sa.CheckConstraint("amount > 0", name="ck_invoice_charges_amount_positive"),
    )
    op.create_index(
        "ix_invoice_charges_company_id",
        "invoice_charges",
        ["company_id"],
    )
    op.create_index(
        "ix_invoice_charges_invoice",
        "invoice_charges",
        ["invoice_id"],
    )


def downgrade() -> None:
    op.drop_table("invoice_charges")
    op.drop_table("invoice_lines")
    op.drop_table("sales_invoices")

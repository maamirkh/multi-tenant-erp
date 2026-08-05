"""028_sales_quotations

Create Sales Quotation aggregate tables for Phase 3:
  - sales_quotations
  - quotation_lines
  - quotation_revisions

Revision ID: 028_sales_quotations
Revises: 027_sales_pricing
Create Date: 2026-08-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "028_sales_quotations"
down_revision: str = "027_sales_pricing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # sales_quotations
    # ------------------------------------------------------------------ #
    op.create_table(
        "sales_quotations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quotation_number", sa.String(30), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quotation_date", sa.String(10), nullable=False),
        sa.Column("validity_date", sa.String(10), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("payment_term_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("shipping_address_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("billing_address_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sales_rep_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(25), nullable=False, server_default="DRAFT"),
        sa.Column("subtotal", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("discount_type", sa.String(10), nullable=True),
        sa.Column("discount_value", sa.Numeric(15, 4), nullable=True),
        sa.Column(
            "discount_amount", sa.Numeric(15, 2), nullable=False, server_default="0"
        ),
        sa.Column("tax_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column(
            "total_amount", sa.Numeric(15, 2), nullable=False, server_default="0"
        ),
        sa.Column("internal_notes", sa.Text, nullable=True),
        sa.Column("customer_notes", sa.Text, nullable=True),
        sa.Column("converted_order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "quotation_number",
            name="uq_sales_quotations_company_number",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_sales_quotations_customer",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'SENT_TO_CUSTOMER', 'ACCEPTED', 'REJECTED', "
            "'CONVERTED', 'EXPIRED', 'CANCELLED')",
            name="ck_sales_quotations_status",
        ),
        sa.CheckConstraint("subtotal >= 0", name="ck_sales_quotations_subtotal"),
        sa.CheckConstraint("total_amount >= 0", name="ck_sales_quotations_total"),
        sa.CheckConstraint("revision_number >= 1", name="ck_sales_quotations_revision"),
        sa.CheckConstraint("version >= 1", name="ck_sales_quotations_version"),
        comment="Sales quotation aggregate root",
    )
    op.create_index(
        "ix_sales_quotations_company_id", "sales_quotations", ["company_id"]
    )
    op.create_index(
        "ix_sales_quotations_company_customer_status",
        "sales_quotations",
        ["company_id", "customer_id", "status"],
    )
    op.create_index(
        "ix_sales_quotations_company_status",
        "sales_quotations",
        ["company_id", "status"],
    )

    # ------------------------------------------------------------------ #
    # quotation_lines
    # ------------------------------------------------------------------ #
    op.create_table(
        "quotation_lines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quotation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer, nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column(
            "unit_of_measure", sa.String(20), nullable=False, server_default="EA"
        ),
        sa.Column("unit_price", sa.Numeric(15, 4), nullable=False),
        sa.Column("discount_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column("discount_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("tax_category", sa.String(20), nullable=True),
        sa.Column("extended_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["quotation_id"],
            ["sales_quotations.id"],
            name="fk_quotation_lines_quotation",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_quotation_lines_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_quotation_lines_unit_price"),
        sa.CheckConstraint("line_number >= 1", name="ck_quotation_lines_line_number"),
        comment="Sales quotation line items",
    )
    op.create_index("ix_quotation_lines_company_id", "quotation_lines", ["company_id"])
    op.create_index(
        "ix_quotation_lines_quotation",
        "quotation_lines",
        ["company_id", "quotation_id"],
    )

    # ------------------------------------------------------------------ #
    # quotation_revisions
    # ------------------------------------------------------------------ #
    op.create_table(
        "quotation_revisions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quotation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer, nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("modified_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("modified_at", sa.String(30), nullable=False),
        sa.Column("change_summary", sa.Text, nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["quotation_id"],
            ["sales_quotations.id"],
            name="fk_quotation_revisions_quotation",
        ),
        sa.CheckConstraint(
            "revision_number >= 1",
            name="ck_quotation_revisions_revision_number",
        ),
        comment="Immutable revision history snapshots for quotations",
    )
    op.create_index(
        "ix_quotation_revisions_company_id", "quotation_revisions", ["company_id"]
    )
    op.create_index(
        "ix_quotation_revisions_quotation",
        "quotation_revisions",
        ["company_id", "quotation_id"],
    )


def downgrade() -> None:
    op.drop_table("quotation_revisions")
    op.drop_table("quotation_lines")
    op.drop_table("sales_quotations")

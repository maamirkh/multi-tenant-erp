"""029_sales_orders

Create Sales Order aggregate tables for Phase 4:
  - sales_orders
  - order_lines
  - sales_approval_matrices
  - sales_matrix_rules
  - sales_approval_records

Revision ID: 029_sales_orders
Revises: 028_sales_quotations
Create Date: 2026-08-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "029_sales_orders"
down_revision: str = "028_sales_quotations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # sales_orders
    # ------------------------------------------------------------------ #
    op.create_table(
        "sales_orders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_number", sa.String(30), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quotation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("order_date", sa.String(10), nullable=False),
        sa.Column("required_delivery_date", sa.String(10), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("payment_term_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("shipping_address_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("billing_address_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sales_rep_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False, server_default="NORMAL"),
        sa.Column("status", sa.String(25), nullable=False, server_default="DRAFT"),
        sa.Column("subtotal", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("discount_type", sa.String(10), nullable=True),
        sa.Column("discount_value", sa.Numeric(15, 4), nullable=True),
        sa.Column(
            "discount_amount", sa.Numeric(15, 2), nullable=False, server_default="0"
        ),
        sa.Column("tax_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column(
            "charges_amount", sa.Numeric(15, 2), nullable=False, server_default="0"
        ),
        sa.Column(
            "total_amount", sa.Numeric(15, 2), nullable=False, server_default="0"
        ),
        sa.Column("internal_notes", sa.Text, nullable=True),
        sa.Column("customer_notes", sa.Text, nullable=True),
        sa.Column("cancellation_reason", sa.Text, nullable=True),
        sa.Column("approval_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "order_number",
            name="uq_sales_orders_company_number",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','REJECTED',"
            "'PARTIALLY_DELIVERED','DELIVERED','INVOICED','CLOSED','CANCELLED')",
            name="ck_sales_orders_status",
        ),
        sa.CheckConstraint(
            "priority IN ('LOW','NORMAL','HIGH','URGENT')",
            name="ck_sales_orders_priority",
        ),
        sa.CheckConstraint("subtotal >= 0", name="ck_sales_orders_subtotal"),
        sa.CheckConstraint("total_amount >= 0", name="ck_sales_orders_total"),
        sa.CheckConstraint(
            "approval_version >= 1", name="ck_sales_orders_approval_version"
        ),
        sa.CheckConstraint("version >= 1", name="ck_sales_orders_version"),
        comment="Sales order aggregate root",
    )
    op.create_index(
        "ix_sales_orders_company_customer_status",
        "sales_orders",
        ["company_id", "customer_id", "status"],
    )
    op.create_index(
        "ix_sales_orders_company_status",
        "sales_orders",
        ["company_id", "status"],
    )
    op.create_index(
        "ix_sales_orders_quotation",
        "sales_orders",
        ["company_id", "quotation_id"],
    )

    # ------------------------------------------------------------------ #
    # order_lines
    # ------------------------------------------------------------------ #
    op.create_table(
        "order_lines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer, nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity_ordered", sa.Numeric(12, 3), nullable=False),
        sa.Column(
            "quantity_delivered", sa.Numeric(12, 3), nullable=False, server_default="0"
        ),
        sa.Column(
            "unit_of_measure", sa.String(20), nullable=False, server_default="EA"
        ),
        sa.Column("unit_price", sa.Numeric(15, 4), nullable=False),
        sa.Column("cost_price", sa.Numeric(15, 4), nullable=True),
        sa.Column("discount_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column("discount_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("tax_category", sa.String(20), nullable=True),
        sa.Column("tax_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("tax_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("extended_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column(
            "delivery_status", sa.String(25), nullable=False, server_default="PENDING"
        ),
        sa.Column(
            "price_source", sa.String(20), nullable=False, server_default="MANUAL"
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "quantity_ordered > 0", name="ck_order_lines_quantity_ordered"
        ),
        sa.CheckConstraint(
            "quantity_delivered >= 0", name="ck_order_lines_quantity_delivered"
        ),
        sa.CheckConstraint("unit_price >= 0", name="ck_order_lines_unit_price"),
        sa.CheckConstraint("line_number >= 1", name="ck_order_lines_line_number"),
        sa.CheckConstraint(
            "delivery_status IN ('PENDING','PARTIALLY_DELIVERED','DELIVERED')",
            name="ck_order_lines_delivery_status",
        ),
        comment="Sales order line items",
    )
    op.create_index(
        "ix_order_lines_order",
        "order_lines",
        ["company_id", "order_id"],
    )

    # ------------------------------------------------------------------ #
    # sales_approval_matrices
    # ------------------------------------------------------------------ #
    op.create_table(
        "sales_approval_matrices",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("document_type", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "document_type IN ('SALES_ORDER','SALES_RETURN')",
            name="ck_sales_approval_matrices_doc_type",
        ),
        comment="Approval workflow matrix definitions for sales documents",
    )
    op.create_index(
        "ix_sales_approval_matrices_company",
        "sales_approval_matrices",
        ["company_id", "document_type"],
    )

    # ------------------------------------------------------------------ #
    # sales_matrix_rules
    # ------------------------------------------------------------------ #
    op.create_table(
        "sales_matrix_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("matrix_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approval_level", sa.Integer, nullable=False),
        sa.Column("min_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("max_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("approver_role", sa.String(50), nullable=True),
        sa.Column("approver_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("customer_category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("auto_approve", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("approval_level >= 1", name="ck_sales_matrix_rules_level"),
        sa.CheckConstraint("min_amount >= 0", name="ck_sales_matrix_rules_min_amount"),
        comment="Approval rules within an approval matrix",
    )
    op.create_index(
        "ix_sales_matrix_rules_matrix",
        "sales_matrix_rules",
        ["company_id", "matrix_id"],
    )

    # ------------------------------------------------------------------ #
    # sales_approval_records
    # ------------------------------------------------------------------ #
    op.create_table(
        "sales_approval_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(20), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approval_level", sa.Integer, nullable=False),
        sa.Column("approver_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(10), nullable=False, server_default="PENDING"),
        sa.Column("comments", sa.Text, nullable=True),
        sa.Column("decided_at", sa.String(30), nullable=True),
        sa.Column("approval_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "document_type IN ('SALES_ORDER','SALES_RETURN')",
            name="ck_sales_approval_records_doc_type",
        ),
        sa.CheckConstraint(
            "decision IN ('PENDING','APPROVED','REJECTED')",
            name="ck_sales_approval_records_decision",
        ),
        sa.CheckConstraint(
            "approval_level >= 1", name="ck_sales_approval_records_level"
        ),
        comment="Immutable approval decision records for sales documents",
    )
    op.create_index(
        "ix_sales_approval_records_document",
        "sales_approval_records",
        ["company_id", "document_type", "document_id"],
    )
    op.create_index(
        "ix_sales_approval_records_approver",
        "sales_approval_records",
        ["company_id", "approver_id", "decision"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sales_approval_records_approver", table_name="sales_approval_records"
    )
    op.drop_index(
        "ix_sales_approval_records_document", table_name="sales_approval_records"
    )
    op.drop_table("sales_approval_records")

    op.drop_index("ix_sales_matrix_rules_matrix", table_name="sales_matrix_rules")
    op.drop_table("sales_matrix_rules")

    op.drop_index(
        "ix_sales_approval_matrices_company", table_name="sales_approval_matrices"
    )
    op.drop_table("sales_approval_matrices")

    op.drop_index("ix_order_lines_order", table_name="order_lines")
    op.drop_table("order_lines")

    op.drop_index("ix_sales_orders_quotation", table_name="sales_orders")
    op.drop_index("ix_sales_orders_company_status", table_name="sales_orders")
    op.drop_index("ix_sales_orders_company_customer_status", table_name="sales_orders")
    op.drop_table("sales_orders")

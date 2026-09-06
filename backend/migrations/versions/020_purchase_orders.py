"""Purchase Orders — Phase 5.

Expands the minimal purchase_orders stub (created by migration 019) with all
remaining columns and creates the three new associated tables:
  po_lines               — PO line items
  po_additional_charges  — header-level charges (freight, handling, etc.)
  po_amendments          — immutable amendment audit records

Revision ID: 020
Revises: 019
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: str = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Expand purchase_orders with all Phase 5 columns
    # (stub already has: id, company_id, created_by, is_deleted,
    #  deleted_at, created_at, updated_at, po_number, status,
    #  purchase_request_id + company_id index + status constraint + unique constraint)
    # ------------------------------------------------------------------
    op.add_column(
        "purchase_orders",
        sa.Column(
            "supplier_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
    )
    op.add_column(
        "purchase_orders",
        sa.Column(
            "payment_terms_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
    )
    op.add_column(
        "purchase_orders",
        sa.Column(
            "delivery_address_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
    )
    op.add_column(
        "purchase_orders",
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "purchase_orders",
        sa.Column("supplier_reference", sa.String(100), nullable=True),
    )
    op.add_column(
        "purchase_orders",
        sa.Column(
            "currency_code",
            sa.String(3),
            server_default="USD",
            nullable=False,
        ),
    )
    op.add_column(
        "purchase_orders",
        sa.Column("exchange_rate", sa.Numeric(15, 6), nullable=True),
    )
    op.add_column(
        "purchase_orders",
        sa.Column(
            "subtotal",
            sa.Numeric(15, 2),
            server_default="0.00",
            nullable=False,
        ),
    )
    op.add_column(
        "purchase_orders",
        sa.Column(
            "total_charges",
            sa.Numeric(15, 2),
            server_default="0.00",
            nullable=False,
        ),
    )
    op.add_column(
        "purchase_orders",
        sa.Column(
            "total_discounts",
            sa.Numeric(15, 2),
            server_default="0.00",
            nullable=False,
        ),
    )
    op.add_column(
        "purchase_orders",
        sa.Column(
            "tax_amount",
            sa.Numeric(15, 2),
            server_default="0.00",
            nullable=False,
        ),
    )
    op.add_column(
        "purchase_orders",
        sa.Column(
            "total",
            sa.Numeric(15, 2),
            server_default="0.00",
            nullable=False,
        ),
    )
    op.add_column(
        "purchase_orders",
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "purchase_orders",
        sa.Column(
            "branch_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
    )
    op.add_column(
        "purchase_orders",
        sa.Column(
            "version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )
    op.add_column(
        "purchase_orders",
        sa.Column(
            "reason_code_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
    )

    # New indexes on purchase_orders
    op.create_index(
        "ix_purchase_orders_supplier_id", "purchase_orders", ["supplier_id"]
    )
    op.create_index("ix_purchase_orders_status", "purchase_orders", ["status"])

    # ------------------------------------------------------------------
    # po_lines
    # ------------------------------------------------------------------
    op.create_table(
        "po_lines",
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
        sa.Column("po_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "pr_line_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column(
            "product_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column("product_description", sa.String(500), nullable=False),
        sa.Column("quantity_ordered", sa.Numeric(15, 3), nullable=False),
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
            "open_quantity",
            sa.Numeric(15, 3),
            server_default="0.000",
            nullable=False,
        ),
        sa.Column("uom_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column(
            "unit_cost",
            sa.Numeric(15, 4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column("line_discount_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("line_discount_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column(
            "line_total",
            sa.Numeric(15, 2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column("tax_code", sa.String(50), nullable=True),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("tax_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column(
            "tax_inclusive",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "quantity_ordered > 0", name="ck_po_lines_quantity_ordered_positive"
        ),
        sa.CheckConstraint("unit_cost >= 0", name="ck_po_lines_unit_cost_non_negative"),
        sa.UniqueConstraint("po_id", "line_number", name="uq_po_lines_po_line"),
        sa.PrimaryKeyConstraint("id"),
        comment="Purchase order line items",
    )
    op.create_index("ix_po_lines_po_id", "po_lines", ["po_id"])
    op.create_index("ix_po_lines_company_id", "po_lines", ["company_id"])

    # ------------------------------------------------------------------
    # po_additional_charges
    # ------------------------------------------------------------------
    op.create_table(
        "po_additional_charges",
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
        sa.Column("po_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("charge_type", sa.String(20), nullable=False),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column(
            "amount",
            sa.Numeric(15, 2),
            server_default="0.00",
            nullable=False,
        ),
        sa.CheckConstraint(
            "charge_type IN ('FREIGHT','HANDLING','INSURANCE','OTHER')",
            name="ck_po_charges_charge_type",
        ),
        sa.CheckConstraint("amount >= 0", name="ck_po_charges_amount_non_negative"),
        sa.PrimaryKeyConstraint("id"),
        comment="Additional header charges on purchase orders",
    )
    op.create_index(
        "ix_po_additional_charges_po_id", "po_additional_charges", ["po_id"]
    )
    op.create_index(
        "ix_po_additional_charges_company_id", "po_additional_charges", ["company_id"]
    )

    # ------------------------------------------------------------------
    # po_amendments
    # ------------------------------------------------------------------
    op.create_table(
        "po_amendments",
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
        sa.Column("po_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("amendment_number", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("change_summary", sa.JSON(), nullable=True),
        sa.Column(
            "requested_by", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column(
            "approved_by", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            server_default="PENDING",
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED')",
            name="ck_po_amendments_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Amendment audit records for approved purchase orders",
    )
    op.create_index("ix_po_amendments_po_id", "po_amendments", ["po_id"])
    op.create_index("ix_po_amendments_company_id", "po_amendments", ["company_id"])


def downgrade() -> None:
    op.drop_table("po_amendments")
    op.drop_table("po_additional_charges")
    op.drop_table("po_lines")
    # Remove added indexes on purchase_orders
    op.drop_index("ix_purchase_orders_status", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_supplier_id", table_name="purchase_orders")
    # Remove added columns from purchase_orders (reverse order)
    op.drop_column("purchase_orders", "reason_code_id")
    op.drop_column("purchase_orders", "version")
    op.drop_column("purchase_orders", "branch_id")
    op.drop_column("purchase_orders", "notes")
    op.drop_column("purchase_orders", "total")
    op.drop_column("purchase_orders", "tax_amount")
    op.drop_column("purchase_orders", "total_discounts")
    op.drop_column("purchase_orders", "total_charges")
    op.drop_column("purchase_orders", "subtotal")
    op.drop_column("purchase_orders", "exchange_rate")
    op.drop_column("purchase_orders", "currency_code")
    op.drop_column("purchase_orders", "supplier_reference")
    op.drop_column("purchase_orders", "expected_delivery_date")
    op.drop_column("purchase_orders", "delivery_address_id")
    op.drop_column("purchase_orders", "payment_terms_id")
    op.drop_column("purchase_orders", "supplier_id")

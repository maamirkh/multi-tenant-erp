"""Purchase Costing — Phase 8.

Creates:
  purchase_cost_entries — immutable GR cost snapshots

Alters:
  gr_lines — adds tax_code, tax_rate, tax_amount columns (tax readiness)

Revision ID: 023
Revises: 022
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "023"
down_revision: str = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # purchase_cost_entries — immutable GR cost snapshot (T189)
    # ------------------------------------------------------------------
    op.create_table(
        "purchase_cost_entries",
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
        # Cost entry fields
        sa.Column("gr_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("po_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "supplier_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False
        ),
        sa.Column("cost_date", sa.Date(), nullable=False),
        sa.Column("subtotal", sa.Numeric(15, 2), server_default="0.00", nullable=False),
        sa.Column(
            "total_charges", sa.Numeric(15, 2), server_default="0.00", nullable=False
        ),
        sa.Column(
            "total_discounts", sa.Numeric(15, 2), server_default="0.00", nullable=False
        ),
        sa.Column(
            "tax_amount", sa.Numeric(15, 2), server_default="0.00", nullable=False
        ),
        sa.Column("total", sa.Numeric(15, 2), server_default="0.00", nullable=False),
        sa.Column(
            "credit_note_pending",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "invoice_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column("currency_code", sa.String(3), server_default="USD", nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "gr_id", name="uq_purchase_cost_entries_company_gr"
        ),
        sa.CheckConstraint(
            "subtotal >= 0", name="ck_purchase_cost_entries_subtotal_non_negative"
        ),
        sa.CheckConstraint(
            "total_charges >= 0", name="ck_purchase_cost_entries_charges_non_negative"
        ),
        sa.CheckConstraint(
            "total_discounts >= 0",
            name="ck_purchase_cost_entries_discounts_non_negative",
        ),
        sa.CheckConstraint(
            "tax_amount >= 0", name="ck_purchase_cost_entries_tax_non_negative"
        ),
        comment="Immutable cost snapshots created on GR confirmation",
    )

    op.create_index(
        "ix_purchase_cost_entries_company_id",
        "purchase_cost_entries",
        ["company_id"],
    )
    op.create_index(
        "ix_purchase_cost_entries_po_id",
        "purchase_cost_entries",
        ["po_id"],
    )
    op.create_index(
        "ix_purchase_cost_entries_supplier_id",
        "purchase_cost_entries",
        ["supplier_id"],
    )

    # ------------------------------------------------------------------
    # gr_lines — add tax readiness columns (T196)
    # ------------------------------------------------------------------
    op.add_column(
        "gr_lines",
        sa.Column("tax_code", sa.String(50), nullable=True),
    )
    op.add_column(
        "gr_lines",
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "gr_lines",
        sa.Column("tax_amount", sa.Numeric(15, 2), nullable=True),
    )


def downgrade() -> None:
    # Remove tax columns from gr_lines
    op.drop_column("gr_lines", "tax_amount")
    op.drop_column("gr_lines", "tax_rate")
    op.drop_column("gr_lines", "tax_code")

    # Drop purchase_cost_entries
    op.drop_index(
        "ix_purchase_cost_entries_supplier_id", table_name="purchase_cost_entries"
    )
    op.drop_index("ix_purchase_cost_entries_po_id", table_name="purchase_cost_entries")
    op.drop_index(
        "ix_purchase_cost_entries_company_id", table_name="purchase_cost_entries"
    )
    op.drop_table("purchase_cost_entries")

"""033_sales_index_audit

Phase 10 T234 — Database index audit: adds missing indexes identified in
spec data-model.md §Index Strategy that were not included in earlier
phase migrations.

Missing indexes added:
  - customers (company_id, category_id)  — category filtering
  - customers (company_id, group_id)     — group filtering (FTS supplement)
  - customers (company_id, credit_status) — credit pipeline views
  - sales_quotations (company_id, sales_rep_id) — rep-specific quotation lists
  - sales_orders (company_id, sales_rep_id)     — rep-specific order lists

Revision ID: 033_sales_index_audit
Revises: 032_sales_returns
Create Date: 2026-08-04
"""

from __future__ import annotations

from alembic import op

revision = "033_sales_index_audit"
down_revision = "032_sales_returns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # customers table — missing category/group/credit_status indexes
    # ------------------------------------------------------------------
    op.create_index(
        "ix_customers_company_category",
        "customers",
        ["company_id", "category_id"],
        unique=False,
    )
    op.create_index(
        "ix_customers_company_group",
        "customers",
        ["company_id", "group_id"],
        unique=False,
    )
    op.create_index(
        "ix_customers_company_credit_status",
        "customers",
        ["company_id", "credit_status"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # sales_quotations — sales rep lookup
    # ------------------------------------------------------------------
    op.create_index(
        "ix_sales_quotations_company_rep",
        "sales_quotations",
        ["company_id", "sales_rep_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # sales_orders — sales rep lookup
    # ------------------------------------------------------------------
    op.create_index(
        "ix_sales_orders_company_rep",
        "sales_orders",
        ["company_id", "sales_rep_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # sales_returns — customer lookup (supplement to existing company_id)
    # ------------------------------------------------------------------
    op.create_index(
        "ix_sales_returns_company_customer",
        "sales_returns",
        ["company_id", "customer_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sales_returns_company_customer", table_name="sales_returns")
    op.drop_index("ix_sales_orders_company_rep", table_name="sales_orders")
    op.drop_index("ix_sales_quotations_company_rep", table_name="sales_quotations")
    op.drop_index("ix_customers_company_credit_status", table_name="customers")
    op.drop_index("ix_customers_company_group", table_name="customers")
    op.drop_index("ix_customers_company_category", table_name="customers")

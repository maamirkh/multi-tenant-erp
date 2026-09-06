"""Purchase Performance Indexes — Phase 11.

Adds composite and covering indexes missing from earlier migrations.
Targets identified by query-pattern audit:

  purchase_requests  — (company_id, created_at) for date-range list queries
  purchase_orders    — (company_id, created_at), (company_id, expected_delivery_date)
                       for date filtering and overdue PO queries
  goods_receipts     — (company_id, received_date) for GR date reports
  vendor_returns     — (company_id, created_at)
  purchase_cost_entries — (company_id, gr_id)
  approval_records   — (company_id, document_id, document_type) composite for
                       approval lookup queries

Revision ID: 024
Revises: 023
"""

from __future__ import annotations

from alembic import op

revision: str = "024"
down_revision: str = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # purchase_requests — date-range list queries
    # ------------------------------------------------------------------
    op.create_index(
        "ix_purchase_requests_company_created",
        "purchase_requests",
        ["company_id", "created_at"],
    )
    op.create_index(
        "ix_purchase_requests_company_status_created",
        "purchase_requests",
        ["company_id", "status", "created_at"],
    )

    # ------------------------------------------------------------------
    # purchase_orders — date filtering + overdue queries
    # ------------------------------------------------------------------
    op.create_index(
        "ix_purchase_orders_company_created",
        "purchase_orders",
        ["company_id", "created_at"],
    )
    op.create_index(
        "ix_purchase_orders_expected_delivery",
        "purchase_orders",
        ["company_id", "expected_delivery_date"],
    )
    op.create_index(
        "ix_purchase_orders_company_status_supplier",
        "purchase_orders",
        ["company_id", "status", "supplier_id"],
    )

    # ------------------------------------------------------------------
    # goods_receipts — date-based report queries
    # ------------------------------------------------------------------
    op.create_index(
        "ix_goods_receipts_company_received",
        "goods_receipts",
        ["company_id", "received_at"],
    )
    op.create_index(
        "ix_goods_receipts_company_status",
        "goods_receipts",
        ["company_id", "status"],
    )

    # ------------------------------------------------------------------
    # vendor_returns — date-range list queries
    # ------------------------------------------------------------------
    op.create_index(
        "ix_vendor_returns_company_created",
        "vendor_returns",
        ["company_id", "created_at"],
    )

    # ------------------------------------------------------------------
    # purchase_cost_entries — lookup by GR within company
    # (ix_purchase_cost_entries_company_id already created in 023)
    # ------------------------------------------------------------------
    op.create_index(
        "ix_purchase_cost_entries_gr_id",
        "purchase_cost_entries",
        ["gr_id"],
    )

    # ------------------------------------------------------------------
    # approval_records — compound lookup: company + document FK
    # ------------------------------------------------------------------
    op.create_index(
        "ix_approval_records_company_doc",
        "approval_records",
        ["company_id", "document_id", "document_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_approval_records_company_doc", table_name="approval_records")

    op.drop_index("ix_purchase_cost_entries_gr_id", table_name="purchase_cost_entries")

    op.drop_index("ix_vendor_returns_company_created", table_name="vendor_returns")

    op.drop_index("ix_goods_receipts_company_status", table_name="goods_receipts")
    op.drop_index("ix_goods_receipts_company_received", table_name="goods_receipts")

    op.drop_index(
        "ix_purchase_orders_company_status_supplier", table_name="purchase_orders"
    )
    op.drop_index("ix_purchase_orders_expected_delivery", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_company_created", table_name="purchase_orders")

    op.drop_index(
        "ix_purchase_requests_company_status_created", table_name="purchase_requests"
    )
    op.drop_index(
        "ix_purchase_requests_company_created", table_name="purchase_requests"
    )

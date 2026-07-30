"""inventory performance optimisation — Phase 11

Adds composite indexes identified during the Phase 11 performance audit.
All indexes target the most common filter combinations used by list endpoints,
ledger queries, and alert dashboards.

Index ordering follows PostgreSQL best practice: equality columns first,
range/sort columns last (leftmost-prefix rule).

Revision ID: 014
Revises: 013
Create Date: 2026-07-25
"""

from __future__ import annotations

from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use raw SQL with IF NOT EXISTS to be idempotent (safe after partial runs).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_inv_categories_parent_id "
        "ON inventory_categories (company_id, parent_id) "
        "WHERE is_deleted = false"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_inv_stock_mov_company_product_at "
        "ON inventory_stock_movements (company_id, product_id, performed_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_inv_stock_mov_company_type "
        "ON inventory_stock_movements (company_id, movement_type)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_inv_adjustments_company_status "
        "ON inventory_adjustments (company_id, status) "
        "WHERE is_deleted = false"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_inv_adjustments_company_product "
        "ON inventory_adjustments (company_id, product_id) "
        "WHERE is_deleted = false"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_inv_product_tags_company_product "
        "ON inventory_product_tags (company_id, product_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_inv_stock_pos_company_product_wh "
        "ON inventory_stock_positions (company_id, product_id, warehouse_id) "
        "WHERE is_deleted = false"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_inv_transfers_company_status_created "
        "ON inventory_stock_transfers (company_id, status, created_at) "
        "WHERE is_deleted = false"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_inv_transfers_company_status_created")
    op.execute("DROP INDEX IF EXISTS ix_inv_stock_pos_company_product_wh")
    op.execute("DROP INDEX IF EXISTS ix_inv_product_tags_company_product")
    op.execute("DROP INDEX IF EXISTS ix_inv_adjustments_company_product")
    op.execute("DROP INDEX IF EXISTS ix_inv_adjustments_company_status")
    op.execute("DROP INDEX IF EXISTS ix_inv_stock_mov_company_type")
    op.execute("DROP INDEX IF EXISTS ix_inv_stock_mov_company_product_at")
    op.execute("DROP INDEX IF EXISTS ix_inv_categories_parent_id")

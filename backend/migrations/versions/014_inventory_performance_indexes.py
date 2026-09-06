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

import sqlalchemy as sa
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── inventory_categories ─────────────────────────────────────────────────
    # Accelerates CategoryRepository.get_children() — filters by parent_id +
    # is_deleted, orders by sort_order + name.
    op.create_index(
        "ix_inv_categories_parent_id",
        "inventory_categories",
        ["company_id", "parent_id"],
        postgresql_where=sa.text("is_deleted = false"),
        comment=(
            "Accelerates CategoryRepository.get_children() tree traversal. "
            "Partial index excludes soft-deleted rows."
        ),
    )

    # ── inventory_stock_movements — composite for ledger queries ─────────────
    # Accelerates the most common ledger view:
    #   WHERE company_id = ? AND product_id = ? ORDER BY performed_at DESC
    op.create_index(
        "ix_inv_stock_mov_company_product_at",
        "inventory_stock_movements",
        ["company_id", "product_id", "performed_at"],
        comment=(
            "Composite index for stock ledger queries filtered by company + product, "
            "ordered by performed_at DESC. Covers the common pattern: "
            "list movements for product in date range."
        ),
    )

    # Accelerates movement-type filter used in reporting:
    #   WHERE company_id = ? AND movement_type = ?
    op.create_index(
        "ix_inv_stock_mov_company_type",
        "inventory_stock_movements",
        ["company_id", "movement_type"],
        comment=(
            "Covers movement_type filter on ledger and report queries. "
            "Used by adjustment reports, transfer reports, and return reports."
        ),
    )

    # ── inventory_adjustments — pending approval queue ────────────────────────
    # Accelerates the approval queue: WHERE company_id = ? AND status = ?
    op.create_index(
        "ix_inv_adjustments_company_status",
        "inventory_adjustments",
        ["company_id", "status"],
        postgresql_where=sa.text("is_deleted = false"),
        comment=(
            "Partial index for AdjustmentRepository.list_for_company(status=...). "
            "Primarily used by the pending-approval queue (status=PENDING_APPROVAL)."
        ),
    )

    # Accelerates adjustment list filtered by product:
    #   WHERE company_id = ? AND product_id = ?
    op.create_index(
        "ix_inv_adjustments_company_product",
        "inventory_adjustments",
        ["company_id", "product_id"],
        postgresql_where=sa.text("is_deleted = false"),
        comment=(
            "Covers AdjustmentRepository.list_for_company(product_id=...) filter. "
            "Used by product detail views showing adjustment history."
        ),
    )

    # ── inventory_product_tags — tag-based product lookups ────────────────────
    # Accelerates ProductTagRepository.list_for_product():
    #   WHERE company_id = ? AND product_id = ?
    op.create_index(
        "ix_inv_product_tags_company_product",
        "inventory_product_tags",
        ["company_id", "product_id"],
        comment=(
            "Covers ProductTagRepository.list_for_product(). "
            "Used by product detail and tag-based product filtering."
        ),
    )

    # ── inventory_stock_positions — alert evaluation composite ────────────────
    # Accelerates AlertEvaluationService: after every stock write, evaluates
    # all positions for a (company, product, warehouse) triple.
    op.create_index(
        "ix_inv_stock_pos_company_product_wh",
        "inventory_stock_positions",
        ["company_id", "product_id", "warehouse_id"],
        postgresql_where=sa.text("is_deleted = false"),
        comment=(
            "Composite for alert evaluation and concurrent-write scenarios. "
            "Supplements the existing unique constraint with a partial index "
            "excluding deleted positions, improving qty_on_hand lookups."
        ),
    )

    # ── inventory_transfers — status + created_at filter ─────────────────────
    # Accelerates TransferRepository.list_for_company(status=...).
    op.create_index(
        "ix_inv_transfers_company_status_created",
        "inventory_stock_transfers",
        ["company_id", "status", "created_at"],
        postgresql_where=sa.text("is_deleted = false"),
        comment=(
            "Covers TransferRepository.list_for_company(status=...) ordered by "
            "created_at DESC. Primary access pattern for the transfer list view."
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inv_transfers_company_status_created",
        table_name="inventory_stock_transfers",
    )
    op.drop_index(
        "ix_inv_stock_pos_company_product_wh", table_name="inventory_stock_positions"
    )
    op.drop_index(
        "ix_inv_product_tags_company_product", table_name="inventory_product_tags"
    )
    op.drop_index(
        "ix_inv_adjustments_company_product", table_name="inventory_adjustments"
    )
    op.drop_index(
        "ix_inv_adjustments_company_status", table_name="inventory_adjustments"
    )
    op.drop_index(
        "ix_inv_stock_mov_company_type", table_name="inventory_stock_movements"
    )
    op.drop_index(
        "ix_inv_stock_mov_company_product_at", table_name="inventory_stock_movements"
    )
    op.drop_index("ix_inv_categories_parent_id", table_name="inventory_categories")

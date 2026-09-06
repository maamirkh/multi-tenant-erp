"""inventory warehouses — Phase 4

Creates:
  - inventory_warehouses
  - inventory_warehouse_locations

Revision ID: 009
Revises: 008
Create Date: 2026-07-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # inventory_warehouses
    # ------------------------------------------------------------------
    op.create_table(
        "inventory_warehouses",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "updated_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # Warehouse fields
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "warehouse_type", sa.String(20), nullable=False, server_default="MAIN"
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "branch_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True
        ),
        # Address value object
        sa.Column("address_line1", sa.String(300), nullable=True),
        sa.Column("address_line2", sa.String(300), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state_province", sa.String(100), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("country_code", sa.String(3), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # Constraints
        sa.UniqueConstraint(
            "company_id", "code", name="uq_inv_warehouses_company_code"
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'ARCHIVED')",
            name="ck_inv_warehouses_status",
        ),
        sa.CheckConstraint(
            "warehouse_type IN ('MAIN', 'BRANCH', 'TRANSIT', 'VIRTUAL', 'CONSIGNMENT')",
            name="ck_inv_warehouses_type",
        ),
        comment="Warehouse aggregate root, scoped per company",
    )
    op.create_index(
        "ix_inv_warehouses_company_id", "inventory_warehouses", ["company_id"]
    )
    op.create_index(
        "ix_inv_warehouses_company_status",
        "inventory_warehouses",
        ["company_id", "status"],
    )

    # ------------------------------------------------------------------
    # inventory_warehouse_locations
    # ------------------------------------------------------------------
    op.create_table(
        "inventory_warehouse_locations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "updated_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # Location fields
        sa.Column(
            "warehouse_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("inventory_warehouses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("location_code", sa.String(50), nullable=False),
        sa.Column("aisle", sa.String(20), nullable=True),
        sa.Column("zone", sa.String(50), nullable=True),
        sa.Column("shelf", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        # Constraints
        sa.UniqueConstraint(
            "company_id",
            "warehouse_id",
            "location_code",
            name="uq_inv_wh_locations_wh_code",
        ),
        comment="Physical/logical locations within a warehouse",
    )
    op.create_index(
        "ix_inv_wh_locations_warehouse_id",
        "inventory_warehouse_locations",
        ["warehouse_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inv_wh_locations_warehouse_id", table_name="inventory_warehouse_locations"
    )
    op.drop_table("inventory_warehouse_locations")
    op.drop_index("ix_inv_warehouses_company_status", table_name="inventory_warehouses")
    op.drop_index("ix_inv_warehouses_company_id", table_name="inventory_warehouses")
    op.drop_table("inventory_warehouses")

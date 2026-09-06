"""Purchase Supplier Core — Phase 1

Creates the Supplier aggregate tables:
  - suppliers           — core supplier master with FTS trigger
  - supplier_contacts   — contact persons
  - supplier_addresses  — postal/billing/shipping addresses

Indexes:
  - Unique (company_id, supplier_code)
  - Status composite index
  - GIN index on tsvector_search column
  - supplier_contacts.supplier_id
  - supplier_addresses.supplier_id

FTS trigger: a PostgreSQL function + trigger maintains the tsvector_search
column on INSERT/UPDATE, covering legal_name, trading_name, supplier_code,
vendor_code.

Revision ID: 016
Revises: 015
Create Date: 2026-07-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # suppliers
    # ------------------------------------------------------------------
    op.create_table(
        "suppliers",
        sa.Column(
            "id",
            PG_UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("supplier_code", sa.String(30), nullable=False),
        sa.Column("vendor_code", sa.String(30), nullable=True),
        sa.Column("legal_name", sa.String(300), nullable=False),
        sa.Column("trading_name", sa.String(300), nullable=True),
        sa.Column(
            "supplier_type", sa.String(20), nullable=False, server_default="GOODS"
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("category_id", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("payment_terms_id", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("tax_registration_number", sa.String(50), nullable=True),
        sa.Column("tax_category", sa.String(50), nullable=True),
        sa.Column("tax_region", sa.String(100), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_preferred", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("rating_score", sa.Numeric(3, 1), nullable=True),
        sa.Column("lead_time_days", sa.Integer, nullable=True),
        sa.Column("branch_id", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("tsvector_search", TSVECTOR, nullable=True),
        # Audit / soft-delete columns (TenantBaseModel)
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("created_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "company_id", "supplier_code", name="uq_suppliers_company_code"
        ),
        sa.CheckConstraint(
            "supplier_type IN ('GOODS', 'SERVICES', 'BOTH')",
            name="ck_suppliers_supplier_type",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'INACTIVE', 'BLOCKED', 'ARCHIVED')",
            name="ck_suppliers_status",
        ),
        sa.CheckConstraint(
            "rating_score IS NULL OR (rating_score >= 0 AND rating_score <= 10)",
            name="ck_suppliers_rating_score",
        ),
        schema=None,
        comment="Supplier aggregate root — core supplier master record",
    )

    op.create_index("ix_suppliers_company_id", "suppliers", ["company_id"])
    op.create_index(
        "ix_suppliers_company_status", "suppliers", ["company_id", "status"]
    )
    op.create_index(
        "ix_suppliers_company_preferred", "suppliers", ["company_id", "is_preferred"]
    )

    # GIN index for FTS
    op.execute(
        "CREATE INDEX ix_suppliers_tsvector ON suppliers USING GIN (tsvector_search)"
    )

    # ------------------------------------------------------------------
    # FTS trigger — maintains tsvector_search on INSERT/UPDATE
    # ------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION suppliers_tsvector_update() RETURNS trigger AS $$
        BEGIN
            NEW.tsvector_search :=
                setweight(to_tsvector('simple', coalesce(NEW.legal_name, '')), 'A') ||
                setweight(to_tsvector('simple', coalesce(NEW.trading_name, '')), 'B') ||
                setweight(to_tsvector('simple', coalesce(NEW.supplier_code, '')), 'A') ||
                setweight(to_tsvector('simple', coalesce(NEW.vendor_code, '')), 'C');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER suppliers_tsvector_trigger
        BEFORE INSERT OR UPDATE ON suppliers
        FOR EACH ROW EXECUTE FUNCTION suppliers_tsvector_update();
    """)

    # ------------------------------------------------------------------
    # supplier_contacts
    # ------------------------------------------------------------------
    op.create_table(
        "supplier_contacts",
        sa.Column(
            "id",
            PG_UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("supplier_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(100), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("mobile", sa.String(50), nullable=True),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("created_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["suppliers.id"], name="fk_supplier_contacts_supplier_id"
        ),
        comment="Supplier contact persons (communication details)",
    )
    op.create_index(
        "ix_supplier_contacts_company_id", "supplier_contacts", ["company_id"]
    )
    op.create_index("ix_sup_contacts_supplier_id", "supplier_contacts", ["supplier_id"])

    # ------------------------------------------------------------------
    # supplier_addresses
    # ------------------------------------------------------------------
    op.create_table(
        "supplier_addresses",
        sa.Column(
            "id",
            PG_UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("supplier_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column(
            "address_type", sa.String(20), nullable=False, server_default="BILLING"
        ),
        sa.Column("address_line_1", sa.String(300), nullable=False),
        sa.Column("address_line_2", sa.String(300), nullable=True),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("created_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["suppliers.id"], name="fk_supplier_addresses_supplier_id"
        ),
        sa.CheckConstraint(
            "address_type IN ('BILLING', 'SHIPPING', 'REGISTERED', 'OTHER')",
            name="ck_sup_addresses_type",
        ),
        comment="Supplier postal / billing / shipping addresses",
    )
    op.create_index(
        "ix_supplier_addresses_company_id", "supplier_addresses", ["company_id"]
    )
    op.create_index(
        "ix_sup_addresses_supplier_id", "supplier_addresses", ["supplier_id"]
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS suppliers_tsvector_trigger ON suppliers")
    op.execute("DROP FUNCTION IF EXISTS suppliers_tsvector_update()")

    op.drop_index("ix_sup_addresses_supplier_id", table_name="supplier_addresses")
    op.drop_index("ix_supplier_addresses_company_id", table_name="supplier_addresses")
    op.drop_table("supplier_addresses")

    op.drop_index("ix_sup_contacts_supplier_id", table_name="supplier_contacts")
    op.drop_index("ix_supplier_contacts_company_id", table_name="supplier_contacts")
    op.drop_table("supplier_contacts")

    op.execute("DROP INDEX IF EXISTS ix_suppliers_tsvector")
    op.drop_index("ix_suppliers_company_preferred", table_name="suppliers")
    op.drop_index("ix_suppliers_company_status", table_name="suppliers")
    op.drop_index("ix_suppliers_company_id", table_name="suppliers")
    op.drop_table("suppliers")

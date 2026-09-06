"""026_sales_customers

Create the Customer aggregate tables for Sales Phase 1:
  - customers
  - customer_contacts
  - customer_addresses
  - customer_bank_details
  - customer_notes

Revision ID: 026_sales_customers
Revises: 025_sales_foundation
Create Date: 2026-07-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "026_sales_customers"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # customers
    # ------------------------------------------------------------------
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # identity
        sa.Column("customer_code", sa.String(30), nullable=False),
        # classification
        sa.Column(
            "customer_type",
            sa.String(20),
            nullable=False,
            server_default="COMPANY",
        ),
        sa.Column("category_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=False), nullable=True),
        # names
        sa.Column("legal_name", sa.String(200), nullable=False),
        sa.Column("trading_name", sa.String(200), nullable=True),
        # status
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        # payment & credit
        sa.Column("payment_term_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column(
            "credit_limit",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "credit_status",
            sa.String(20),
            nullable=False,
            server_default="GOOD",
        ),
        # rating
        sa.Column("rating", sa.String(1), nullable=True),
        # currency & tax
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("tax_registration_number", sa.String(50), nullable=True),
        sa.Column(
            "tax_exempt",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("tax_exempt_certificate", sa.String(100), nullable=True),
        sa.Column("tax_exempt_expiry", sa.String(10), nullable=True),
        # business profile
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("annual_revenue_range", sa.String(50), nullable=True),
        # custom fields
        sa.Column("custom_fields", postgresql.JSONB(), nullable=True),
        # notes
        sa.Column("notes", sa.Text(), nullable=True),
        # optimistic lock
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        # full-text search
        sa.Column("tsvector_search", postgresql.TSVECTOR(), nullable=True),
        # constraints
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "customer_code", name="uq_customers_company_code"
        ),
        sa.CheckConstraint(
            "customer_type IN ('INDIVIDUAL', 'COMPANY', 'GOVERNMENT', 'INTERNAL')",
            name="ck_customers_customer_type",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'ON_HOLD', 'BLOCKED', 'INACTIVE')",
            name="ck_customers_status",
        ),
        sa.CheckConstraint(
            "credit_status IN ('GOOD', 'WARNING', 'EXCEEDED', 'HOLD')",
            name="ck_customers_credit_status",
        ),
        sa.CheckConstraint(
            "rating IS NULL OR rating IN ('A', 'B', 'C', 'D', 'F')",
            name="ck_customers_rating",
        ),
        sa.CheckConstraint(
            "credit_limit >= 0",
            name="ck_customers_credit_limit",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_customers_version",
        ),
        comment="Customer aggregate root — core customer master record",
    )
    op.create_index(
        "ix_customers_company_id", "customers", ["company_id"], unique=False
    )
    op.create_index(
        "ix_customers_company_status",
        "customers",
        ["company_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_customers_company_type",
        "customers",
        ["company_id", "customer_type"],
        unique=False,
    )
    op.create_index(
        "ix_customers_tsvector",
        "customers",
        ["tsvector_search"],
        unique=False,
        postgresql_using="gin",
    )

    # ------------------------------------------------------------------
    # customer_contacts
    # ------------------------------------------------------------------
    op.create_table(
        "customer_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("customer_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("contact_name", sa.String(200), nullable=False),
        sa.Column("title", sa.String(100), nullable=True),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("mobile", sa.String(30), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_billing_contact",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_shipping_contact",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="Customer contact persons",
    )
    op.create_index(
        "ix_customer_contacts_company_id",
        "customer_contacts",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_customer_contacts_customer_id",
        "customer_contacts",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        "ix_customer_contacts_company_customer",
        "customer_contacts",
        ["company_id", "customer_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # customer_addresses
    # ------------------------------------------------------------------
    op.create_table(
        "customer_addresses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("customer_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "address_type",
            sa.String(10),
            nullable=False,
            server_default="BILLING",
        ),
        sa.Column("address_label", sa.String(100), nullable=True),
        sa.Column("address_line_1", sa.String(300), nullable=False),
        sa.Column("address_line_2", sa.String(300), nullable=True),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state_province", sa.String(100), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column(
            "is_default_billing",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_default_shipping",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "address_type IN ('BILLING', 'SHIPPING', 'BOTH')",
            name="ck_customer_addresses_type",
        ),
        comment="Customer billing and shipping addresses",
    )
    op.create_index(
        "ix_customer_addresses_company_id",
        "customer_addresses",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_customer_addresses_customer_id",
        "customer_addresses",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        "ix_customer_addresses_company_customer",
        "customer_addresses",
        ["company_id", "customer_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # customer_bank_details
    # ------------------------------------------------------------------
    op.create_table(
        "customer_bank_details",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("customer_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("bank_name", sa.String(200), nullable=False),
        sa.Column("branch_name", sa.String(200), nullable=True),
        sa.Column("account_number", sa.String(50), nullable=False),
        sa.Column("iban", sa.String(34), nullable=True),
        sa.Column("swift_bic", sa.String(11), nullable=True),
        sa.Column("account_holder_name", sa.String(200), nullable=False),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Customer bank account details",
    )
    op.create_index(
        "ix_customer_bank_details_company_id",
        "customer_bank_details",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_customer_bank_details_customer_id",
        "customer_bank_details",
        ["customer_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # customer_notes
    # ------------------------------------------------------------------
    op.create_table(
        "customer_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("customer_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("author_name", sa.String(200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        comment="Append-only internal notes for customers",
    )
    op.create_index(
        "ix_customer_notes_company_id",
        "customer_notes",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_customer_notes_customer_id",
        "customer_notes",
        ["customer_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # PostgreSQL FTS trigger for customers
    # ------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION update_customer_tsvector()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            NEW.tsvector_search :=
                to_tsvector('english',
                    coalesce(NEW.legal_name, '') || ' ' ||
                    coalesce(NEW.trading_name, '') || ' ' ||
                    coalesce(NEW.customer_code, '')
                );
            RETURN NEW;
        END;
        $$;
        """)
    op.execute("""
        CREATE TRIGGER trg_customer_tsvector
        BEFORE INSERT OR UPDATE ON customers
        FOR EACH ROW EXECUTE FUNCTION update_customer_tsvector();
        """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_customer_tsvector ON customers")
    op.execute("DROP FUNCTION IF EXISTS update_customer_tsvector()")

    op.drop_table("customer_notes")
    op.drop_table("customer_bank_details")
    op.drop_table("customer_addresses")
    op.drop_table("customer_contacts")
    op.drop_table("customers")

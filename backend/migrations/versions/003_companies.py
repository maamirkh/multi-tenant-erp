"""Epic 003 — Companies: create all companies module tables.

Creates the following tables in FK-dependency order:
  1. event_outbox     — shared transactional outbox (core infrastructure)
  2. companies        — primary tenant entity
  3. company_addresses — child addresses with FK to companies
  4. company_audit_logs — immutable audit trail with FK to companies

Two PostgreSQL ENUM types are created before the tables that use them:
  - businesstype  (companies.business_type)
  - addresstype   (company_addresses.address_type)

Index strategy (plan.md §9.5):
  - companies.lower(legal_name)  — expression UNIQUE index (case-insensitive)
  - companies.slug               — UNIQUE index
  - companies.owner_id           — BTREE
  - companies.status             — BTREE
  - companies.deleted_at         — BTREE (purge job queries)
  - companies.created_at         — BTREE
  - companies.subscription_id    — BTREE (future billing)
  - companies.custom_domain      — PARTIAL UNIQUE WHERE NOT NULL
  - company_addresses.(company_id, address_type) — COMPOSITE
  - company_audit_logs.(company_id, created_at) — COMPOSITE
  - company_audit_logs.actor_user_id — BTREE
  - event_outbox.(published, created_at) — COMPOSITE (relay polling)

Downgrade drops in strict reverse order respecting FK dependencies:
  company_audit_logs → company_addresses → companies → event_outbox

Revision ID: 003
Revises:     002
Create Date: 2026-07-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ── Revision identifiers ───────────────────────────────────────────────────

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ── PostgreSQL ENUM definitions ────────────────────────────────────────────

_business_type_enum = postgresql.ENUM(
    "sole_proprietor",
    "partnership",
    "llc",
    "corporation",
    "non_profit",
    "other",
    name="businesstype",
    create_type=False,
)

_address_type_enum = postgresql.ENUM(
    "registered",
    "mailing",
    "billing",
    "shipping",
    name="addresstype",
    create_type=False,
)


def upgrade() -> None:
    """Create all companies module tables in FK-dependency order."""

    # ── 0. PostgreSQL ENUM types ───────────────────────────────────────────
    _business_type_enum.create(op.get_bind(), checkfirst=True)
    _address_type_enum.create(op.get_bind(), checkfirst=True)

    # ── 1. event_outbox ───────────────────────────────────────────────────
    op.create_table(
        "event_outbox",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column("event_type", sa.String(200), nullable=False),
        sa.Column("aggregate_id", sa.String(200), nullable=False),
        sa.Column("aggregate_type", sa.String(200), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_event_outbox"),
    )
    op.create_index("ix_event_outbox_event_type", "event_outbox", ["event_type"])
    op.create_index("ix_event_outbox_aggregate_id", "event_outbox", ["aggregate_id"])
    op.create_index("ix_event_outbox_published", "event_outbox", ["published"])
    op.create_index(
        "ix_event_outbox_published_created_at",
        "event_outbox",
        ["published", "created_at"],
    )

    # ── 2. companies ──────────────────────────────────────────────────────
    op.create_table(
        "companies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        # Identity
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("trade_name", sa.String(255), nullable=True),
        sa.Column("slug", sa.String(100), nullable=False),
        # Status — VARCHAR with CHECK constraint (not PgEnum, for forward compatibility)
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending_setup'"),
        ),
        # Ownership
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("primary_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        # Contact
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("phone_primary", sa.String(20), nullable=True),
        sa.Column("phone_secondary", sa.String(20), nullable=True),
        sa.Column("website", sa.String(2048), nullable=True),
        # Legal / Tax
        sa.Column("tax_number", sa.String(50), nullable=True),
        sa.Column("registration_number", sa.String(50), nullable=True),
        sa.Column("business_category", sa.String(100), nullable=True),
        sa.Column("business_type", _business_type_enum, nullable=True),
        sa.Column("incorporation_date", sa.Date(), nullable=True),
        # Regional
        sa.Column("default_currency", sa.String(3), nullable=True),
        sa.Column("default_timezone", sa.String(100), nullable=True),
        sa.Column("default_language", sa.String(10), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column(
            "fiscal_year_start_month",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "date_format",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'YYYY-MM-DD'"),
        ),
        sa.Column(
            "number_format",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # Branding
        sa.Column("logo_url", sa.String(2048), nullable=True),
        sa.Column("logo_previous_url", sa.String(2048), nullable=True),
        sa.Column("brand_color_primary", sa.String(7), nullable=True),
        sa.Column("brand_color_secondary", sa.String(7), nullable=True),
        sa.Column("tagline", sa.String(255), nullable=True),
        # Extensibility
        sa.Column(
            "settings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # SaaS / Future
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("custom_domain", sa.String(253), nullable=True),
        # Soft delete
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_reason", sa.Text(), nullable=True),
        # Constraints
        sa.CheckConstraint(
            "status IN ('pending_setup','active','inactive','suspended','deleted')",
            name="ck_companies_status",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_companies_owner_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["primary_admin_id"],
            ["users.id"],
            name="fk_companies_primary_admin_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_companies"),
    )
    # Standard indexes
    op.create_index("ix_companies_slug", "companies", ["slug"], unique=True)
    op.create_index("ix_companies_owner_id", "companies", ["owner_id"])
    op.create_index("ix_companies_status", "companies", ["status"])
    op.create_index("ix_companies_deleted_at", "companies", ["deleted_at"])
    op.create_index("ix_companies_created_at", "companies", ["created_at"])
    op.create_index("ix_companies_subscription_id", "companies", ["subscription_id"])
    op.create_index(
        "ix_companies_status_deleted_at", "companies", ["status", "deleted_at"]
    )
    # Case-insensitive expression unique index on legal_name
    op.create_index(
        "ix_companies_lower_legal_name",
        "companies",
        [sa.text("lower(legal_name)")],
        unique=True,
    )
    # Partial unique index on custom_domain where NOT NULL
    op.create_index(
        "ix_companies_custom_domain",
        "companies",
        ["custom_domain"],
        unique=True,
        postgresql_where=sa.text("custom_domain IS NOT NULL"),
    )

    # ── 3. company_addresses ──────────────────────────────────────────────
    op.create_table(
        "company_addresses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("address_type", _address_type_enum, nullable=False),
        sa.Column("street_line_1", sa.String(255), nullable=False),
        sa.Column("street_line_2", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state_province", sa.String(100), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_company_addresses_company_id_companies",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_company_addresses"),
    )
    op.create_index(
        "ix_company_addresses_company_id_type",
        "company_addresses",
        ["company_id", "address_type"],
    )
    # Partial unique index: only one primary address of each type per company
    op.create_index(
        "ix_company_addresses_primary_per_type",
        "company_addresses",
        ["company_id", "address_type"],
        unique=True,
        postgresql_where=sa.text("is_primary = TRUE"),
    )

    # ── 4. company_audit_logs ─────────────────────────────────────────────
    op.create_table(
        "company_audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("before_state", postgresql.JSONB(), nullable=True),
        sa.Column("after_state", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_company_audit_logs_company_id_companies",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_company_audit_logs"),
    )
    op.create_index(
        "ix_company_audit_logs_company_id",
        "company_audit_logs",
        ["company_id"],
    )
    op.create_index(
        "ix_company_audit_logs_company_id_created_at",
        "company_audit_logs",
        ["company_id", "created_at"],
    )
    op.create_index(
        "ix_company_audit_logs_actor_user_id",
        "company_audit_logs",
        ["actor_user_id"],
    )


def downgrade() -> None:
    """Drop all companies module tables in reverse FK-dependency order."""

    # ── 4. company_audit_logs (first — FKs point to companies) ───────────
    op.drop_index(
        "ix_company_audit_logs_actor_user_id", table_name="company_audit_logs"
    )
    op.drop_index(
        "ix_company_audit_logs_company_id_created_at",
        table_name="company_audit_logs",
    )
    op.drop_index("ix_company_audit_logs_company_id", table_name="company_audit_logs")
    op.drop_table("company_audit_logs")

    # ── 3. company_addresses ──────────────────────────────────────────────
    op.drop_index(
        "ix_company_addresses_primary_per_type", table_name="company_addresses"
    )
    op.drop_index(
        "ix_company_addresses_company_id_type", table_name="company_addresses"
    )
    op.drop_table("company_addresses")

    # ── 2. companies ──────────────────────────────────────────────────────
    op.drop_index("ix_companies_custom_domain", table_name="companies")
    op.drop_index("ix_companies_lower_legal_name", table_name="companies")
    op.drop_index("ix_companies_status_deleted_at", table_name="companies")
    op.drop_index("ix_companies_subscription_id", table_name="companies")
    op.drop_index("ix_companies_created_at", table_name="companies")
    op.drop_index("ix_companies_deleted_at", table_name="companies")
    op.drop_index("ix_companies_status", table_name="companies")
    op.drop_index("ix_companies_owner_id", table_name="companies")
    op.drop_index("ix_companies_slug", table_name="companies")
    op.drop_table("companies")

    # ── 1. event_outbox ───────────────────────────────────────────────────
    op.drop_index("ix_event_outbox_published_created_at", table_name="event_outbox")
    op.drop_index("ix_event_outbox_published", table_name="event_outbox")
    op.drop_index("ix_event_outbox_aggregate_id", table_name="event_outbox")
    op.drop_index("ix_event_outbox_event_type", table_name="event_outbox")
    op.drop_table("event_outbox")

    # ── 0. Drop ENUM types ────────────────────────────────────────────────
    _address_type_enum.drop(op.get_bind(), checkfirst=True)
    _business_type_enum.drop(op.get_bind(), checkfirst=True)

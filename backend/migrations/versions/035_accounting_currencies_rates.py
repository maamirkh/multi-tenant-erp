"""Accounting currencies and exchange rates — Phase 1.

Creates:
  - accounting_currencies      (global registry, seeded with major ISO 4217 currencies)
  - accounting_exchange_rates  (company-scoped rate history)

Revision ID: 035
Revises: 034
Create Date: 2026-08-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None

# Seed data: major ISO 4217 currencies (iso_code, name, symbol, decimal_places)
_SEED_CURRENCIES = [
    ("USD", "US Dollar", "$", 2),
    ("EUR", "Euro", "€", 2),
    ("GBP", "British Pound", "£", 2),
    ("PKR", "Pakistani Rupee", "₨", 2),
    ("INR", "Indian Rupee", "₹", 2),
    ("AED", "UAE Dirham", "د.إ", 2),
    ("SAR", "Saudi Riyal", "﷼", 2),
    ("CNY", "Chinese Yuan", "¥", 2),
    ("JPY", "Japanese Yen", "¥", 0),
    ("AUD", "Australian Dollar", "$", 2),
    ("CAD", "Canadian Dollar", "$", 2),
    ("CHF", "Swiss Franc", "Fr", 2),
]


def upgrade() -> None:
    # --- accounting_currencies (global — no company_id) ---
    currencies_table = op.create_table(
        "accounting_currencies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("iso_code", sa.String(3), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("decimal_places", sa.Integer(), server_default="2", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("iso_code", name="uq_accounting_currencies_iso_code"),
        sa.CheckConstraint(
            "decimal_places >= 0", name="ck_accounting_currencies_decimals"
        ),
        comment="ISO 4217 currency registry — global reference data",
    )

    op.bulk_insert(
        currencies_table,
        [
            {
                "iso_code": code,
                "name": name,
                "symbol": symbol,
                "decimal_places": decimals,
                "is_active": True,
            }
            for code, name, symbol, decimals in _SEED_CURRENCIES
        ],
    )

    # --- accounting_exchange_rates (company-scoped) ---
    op.create_table(
        "accounting_exchange_rates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_currency_code", sa.String(3), nullable=False),
        sa.Column("to_currency_code", sa.String(3), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("rate", sa.Numeric(20, 10), nullable=False),
        sa.Column("rate_type", sa.String(20), server_default="SPOT", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "from_currency_code",
            "to_currency_code",
            "rate_date",
            "rate_type",
            name="uq_accounting_fx_rate_company_pair_date_type",
        ),
        sa.CheckConstraint("rate > 0", name="ck_accounting_fx_rate_positive"),
        comment="Exchange rate per currency pair per date, scoped per company",
    )
    op.create_index(
        "ix_accounting_fx_rates_lookup",
        "accounting_exchange_rates",
        [
            "company_id",
            "from_currency_code",
            "to_currency_code",
            sa.text("rate_date DESC"),
        ],
    )


def downgrade() -> None:
    op.drop_table("accounting_exchange_rates")
    op.drop_table("accounting_currencies")

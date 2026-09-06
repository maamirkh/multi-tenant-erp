"""Fix missing server-side defaults on created_at/updated_at — Epics 5-7.

**Defect found during Epic 1-8 consolidated live verification** (not part of
any approved task in this epic's tasks.md — a genuine, previously-
undetected schema defect discovered while live-testing Epic 5/6/7 against
the real Docker/PostgreSQL stack for the first time).

Root cause: ``core.database.models.base_model.BaseModel`` correctly
declares ``server_default=func.now()`` on both ``created_at`` and
``updated_at`` for every model in the codebase. But the Alembic migrations
that originally created 43 Inventory/Purchase/Sales tables (Epic 5/6/7,
migrations 004-033) did not include a matching ``server_default`` in their
raw ``op.create_table()`` DDL for these two columns — a drift between the
ORM model (correct) and the actual migration-applied schema (missing).

This was invisible to the ENTIRE existing test suite (3300+ tests across
Epics 5-7) because ``tests/conftest.py``'s SQLite test database is built via
``Base.metadata.create_all(engine)`` — i.e. derived live from the CURRENT
ORM model definitions on every test run, completely bypassing Alembic
migrations. Only a real PostgreSQL database built from the actual migration
files (as this live-verification session did, for the first time against
Epic 5/6/7 tables specifically) can expose migration-vs-model drift like
this. (The same class of bug — migration/model or migration/migration drift
invisible to SQLite tests — was already found and fixed twice in Epic 8's
own migrations 048/049 during Phase 18; this is the same root cause
recurring in three earlier, previously-unverified epics.)

Impact: any INSERT into one of these 43 tables that does not explicitly
set ``created_at``/``updated_at`` in Python (the universal pattern
throughout this codebase — see ``BaseRepository.create()``'s docstring:
"``id``, ``created_at``, ``updated_at`` ... are populated" by the server)
fails with a NOT NULL constraint violation against real PostgreSQL. This
blocked live verification of basic Inventory warehouse/product creation,
Purchase supplier creation, and Sales customer/order/invoice creation —
i.e., the majority of Epic 5/6/7's core write paths — the moment they were
exercised against Postgres instead of SQLite.

Fix: purely additive ``ALTER COLUMN ... SET DEFAULT now()`` for all 54
affected columns across 43 tables. Does not touch existing data or change
any column's nullability/type — safe, reversible, zero data risk.

Spec ref: none (pre-existing defect in Epics 5-7, found during Epic 1-8
consolidated live verification, fixed per that verification's explicit
"smallest safe fix + document + regression test" mandate)
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "051"
down_revision = "050"
branch_labels = None
depends_on = None


_AFFECTED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("bank_details", "updated_at"),
    ("credit_limits", "updated_at"),
    ("customer_categories", "updated_at"),
    ("customer_groups", "updated_at"),
    ("customer_specific_prices", "updated_at"),
    ("delivery_note_lines", "updated_at"),
    ("delivery_notes", "updated_at"),
    ("discount_rules", "updated_at"),
    ("inventory_adjustments", "created_at"),
    ("inventory_adjustments", "updated_at"),
    ("inventory_fifo_cost_layers", "created_at"),
    ("inventory_fifo_cost_layers", "updated_at"),
    ("inventory_snapshot_lines", "created_at"),
    ("inventory_snapshot_lines", "updated_at"),
    ("inventory_snapshots", "created_at"),
    ("inventory_snapshots", "updated_at"),
    ("inventory_stock_movements", "created_at"),
    ("inventory_stock_movements", "updated_at"),
    ("inventory_stock_positions", "created_at"),
    ("inventory_stock_positions", "updated_at"),
    ("inventory_stock_transfer_lines", "created_at"),
    ("inventory_stock_transfer_lines", "updated_at"),
    ("inventory_stock_transfers", "created_at"),
    ("inventory_stock_transfers", "updated_at"),
    ("inventory_warehouse_locations", "created_at"),
    ("inventory_warehouse_locations", "updated_at"),
    ("inventory_warehouses", "created_at"),
    ("inventory_warehouses", "updated_at"),
    ("invoice_charges", "updated_at"),
    ("invoice_lines", "updated_at"),
    ("order_lines", "updated_at"),
    ("price_entries", "updated_at"),
    ("price_lists", "updated_at"),
    ("quotation_lines", "updated_at"),
    ("quotation_revisions", "updated_at"),
    ("sales_approval_matrices", "updated_at"),
    ("sales_approval_records", "updated_at"),
    ("sales_configuration", "updated_at"),
    ("sales_feature_flags", "updated_at"),
    ("sales_invoices", "updated_at"),
    ("sales_matrix_rules", "updated_at"),
    ("sales_orders", "updated_at"),
    ("sales_payment_terms", "updated_at"),
    ("sales_quotations", "updated_at"),
    ("sales_reason_codes", "updated_at"),
    ("sales_return_lines", "updated_at"),
    ("sales_returns", "updated_at"),
    ("sales_sequences", "updated_at"),
    ("supplier_addresses", "updated_at"),
    ("supplier_contacts", "updated_at"),
    ("supplier_documents", "updated_at"),
    ("supplier_lead_times", "updated_at"),
    ("supplier_ratings", "updated_at"),
    ("suppliers", "updated_at"),
)


def upgrade() -> None:
    for table, column in _AFFECTED_COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT now()")


def downgrade() -> None:
    for table, column in _AFFECTED_COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT")

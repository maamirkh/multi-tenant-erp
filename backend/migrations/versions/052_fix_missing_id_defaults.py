"""Fix missing server-side defaults on id (primary key) — Epics 5-7.

**Defect found during Epic 1-8 consolidated live verification** (2026-08-14,
same session as migration 051 — a second, distinct instance of the same
root cause: migration-vs-ORM-model drift, invisible to the SQLite test
suite for the identical reason documented in 051).

Root cause: ``core.database.models.base_model.BaseModel`` declares
``id: Mapped[UUID] = mapped_column(..., server_default=text("gen_random_uuid()"))``
for every model. The Alembic migrations that created these 23
Inventory/Sales tables did not include a matching ``server_default`` on
their ``id`` column DDL. Unlike migration 051 (created_at/updated_at,
harmless-looking until you insert), a missing default on ``id`` itself is
immediately fatal: ANY insert that relies on the server to generate the
primary key (the universal pattern in this codebase — ORM objects are
constructed without an explicit ``id=...`` kwarg) fails outright with a
NOT NULL violation on the primary key column.

Found via: ``POST /companies/{id}/sales/customers`` returning a real
``IntegrityError`` (``null value in column "id" of relation "customers"
violates not-null constraint``) during live verification of the Sales
module against real PostgreSQL for the first time.

``permissions.id`` is deliberately excluded — it is a string dot-notation
code (e.g. ``"members.create"``), always supplied explicitly by
application code (see ``modules/users_roles/models/permission.py``), not a
server-generated UUID. Including it would be wrong, not merely redundant.

Fix: purely additive ``ALTER COLUMN id SET DEFAULT gen_random_uuid()`` for
the 23 affected tables. Does not touch existing data or any column's
nullability/type — safe, reversible, zero data risk.

Spec ref: none (pre-existing defect in Epics 5-7, found during Epic 1-8
consolidated live verification, fixed per that verification's explicit
"smallest safe fix + document + regression test" mandate — same mandate
migration 051 was fixed under)
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "052"
down_revision = "051"
branch_labels = None
depends_on = None


_AFFECTED_TABLES: tuple[str, ...] = (
    "customer_addresses",
    "customer_bank_details",
    "customer_contacts",
    "customer_notes",
    "customers",
    "inventory_adjustments",
    "inventory_fifo_cost_layers",
    "inventory_low_stock_alerts",
    "inventory_reorder_rules",
    "inventory_reorder_suggestions",
    "inventory_snapshot_lines",
    "inventory_snapshots",
    "inventory_stock_movements",
    "inventory_stock_positions",
    "inventory_stock_transfer_lines",
    "inventory_stock_transfers",
    "inventory_warehouse_locations",
    "inventory_warehouses",
    "invoice_charges",
    "invoice_lines",
    "sales_invoices",
    "sales_return_lines",
    "sales_returns",
)


def upgrade() -> None:
    for table in _AFFECTED_TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN id SET DEFAULT gen_random_uuid()")


def downgrade() -> None:
    for table in _AFFECTED_TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN id DROP DEFAULT")

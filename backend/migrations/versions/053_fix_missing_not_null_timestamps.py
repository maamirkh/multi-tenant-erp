"""Fix missing NOT NULL constraint on created_at/updated_at — Purchase & Sales.

**Defect found during the post-Epic-8, pre-Epic-9 hardening audit**
(2026-08-14) — a distinct, previously-unremediated sibling of the
migration-vs-model drift already fixed once for these same columns in
migration 051 (server_default) and again in 052 (id server_default).

Root cause: ``core.database.models.base_model.BaseModel`` declares
``created_at``/``updated_at`` as ``nullable=False`` for every model. The
migrations that originally created the 34 affected Purchase/Sales tables
(migrations 016-033) correctly matched the model's ``server_default`` after
051 was applied, but never applied the matching ``NOT NULL`` constraint at
the DB level — the column DDL left them nullable. This is invisible to the
SQLite test suite for the same reason 051/052 were: SQLite tests build their
schema live from the ORM models via ``Base.metadata.create_all()``, which
always gets ``nullable=False`` right; only a real Postgres database built
from the actual migration files can show the drift.

Practical risk: because these columns already carry ``server_default =
now()`` (fixed by migration 051) and the ORM never explicits sets them to
``NULL`` on insert, this drift has not caused an observed failure — but it
is a real, unenforced invariant. Any direct-SQL bulk load, data-migration
script, or future ORM change that omits the column would silently insert a
NULL where the model guarantees non-null, and any code (including,
plausibly, Epic 9's own new services) built against the documented model
contract could break on an unexpected `None`.

Inventory tables (migrations 004-014) are NOT affected — they were built
with the correct NOT NULL constraint from the start; only Purchase/Sales
tables (016-033) have this specific gap. Verified zero existing NULL rows
in every affected column before writing this migration (see hardening audit
report) — the ALTER COLUMN ... SET NOT NULL is guaranteed to succeed.

Fix: purely additive ``ALTER COLUMN ... SET NOT NULL`` for the 36 affected
columns across 34 tables. Does not touch existing data or any column's
default/type — safe, reversible (downgrade restores nullable), zero data
risk given the confirmed absence of existing NULLs.

Spec ref: none (pre-existing defect in Epics 6-7, found during the
pre-Epic-9 hardening audit, fixed per that audit's "smallest safe fix +
document + regression test" mandate)
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None


_AFFECTED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("bank_details", "updated_at"),
    ("credit_limits", "updated_at"),
    ("customer_categories", "updated_at"),
    ("customer_groups", "updated_at"),
    ("customer_specific_prices", "updated_at"),
    ("delivery_note_lines", "created_at"),
    ("delivery_note_lines", "updated_at"),
    ("delivery_notes", "created_at"),
    ("delivery_notes", "updated_at"),
    ("discount_rules", "updated_at"),
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
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET NOT NULL")


def downgrade() -> None:
    for table, column in _AFFECTED_COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP NOT NULL")

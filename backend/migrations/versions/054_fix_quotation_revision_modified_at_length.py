"""Widen quotation_revisions.modified_at from VARCHAR(30) to VARCHAR(40).

**Defect found live during the pre-Epic-9 hardening audit** (2026-08-15,
discovered incidentally while live-verifying the transaction/commit fixes
against real Postgres — not one of the audit's five named focus areas, but
a genuine, demonstrated production-breaking defect fixed under the same
audit's "you MAY fix it: document, root-cause, smallest fix, add a
regression test, re-verify" mandate).

Root cause: ``modules.sales.models.quotation.QuotationRevision.modified_at``
was declared ``String(30)``, but ``QuotationService._capture_revision()``
always writes ``utcnow().isoformat()``, which — with microseconds and a
UTC offset — is 32 characters (e.g. ``"2026-08-15T07:57:23.605415+00:00"``).
Every quotation creation calls ``_capture_revision()`` once, so this was a
100%-reproducible crash (``psycopg2.errors.StringDataRightTruncation``) on
real PostgreSQL — confirmed live: ``POST /companies/{id}/sales/quotations``
returned a 500 for any request. Invisible to the entire Sales test suite
(3600+ tests, all previously green) because SQLite has no VARCHAR length
enforcement — the exact same "migration/model constraint invisible to
SQLite" root cause documented in migrations 051-053.

Fix: purely additive ``ALTER COLUMN modified_at TYPE VARCHAR(40)``. Does
not touch existing data (existing values are all <=30 chars and fit the
wider type unchanged) — safe, reversible, zero data risk.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "054"
down_revision = "053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE quotation_revisions ALTER COLUMN modified_at TYPE VARCHAR(40)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE quotation_revisions ALTER COLUMN modified_at TYPE VARCHAR(30)"
    )

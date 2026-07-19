"""Initial schema baseline.

This is an empty baseline migration.  It establishes the Alembic version
history without making any schema changes.

All future migrations reference this revision as ``down_revision``, giving
the migration history a clean, unambiguous starting point.

Revision ID: 001
Revises:     (none — root of the migration graph)
Create Date: 2026-07-11

"""

from collections.abc import Sequence

from alembic import op  # noqa: F401 — available for future use

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Baseline upgrade — no schema changes.

    Epic 1 creates no business tables.  Future migrations add tables on top
    of this baseline via sequential ``down_revision`` chains.
    """


def downgrade() -> None:
    """Baseline downgrade — no schema changes.

    Downgrading below the baseline is a no-op; the Alembic version table
    itself is managed by Alembic and is not removed here.
    """

"""Reports audit log table — Epic 11, Phase 6 (T179).

Creates ``reports_audit_log`` (append-only audit trail for every export
and every saved-view create/update/delete — plan.md §22, data-model.md)
with its two indexes: ``ix_reports_audit_log_company_created_at``
(chronological per-tenant audit review) and
``ix_reports_audit_log_company_actor`` (per-user audit review).

**Renumbered (2026-09-28)**: tasks.md T179 names this ``076`` /
``down_revision="075"``, but ``076`` was already taken by Phase 1's
``076_reports_saved_report_views_table.py`` (itself renumbered from its
own planned ``075``, see that file's docstring). Shifted to ``077`` —
same renumbering rationale; Phase 10's conditional T268 index migration
therefore becomes ``078`` if it is ever needed.

Revision ID: 077
Revises: 076
Create Date: 2026-09-28
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "077"
down_revision = "076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports_audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("before", postgresql.JSONB(), nullable=True),
        sa.Column("after", postgresql.JSONB(), nullable=True),
        sa.Column("report_key", sa.String(100), nullable=True),
        sa.Column("filter_scope", postgresql.JSONB(), nullable=True),
        sa.Column("format", sa.String(10), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
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
        comment="Append-only Reports & Analytics audit trail",
    )
    op.create_index(
        "ix_reports_audit_log_company_id",
        "reports_audit_log",
        ["company_id"],
    )
    op.create_index(
        "ix_reports_audit_log_company_created_at",
        "reports_audit_log",
        ["company_id", "created_at"],
    )
    op.create_index(
        "ix_reports_audit_log_company_actor",
        "reports_audit_log",
        ["company_id", "actor_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_reports_audit_log_company_actor", "reports_audit_log")
    op.drop_index("ix_reports_audit_log_company_created_at", "reports_audit_log")
    op.drop_index("ix_reports_audit_log_company_id", "reports_audit_log")
    op.drop_table("reports_audit_log")

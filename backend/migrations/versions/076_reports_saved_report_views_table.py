"""Reports saved report views table — Epic 11, Phase 1 (T040).

Creates ``saved_report_views`` (private, user-owned reporting
configuration, spec §29/data-model.md) with its two indexes
(plan.md §17): ``ix_saved_report_views_company_user`` (list-my-views
lookup) and ``ix_saved_report_views_company_report_key`` (registry-
retirement audit/cleanup queries).

**Renumbered per explicit correction (2026-09-12)**: originally candidate
``075`` in plan.md §16/tasks.md T040; shifted to ``076`` because Phase
0's ``073_reports_foundation.py`` and this epic's own ``074``/``075``
(capability/permission seed) all precede it.

Revision ID: 076
Revises: 075
Create Date: 2026-09-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "076"
down_revision = "075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_report_views",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("filter_config", postgresql.JSONB(), nullable=False),
        sa.Column("grouping", postgresql.JSONB(), nullable=True),
        sa.Column("sorting", sa.String(100), nullable=True),
        sa.Column("visible_columns", postgresql.JSONB(), nullable=True),
        sa.Column("date_preset", sa.String(30), nullable=True),
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
        comment="Private, user-owned saved report view configurations",
    )
    op.create_index(
        "ix_saved_report_views_company_user",
        "saved_report_views",
        ["company_id", "user_id"],
    )
    op.create_index(
        "ix_saved_report_views_company_report_key",
        "saved_report_views",
        ["company_id", "report_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_saved_report_views_company_report_key", "saved_report_views")
    op.drop_index("ix_saved_report_views_company_user", "saved_report_views")
    op.drop_table("saved_report_views")

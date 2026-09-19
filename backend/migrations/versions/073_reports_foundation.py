"""Reports foundation — Epic 11 Phase 0 corrective addition.

Creates ``reports_feature_flags``, the per-company override table backing
``ReportsFeatureFlagService``/``ReportsModuleEnablementProvider``
(plan.md §12), mirroring ``crm_feature_flags``
(``055_crm_foundation.py``)/``installments_feature_flags``
(``062_installments_foundation.py``) exactly.

**Correction note**: `specs/011-reports-analytics/tasks.md` (Phase 0/1)
never lists a migration for this table, even though plan.md §12 and
tasks.md T005/T006 both require a row-backed ``ReportsFeatureFlagService``
identical in shape to CRM's/Installments' own per-module tables — an
omission discovered while implementing Phase 0 (Gate 0's entitlement
round-trip test cannot pass without this table existing against real
Postgres). This is the smallest possible fix: one additive migration,
narrowly scoped to the one missing table, inserted at the epic's actual
next free revision number. **Downstream effect**: when Phase 1 is
implemented, its four migrations (capability seed, permission seed, saved
views table, audit log table) must be renumbered ``074-077`` (instead of
the doc's stated ``073-076``), with matching ``down_revision`` shifts; no
other Phase 1 content changes.

Revision ID: 073
Revises: 072
Create Date: 2026-09-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "073"
down_revision = "072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports_feature_flags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("flag_key", sa.String(50), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
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
        sa.UniqueConstraint("company_id", "flag_key", name="uq_reports_ff_company_key"),
        comment="Per-company feature flag overrides for the Reports module",
    )
    op.create_index(
        "ix_reports_feature_flags_flag_key", "reports_feature_flags", ["flag_key"]
    )
    op.create_index(
        "ix_reports_feature_flags_company_id",
        "reports_feature_flags",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_reports_feature_flags_company_id", "reports_feature_flags")
    op.drop_index("ix_reports_feature_flags_flag_key", "reports_feature_flags")
    op.drop_table("reports_feature_flags")

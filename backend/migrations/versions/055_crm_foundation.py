"""CRM foundation — Epic 9, Phase 1 (Part A) + Phase 2 (Part B).

Part A (Phase 1) created only the module gate:
  - crm_feature_flags

Part B (this revision, Phase 2) appends the remaining 7 tables
(crm_lead_sources, crm_pipelines, crm_pipeline_stages, crm_leads,
crm_opportunities, crm_activities, crm_audit_log) to this SAME migration
file — CRM's entire schema is a single linear migration, per plan.md
§7/§29.2, not one migration per phase.

Every column's ``server_default``/``nullable``/``CHECK``/index is declared
explicitly here to match its ORM model exactly (see
``backend/modules/crm/models/``) — this is the single most important
lesson from migrations 051-054 (four separate real defects, all caused by
raw DDL omitting a ``server_default`` the ORM model declared).

Circular FK note: ``crm_leads.converted_opportunity_id`` references
``crm_opportunities.id``, but ``crm_opportunities`` (via
``source_lead_id``) also references ``crm_leads.id``. ``crm_leads`` is
created first (dependency order below) with that column but WITHOUT its FK
constraint; the FK is added via ``op.create_foreign_key()`` once
``crm_opportunities`` exists — the standard two-table-cycle technique,
matching the ORM model's ``ForeignKey(..., use_alter=True)`` declaration
in ``modules/crm/models/lead.py``.

Partial unique indexes (BR-008 default-pipeline, at-most-one
won/lost-stage) are created via raw ``CREATE UNIQUE INDEX ... WHERE ...``,
the same technique already used by migration 013
(``uq_inv_alert_open_dedup``) for an equivalent "at most one X per group"
invariant.

Revision ID: 055
Revises: 054
Create Date: 2026-08-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "055"
down_revision = "054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- crm_feature_flags ---
    op.create_table(
        "crm_feature_flags",
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
        sa.UniqueConstraint("company_id", "flag_key", name="uq_crm_ff_company_key"),
        comment="Per-company feature flag overrides for the CRM module",
    )
    op.create_index("ix_crm_feature_flags_flag_key", "crm_feature_flags", ["flag_key"])

    # --- crm_lead_sources ---
    op.create_table(
        "crm_lead_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
            "company_id", "code", name="uq_crm_lead_sources_company_code"
        ),
        comment="Company-configurable CRM lead-source lookup values",
    )
    op.create_index(
        "ix_crm_lead_sources_company_active",
        "crm_lead_sources",
        ["company_id", "is_active"],
    )

    # --- crm_pipelines ---
    op.create_table(
        "crm_pipelines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
        comment="Company-configurable CRM sales pipelines",
    )
    # BR-008: exactly one active default pipeline per company.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_crm_pipelines_company_default
        ON crm_pipelines (company_id)
        WHERE is_default = true AND is_deleted = false
        """
    )

    # --- crm_pipeline_stages ---
    op.create_table(
        "crm_pipeline_stages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("probability", sa.Integer(), nullable=False),
        sa.Column("is_won_stage", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "is_lost_stage", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
        sa.ForeignKeyConstraint(
            ["pipeline_id"],
            ["crm_pipelines.id"],
            name="fk_crm_pipeline_stages_pipeline_id",
        ),
        sa.CheckConstraint("sequence >= 1", name="ck_crm_pipeline_stages_sequence"),
        sa.CheckConstraint(
            "probability BETWEEN 0 AND 100",
            name="ck_crm_pipeline_stages_probability",
        ),
        comment="Ordered stages within a CRM Pipeline",
    )
    op.create_index(
        "ix_crm_pipeline_stages_company_pipeline_seq",
        "crm_pipeline_stages",
        ["company_id", "pipeline_id", "sequence"],
    )
    # At most one won-stage and one lost-stage per pipeline.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_crm_pipeline_stages_won
        ON crm_pipeline_stages (pipeline_id)
        WHERE is_won_stage = true AND is_deleted = false
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_crm_pipeline_stages_lost
        ON crm_pipeline_stages (pipeline_id)
        WHERE is_lost_stage = true AND is_deleted = false
        """
    )

    # --- crm_leads ---
    op.create_table(
        "crm_leads",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("lead_company_name", sa.String(200), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("mobile", sa.String(30), nullable=True),
        sa.Column("address_line1", sa.String(300), nullable=True),
        sa.Column("address_line2", sa.String(300), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'NEW'"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_contact_date", sa.Date(), nullable=True),
        sa.Column("next_follow_up_date", sa.Date(), nullable=True),
        sa.Column("qualification_notes", sa.Text(), nullable=True),
        sa.Column("disqualification_reason", sa.Text(), nullable=True),
        sa.Column(
            "converted_customer_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        # No inline FK — crm_opportunities does not exist yet. Added below
        # via op.create_foreign_key() once crm_opportunities is created.
        sa.Column(
            "converted_opportunity_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["source_id"], ["crm_lead_sources.id"], name="fk_crm_leads_source_id"
        ),
        sa.CheckConstraint(
            "status IN ('NEW', 'CONTACTED', 'QUALIFIED', 'UNQUALIFIED', "
            "'CONVERTED', 'LOST')",
            name="ck_crm_leads_status",
        ),
        sa.CheckConstraint(
            "score IS NULL OR score BETWEEN 0 AND 100", name="ck_crm_leads_score"
        ),
        sa.CheckConstraint(
            "first_name IS NOT NULL OR last_name IS NOT NULL "
            "OR lead_company_name IS NOT NULL",
            name="ck_crm_leads_name_or_company",
        ),
        sa.CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL",
            name="ck_crm_leads_email_or_phone",
        ),
        sa.CheckConstraint("version >= 1", name="ck_crm_leads_version"),
        comment="CRM Lead aggregate root — an unqualified prospect",
    )
    op.create_index(
        "ix_crm_leads_company_status", "crm_leads", ["company_id", "status"]
    )
    op.create_index(
        "ix_crm_leads_company_owner", "crm_leads", ["company_id", "owner_id"]
    )
    op.create_index(
        "ix_crm_leads_company_follow_up",
        "crm_leads",
        ["company_id", "next_follow_up_date"],
    )
    op.create_index("ix_crm_leads_company_email", "crm_leads", ["company_id", "email"])

    # --- crm_opportunities ---
    op.create_table(
        "crm_opportunities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "value",
            sa.Numeric(15, 2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("probability", sa.Integer(), nullable=False),
        sa.Column("expected_close_date", sa.Date(), nullable=True),
        sa.Column("source_lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(10),
            server_default=sa.text("'OPEN'"),
            nullable=False,
        ),
        sa.Column("lost_reason", sa.Text(), nullable=True),
        sa.Column("won_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quotation_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["pipeline_id"],
            ["crm_pipelines.id"],
            name="fk_crm_opportunities_pipeline_id",
        ),
        sa.ForeignKeyConstraint(
            ["stage_id"],
            ["crm_pipeline_stages.id"],
            name="fk_crm_opportunities_stage_id",
        ),
        sa.ForeignKeyConstraint(
            ["source_lead_id"],
            ["crm_leads.id"],
            name="fk_crm_opportunities_source_lead_id",
        ),
        sa.CheckConstraint("value >= 0", name="ck_crm_opportunities_value"),
        sa.CheckConstraint(
            "probability BETWEEN 0 AND 100",
            name="ck_crm_opportunities_probability",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'WON', 'LOST')", name="ck_crm_opportunities_status"
        ),
        comment="CRM Opportunity aggregate root — a trackable sales pursuit",
    )
    op.create_index(
        "ix_crm_opportunities_company_status",
        "crm_opportunities",
        ["company_id", "status"],
    )
    op.create_index(
        "ix_crm_opportunities_company_owner",
        "crm_opportunities",
        ["company_id", "owner_id"],
    )
    op.create_index(
        "ix_crm_opportunities_company_customer",
        "crm_opportunities",
        ["company_id", "customer_id"],
    )
    op.create_index(
        "ix_crm_opportunities_company_pipeline_stage",
        "crm_opportunities",
        ["company_id", "pipeline_id", "stage_id"],
    )
    op.create_index(
        "ix_crm_opportunities_company_close_date",
        "crm_opportunities",
        ["company_id", "expected_close_date"],
    )

    # Deferred FK closing the crm_leads <-> crm_opportunities cycle, now that
    # crm_opportunities exists (matches ORM's ForeignKey(use_alter=True)).
    op.create_foreign_key(
        "fk_crm_leads_converted_opportunity_id",
        "crm_leads",
        "crm_opportunities",
        ["converted_opportunity_id"],
        ["id"],
    )

    # --- crm_activities ---
    op.create_table(
        "crm_activities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activity_type", sa.String(15), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(15),
            server_default=sa.text("'PLANNED'"),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.String(10),
            server_default=sa.text("'MEDIUM'"),
            nullable=False,
        ),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["lead_id"], ["crm_leads.id"], name="fk_crm_activities_lead_id"
        ),
        sa.ForeignKeyConstraint(
            ["opportunity_id"],
            ["crm_opportunities.id"],
            name="fk_crm_activities_opportunity_id",
        ),
        sa.CheckConstraint(
            "activity_type IN ('CALL', 'EMAIL', 'MEETING', 'TASK', 'NOTE', "
            "'FOLLOW_UP')",
            name="ck_crm_activities_type",
        ),
        sa.CheckConstraint(
            "status IN ('PLANNED', 'COMPLETED', 'CANCELLED')",
            name="ck_crm_activities_status",
        ),
        sa.CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_crm_activities_priority",
        ),
        sa.CheckConstraint(
            "lead_id IS NOT NULL OR customer_id IS NOT NULL "
            "OR opportunity_id IS NOT NULL",
            name="ck_crm_activities_has_relation",
        ),
        comment="CRM Activity — a single dated interaction or task",
    )
    op.create_index(
        "ix_crm_activities_company_assigned_status",
        "crm_activities",
        ["company_id", "assigned_to", "status"],
    )
    op.create_index(
        "ix_crm_activities_company_due_date",
        "crm_activities",
        ["company_id", "due_date"],
    )
    op.create_index(
        "ix_crm_activities_company_lead", "crm_activities", ["company_id", "lead_id"]
    )
    op.create_index(
        "ix_crm_activities_company_customer",
        "crm_activities",
        ["company_id", "customer_id"],
    )
    op.create_index(
        "ix_crm_activities_company_opportunity",
        "crm_activities",
        ["company_id", "opportunity_id"],
    )

    # --- crm_audit_log ---
    op.create_table(
        "crm_audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("before_state", postgresql.JSONB(), nullable=True),
        sa.Column("after_state", postgresql.JSONB(), nullable=True),
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
        comment="Append-only CRM audit trail",
    )
    op.create_index(
        "ix_crm_audit_log_company_entity",
        "crm_audit_log",
        ["company_id", "entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_table("crm_audit_log")

    op.drop_index("ix_crm_activities_company_opportunity", "crm_activities")
    op.drop_index("ix_crm_activities_company_customer", "crm_activities")
    op.drop_index("ix_crm_activities_company_lead", "crm_activities")
    op.drop_index("ix_crm_activities_company_due_date", "crm_activities")
    op.drop_index("ix_crm_activities_company_assigned_status", "crm_activities")
    op.drop_table("crm_activities")

    # Drop the deferred cross-cycle FK before dropping either side of it.
    op.drop_constraint(
        "fk_crm_leads_converted_opportunity_id", "crm_leads", type_="foreignkey"
    )

    op.drop_index("ix_crm_opportunities_company_close_date", "crm_opportunities")
    op.drop_index("ix_crm_opportunities_company_pipeline_stage", "crm_opportunities")
    op.drop_index("ix_crm_opportunities_company_customer", "crm_opportunities")
    op.drop_index("ix_crm_opportunities_company_owner", "crm_opportunities")
    op.drop_index("ix_crm_opportunities_company_status", "crm_opportunities")
    op.drop_table("crm_opportunities")

    op.drop_index("ix_crm_leads_company_email", "crm_leads")
    op.drop_index("ix_crm_leads_company_follow_up", "crm_leads")
    op.drop_index("ix_crm_leads_company_owner", "crm_leads")
    op.drop_index("ix_crm_leads_company_status", "crm_leads")
    op.drop_table("crm_leads")

    op.execute("DROP INDEX IF EXISTS uq_crm_pipeline_stages_lost")
    op.execute("DROP INDEX IF EXISTS uq_crm_pipeline_stages_won")
    op.drop_index("ix_crm_pipeline_stages_company_pipeline_seq", "crm_pipeline_stages")
    op.drop_table("crm_pipeline_stages")

    op.execute("DROP INDEX IF EXISTS uq_crm_pipelines_company_default")
    op.drop_table("crm_pipelines")

    op.drop_index("ix_crm_lead_sources_company_active", "crm_lead_sources")
    op.drop_table("crm_lead_sources")

    op.drop_table("crm_feature_flags")

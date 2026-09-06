"""DB-level constraint tests for CRM Phase 2 (Epic 9).

Proves the database-level invariants from plan.md §6.3/§6.4/§6.6 are real,
not just documented:
  - BR-008: at most one is_default=true Pipeline per company.
  - At most one is_won_stage=true / is_lost_stage=true PipelineStage per
    pipeline.
  - BR-006: an Activity must relate to at least one of Lead/Customer/
    Opportunity.

Run against SQLite (the shared in-memory test engine) rather than a live
Postgres container: every partial unique index in this module's models
declares BOTH ``postgresql_where`` and ``sqlite_where`` (the same dual
convention already established by
``modules/inventory/models/alerts.py::LowStockAlert.uq_inv_alert_open_dedup``),
and SQLite enforces CHECK constraints natively — so these invariants are
genuinely exercised here, not merely documented as "Postgres-only, verify
later". Live Postgres replay of the full migration is still performed as
part of the epic's final comprehensive verification pass, per the
project's phased implementation instructions.

Task: T021 (tasks.md Phase 2).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from modules.crm.models.activity import Activity
from modules.crm.models.pipeline import Pipeline
from modules.crm.models.pipeline_stage import PipelineStage


class TestDefaultPipelineConstraint:
    """BR-008: exactly one is_default=true Pipeline per company."""

    def test_second_default_pipeline_for_same_company_rejected(
        self, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        db_session.add(Pipeline(company_id=company_id, name="First", is_default=True))
        db_session.flush()

        db_session.add(Pipeline(company_id=company_id, name="Second", is_default=True))
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestPipelineStageWonLostConstraints:
    """At most one is_won_stage=true and one is_lost_stage=true per pipeline."""

    def test_second_won_stage_on_same_pipeline_rejected(
        self, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        pipeline = Pipeline(company_id=company_id, name="Std")
        db_session.add(pipeline)
        db_session.flush()

        db_session.add(
            PipelineStage(
                company_id=company_id,
                pipeline_id=pipeline.id,
                name="Closed Won",
                sequence=1,
                probability=100,
                is_won_stage=True,
            )
        )
        db_session.flush()

        db_session.add(
            PipelineStage(
                company_id=company_id,
                pipeline_id=pipeline.id,
                name="Another Won",
                sequence=2,
                probability=100,
                is_won_stage=True,
            )
        )
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_second_lost_stage_on_same_pipeline_rejected(
        self, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        pipeline = Pipeline(company_id=company_id, name="Std")
        db_session.add(pipeline)
        db_session.flush()

        db_session.add(
            PipelineStage(
                company_id=company_id,
                pipeline_id=pipeline.id,
                name="Closed Lost",
                sequence=1,
                probability=0,
                is_lost_stage=True,
            )
        )
        db_session.flush()

        db_session.add(
            PipelineStage(
                company_id=company_id,
                pipeline_id=pipeline.id,
                name="Another Lost",
                sequence=2,
                probability=0,
                is_lost_stage=True,
            )
        )
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_won_and_lost_stage_may_coexist_on_same_pipeline(
        self, db_session: Session
    ) -> None:
        """The won/lost partial indexes are independent — one of each is fine."""
        company_id = uuid.uuid4()
        pipeline = Pipeline(company_id=company_id, name="Std")
        db_session.add(pipeline)
        db_session.flush()

        db_session.add(
            PipelineStage(
                company_id=company_id,
                pipeline_id=pipeline.id,
                name="Closed Won",
                sequence=1,
                probability=100,
                is_won_stage=True,
            )
        )
        db_session.add(
            PipelineStage(
                company_id=company_id,
                pipeline_id=pipeline.id,
                name="Closed Lost",
                sequence=2,
                probability=0,
                is_lost_stage=True,
            )
        )
        db_session.flush()  # must not raise


class TestActivityRelationCheckConstraint:
    """BR-006: an Activity must relate to at least one of lead/customer/opportunity."""

    def test_activity_with_no_relation_rejected(self, db_session: Session) -> None:
        db_session.add(
            Activity(
                company_id=uuid.uuid4(),
                activity_type="NOTE",
                subject="Orphan note",
                assigned_to=str(uuid.uuid4()),
            )
        )
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_activity_with_customer_relation_accepted(
        self, db_session: Session
    ) -> None:
        db_session.add(
            Activity(
                company_id=uuid.uuid4(),
                activity_type="NOTE",
                subject="Linked note",
                assigned_to=str(uuid.uuid4()),
                customer_id=str(uuid.uuid4()),
            )
        )
        db_session.flush()  # must not raise

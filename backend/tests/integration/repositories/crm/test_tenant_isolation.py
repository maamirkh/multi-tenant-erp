"""Tenant isolation tests for all 6 CRM business tables (Epic 9, Phase 2).

Proves Company A's rows are invisible to Company B's queries, for every
CRM table, before any service logic is built on top. Uses the generic
``BaseRepository`` directly (per-table repositories are built in later
phases; ``BaseRepository``'s ``company_id``-scoped ``list()``/
``get_by_id_or_none()`` already gives full coverage here).

Task: T020 (tasks.md Phase 2).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.crm.models.activity import Activity
from modules.crm.models.audit import CrmAuditLog
from modules.crm.models.lead import Lead
from modules.crm.models.lead_source import LeadSource
from modules.crm.models.opportunity import Opportunity
from modules.crm.models.pipeline import Pipeline
from modules.crm.models.pipeline_stage import PipelineStage


class TestLeadSourceTenantIsolation:
    def test_list_scoped_to_company(self, db_session: Session) -> None:
        repo = BaseRepository(db_session, LeadSource)
        company_a, company_b = uuid.uuid4(), uuid.uuid4()
        repo.create(LeadSource(company_id=company_a, code="WEBSITE", name="Website"))

        items_a, total_a = repo.list(company_id=company_a)
        items_b, total_b = repo.list(company_id=company_b)

        assert total_a == 1
        assert total_b == 0
        assert items_b == []


class TestLeadTenantIsolation:
    def test_list_scoped_to_company(self, db_session: Session) -> None:
        repo = BaseRepository(db_session, Lead)
        company_a, company_b = uuid.uuid4(), uuid.uuid4()
        repo.create(
            Lead(company_id=company_a, first_name="Jane", email="jane@example.com")
        )

        items_a, total_a = repo.list(company_id=company_a)
        items_b, total_b = repo.list(company_id=company_b)

        assert total_a == 1
        assert total_b == 0
        assert items_b == []

    def test_get_by_id_does_not_cross_company(self, db_session: Session) -> None:
        repo = BaseRepository(db_session, Lead)
        company_a, company_b = uuid.uuid4(), uuid.uuid4()
        lead = repo.create(
            Lead(company_id=company_a, first_name="Jane", email="jane@example.com")
        )

        assert repo.get_by_id_or_none(id=lead.id, company_id=company_a) is not None
        assert repo.get_by_id_or_none(id=lead.id, company_id=company_b) is None


class TestPipelineTenantIsolation:
    def test_list_scoped_to_company(self, db_session: Session) -> None:
        repo = BaseRepository(db_session, Pipeline)
        company_a, company_b = uuid.uuid4(), uuid.uuid4()
        repo.create(Pipeline(company_id=company_a, name="Standard", is_default=True))

        items_a, total_a = repo.list(company_id=company_a)
        items_b, total_b = repo.list(company_id=company_b)

        assert total_a == 1
        assert total_b == 0
        assert items_b == []

    def test_each_company_may_have_its_own_default_pipeline(
        self, db_session: Session
    ) -> None:
        """BR-008 scopes 'one default pipeline' per company, not globally."""
        repo = BaseRepository(db_session, Pipeline)
        company_a, company_b = uuid.uuid4(), uuid.uuid4()

        repo.create(Pipeline(company_id=company_a, name="A Default", is_default=True))
        repo.create(Pipeline(company_id=company_b, name="B Default", is_default=True))

        _, total_a = repo.list(company_id=company_a)
        _, total_b = repo.list(company_id=company_b)
        assert total_a == 1
        assert total_b == 1


class TestPipelineStageTenantIsolation:
    def test_list_scoped_to_company(self, db_session: Session) -> None:
        pipeline_repo = BaseRepository(db_session, Pipeline)
        stage_repo = BaseRepository(db_session, PipelineStage)
        company_a, company_b = uuid.uuid4(), uuid.uuid4()
        pipeline = pipeline_repo.create(Pipeline(company_id=company_a, name="Std"))
        stage_repo.create(
            PipelineStage(
                company_id=company_a,
                pipeline_id=pipeline.id,
                name="Qualification",
                sequence=1,
                probability=20,
            )
        )

        items_a, total_a = stage_repo.list(company_id=company_a)
        items_b, total_b = stage_repo.list(company_id=company_b)

        assert total_a == 1
        assert total_b == 0
        assert items_b == []


class TestOpportunityTenantIsolation:
    def test_list_scoped_to_company(self, db_session: Session) -> None:
        pipeline_repo = BaseRepository(db_session, Pipeline)
        stage_repo = BaseRepository(db_session, PipelineStage)
        opp_repo = BaseRepository(db_session, Opportunity)
        company_a, company_b = uuid.uuid4(), uuid.uuid4()
        pipeline = pipeline_repo.create(Pipeline(company_id=company_a, name="Std"))
        stage = stage_repo.create(
            PipelineStage(
                company_id=company_a,
                pipeline_id=pipeline.id,
                name="Qualification",
                sequence=1,
                probability=20,
            )
        )
        opp_repo.create(
            Opportunity(
                company_id=company_a,
                name="Acme Deal",
                customer_id=str(uuid.uuid4()),
                owner_id=str(uuid.uuid4()),
                pipeline_id=pipeline.id,
                stage_id=stage.id,
                currency_code="USD",
                probability=20,
            )
        )

        items_a, total_a = opp_repo.list(company_id=company_a)
        items_b, total_b = opp_repo.list(company_id=company_b)

        assert total_a == 1
        assert total_b == 0
        assert items_b == []


class TestActivityTenantIsolation:
    def test_list_scoped_to_company(self, db_session: Session) -> None:
        repo = BaseRepository(db_session, Activity)
        company_a, company_b = uuid.uuid4(), uuid.uuid4()
        repo.create(
            Activity(
                company_id=company_a,
                activity_type="CALL",
                subject="Intro call",
                assigned_to=str(uuid.uuid4()),
                customer_id=str(uuid.uuid4()),
            )
        )

        items_a, total_a = repo.list(company_id=company_a)
        items_b, total_b = repo.list(company_id=company_b)

        assert total_a == 1
        assert total_b == 0
        assert items_b == []


class TestCrmAuditLogTenantIsolation:
    def test_list_scoped_to_company(self, db_session: Session) -> None:
        repo = BaseRepository(db_session, CrmAuditLog)
        company_a, company_b = uuid.uuid4(), uuid.uuid4()
        repo.create(
            CrmAuditLog(
                company_id=company_a,
                entity_type="LEAD",
                entity_id=uuid.uuid4(),
                action="CREATED",
            )
        )

        items_a, total_a = repo.list(company_id=company_a)
        items_b, total_b = repo.list(company_id=company_b)

        assert total_a == 1
        assert total_b == 0
        assert items_b == []

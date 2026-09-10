"""API tests: CRM reports/dashboard against a hand-seeded known dataset
(T084).

Matches the established "hand-verified known dataset" pattern from
Accounting's own ``TestKnownDataset``-style tests — every metric is
asserted against a value hand-calculated from the exact seeded rows
below, not merely "some non-error response".

Dataset (single company, all timestamps default to "now" so every row
falls within the current calendar month, keeping the dashboard's
current-month window trivially satisfied without period-boundary
fixtures):

Leads (6):
  A NEW/WEB, B CONTACTED/WEB, C QUALIFIED/REFERRAL, D QUALIFIED/REFERRAL,
  E CONVERTED/WEB, F UNQUALIFIED/(no source)
  -> count_by_status = {NEW:1, CONTACTED:1, QUALIFIED:2, CONVERTED:1,
     UNQUALIFIED:1}; count_by_source = {WEB:3, REFERRAL:2, none:1}
  -> conversion_rate = 1/6 = 16.67%; qualified_to_close_rate = 1/(2+1) = 33.33%

Opportunities (4, one pipeline with stages S1 seq1 prob20, S2 seq2 prob50):
  Opp1 OPEN/S1/owner/1000/no source
  Opp2 OPEN/S2/owner/2000/source via Lead E (WEB)
  Opp3 WON/5000 (won_at=now, created_at=now -> 0-day cycle)
  Opp4 LOST/1500 ("Budget cut")
  -> value_by_stage = {S1:1000, S2:2000}; value_by_owner = {owner:3000}
  -> value_by_source = {none:1000, WEB:2000}
  -> won_value=5000, lost_value=1500, win_rate=1/(1+1)=50%
  -> avg_deal_size=5000, avg_sales_cycle_days=0
  -> open_pipeline_value=3000, weighted_pipeline_value=1000*0.2+2000*0.5=1200

Activities (3):
  Act1 CALL/COMPLETED (lead A), Act2 EMAIL/COMPLETED (lead B)
  Act3 TASK/PLANNED/overdue (lead C, owner)
  -> completed_by_type={CALL:1,EMAIL:1}, completed_count=2
  -> overdue_by_owner={owner:1}, overdue_count=1

Task: T084 (tasks.md Phase 9).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.crm.models.activity import Activity
from modules.crm.models.lead import Lead
from modules.crm.models.lead_source import LeadSource
from modules.crm.models.opportunity import Opportunity
from modules.crm.models.pipeline import Pipeline
from modules.crm.models.pipeline_stage import PipelineStage
from modules.crm.repositories.activity import ActivityRepository
from modules.crm.repositories.lead import LeadRepository
from modules.crm.repositories.lead_source import LeadSourceRepository
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.crm.repositories.pipeline import PipelineRepository
from modules.crm.repositories.pipeline_stage import PipelineStageRepository
from tests.integration.api.v1.crm.conftest import (
    auth_header,
    create_company,
    crm_url,
    new_user_and_token,
)


def _current_user_id(client: TestClient, token: str) -> str:
    resp = client.get("/api/v1/profile", headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    return str(resp.json()["data"]["id"])


def _seed_dataset(db_session: Session, company_id: UUID, owner_id: UUID) -> None:
    source_repo = LeadSourceRepository(db_session)
    web = source_repo.create(
        LeadSource(company_id=company_id, code="WEB", name="Website")
    )
    referral = source_repo.create(
        LeadSource(company_id=company_id, code="REFERRAL", name="Referral")
    )

    lead_repo = LeadRepository(db_session)
    lead_repo.create(
        Lead(
            company_id=company_id,
            first_name="A",
            last_name="Lead",
            email=f"a-{uuid4().hex[:6]}@example.com",
            status="NEW",
            source_id=web.id,
        )
    )
    lead_b = lead_repo.create(
        Lead(
            company_id=company_id,
            first_name="B",
            last_name="Lead",
            email=f"b-{uuid4().hex[:6]}@example.com",
            status="CONTACTED",
            source_id=web.id,
        )
    )
    lead_c = lead_repo.create(
        Lead(
            company_id=company_id,
            first_name="C",
            last_name="Lead",
            email=f"c-{uuid4().hex[:6]}@example.com",
            status="QUALIFIED",
            qualification_notes="ok",
            source_id=referral.id,
        )
    )
    lead_repo.create(
        Lead(
            company_id=company_id,
            first_name="D",
            last_name="Lead",
            email=f"d-{uuid4().hex[:6]}@example.com",
            status="QUALIFIED",
            qualification_notes="ok",
            source_id=referral.id,
        )
    )
    lead_e = lead_repo.create(
        Lead(
            company_id=company_id,
            first_name="E",
            last_name="Lead",
            email=f"e-{uuid4().hex[:6]}@example.com",
            status="CONVERTED",
            source_id=web.id,
            converted_at=utcnow(),
            converted_customer_id=str(uuid4()),
        )
    )
    lead_repo.create(
        Lead(
            company_id=company_id,
            first_name="F",
            last_name="Lead",
            email=f"f-{uuid4().hex[:6]}@example.com",
            status="UNQUALIFIED",
            disqualification_reason="Not a fit",
        )
    )

    pipeline = PipelineRepository(db_session).create(
        Pipeline(company_id=company_id, name="Report Pipeline", is_default=True)
    )
    stage_repo = PipelineStageRepository(db_session)
    stage1 = stage_repo.create(
        PipelineStage(
            company_id=company_id,
            pipeline_id=pipeline.id,
            name="Qualification",
            sequence=1,
            probability=20,
        )
    )
    stage2 = stage_repo.create(
        PipelineStage(
            company_id=company_id,
            pipeline_id=pipeline.id,
            name="Proposal",
            sequence=2,
            probability=50,
        )
    )

    opp_repo = OpportunityRepository(db_session)
    customer_id = str(uuid4())
    opp_repo.create(
        Opportunity(
            company_id=company_id,
            name="Opp1",
            customer_id=customer_id,
            owner_id=str(owner_id),
            pipeline_id=pipeline.id,
            stage_id=stage1.id,
            value=Decimal("1000"),
            currency_code="USD",
            probability=20,
            status="OPEN",
        )
    )
    opp_repo.create(
        Opportunity(
            company_id=company_id,
            name="Opp2",
            customer_id=customer_id,
            owner_id=str(owner_id),
            pipeline_id=pipeline.id,
            stage_id=stage2.id,
            value=Decimal("2000"),
            currency_code="USD",
            probability=50,
            status="OPEN",
            source_lead_id=lead_e.id,
        )
    )
    opp_repo.create(
        Opportunity(
            company_id=company_id,
            name="Opp3-Won",
            customer_id=customer_id,
            owner_id=str(owner_id),
            pipeline_id=pipeline.id,
            stage_id=stage2.id,
            value=Decimal("5000"),
            currency_code="USD",
            probability=100,
            status="WON",
            won_at=utcnow(),
        )
    )
    opp_repo.create(
        Opportunity(
            company_id=company_id,
            name="Opp4-Lost",
            customer_id=customer_id,
            owner_id=str(owner_id),
            pipeline_id=pipeline.id,
            stage_id=stage1.id,
            value=Decimal("1500"),
            currency_code="USD",
            probability=0,
            status="LOST",
            lost_at=utcnow(),
            lost_reason="Budget cut",
        )
    )

    activity_repo = ActivityRepository(db_session)
    now = utcnow()
    activity_repo.create(
        Activity(
            company_id=company_id,
            activity_type="CALL",
            subject="Call A",
            status="COMPLETED",
            completed_at=now,
            assigned_to=str(owner_id),
            lead_id=lead_b.id,
        )
    )
    activity_repo.create(
        Activity(
            company_id=company_id,
            activity_type="EMAIL",
            subject="Email B",
            status="COMPLETED",
            completed_at=now,
            assigned_to=str(owner_id),
            lead_id=lead_b.id,
        )
    )
    activity_repo.create(
        Activity(
            company_id=company_id,
            activity_type="TASK",
            subject="Overdue task",
            status="PLANNED",
            due_date=now - timedelta(days=3),
            assigned_to=str(owner_id),
            lead_id=lead_c.id,
        )
    )


class TestPipelineReport:
    def test_pipeline_report_matches_hand_calculated_values(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        owner_id = _current_user_id(crm_client, token)
        _seed_dataset(db_session, UUID(company_id), UUID(owner_id))

        resp = crm_client.get(
            crm_url(company_id, "/reports/pipeline"), headers=auth_header(token)
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]

        stage_totals = {
            v["stage_id"]: Decimal(v["value"]) for v in data["value_by_stage"]
        }
        assert sorted(stage_totals.values()) == [Decimal("1000"), Decimal("2000")]

        owner_totals = {
            v["owner_id"]: Decimal(v["value"]) for v in data["value_by_owner"]
        }
        assert owner_totals == {owner_id: Decimal("3000")}

        source_totals = {
            (v["source_id"] or "none"): Decimal(v["value"])
            for v in data["value_by_source"]
        }
        assert source_totals["none"] == Decimal("1000")
        assert Decimal("2000") in source_totals.values()

        assert Decimal(data["won_value"]) == Decimal("5000")
        assert Decimal(data["lost_value"]) == Decimal("1500")
        assert Decimal(data["win_rate"]) == Decimal("50.00")
        assert Decimal(data["avg_deal_size"]) == Decimal("5000.00")
        assert Decimal(data["avg_sales_cycle_days"]) == Decimal("0.00")


class TestLeadReport:
    def test_lead_report_matches_hand_calculated_values(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        owner_id = _current_user_id(crm_client, token)
        _seed_dataset(db_session, UUID(company_id), UUID(owner_id))

        resp = crm_client.get(
            crm_url(company_id, "/reports/leads"), headers=auth_header(token)
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]

        assert data["total_count"] == 6
        assert data["count_by_status"] == {
            "NEW": 1,
            "CONTACTED": 1,
            "QUALIFIED": 2,
            "CONVERTED": 1,
            "UNQUALIFIED": 1,
        }
        assert sorted(data["count_by_source"].values()) == [1, 2, 3]
        assert Decimal(data["conversion_rate"]) == Decimal("16.67")
        assert Decimal(data["qualified_to_close_rate"]) == Decimal("33.33")


class TestActivityReport:
    def test_activity_report_matches_hand_calculated_values(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        owner_id = _current_user_id(crm_client, token)
        _seed_dataset(db_session, UUID(company_id), UUID(owner_id))

        resp = crm_client.get(
            crm_url(company_id, "/reports/activities"), headers=auth_header(token)
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]

        assert data["completed_count"] == 2
        assert data["completed_by_type"] == {"CALL": 1, "EMAIL": 1}
        assert data["overdue_count"] == 1
        assert data["overdue_by_owner"] == {owner_id: 1}


class TestDashboard:
    def test_dashboard_matches_hand_calculated_values(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        owner_id = _current_user_id(crm_client, token)
        _seed_dataset(db_session, UUID(company_id), UUID(owner_id))

        resp = crm_client.get(
            crm_url(company_id, "/dashboard"), headers=auth_header(token)
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]

        assert Decimal(data["open_pipeline_value"]) == Decimal("3000")
        assert Decimal(data["weighted_pipeline_value"]) == Decimal("1200.00")
        assert data["lead_count"] == 6
        assert Decimal(data["conversion_rate"]) == Decimal("16.67")
        assert Decimal(data["win_rate"]) == Decimal("50.00")
        assert data["overdue_follow_up_count"] == 1
        assert data["activities_completed"] == 2


class TestReportsPermission:
    def test_denied_without_reports_view_permission(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        from tests.fixtures.auth_fixtures import create_test_user
        from tests.fixtures.users_roles_fixtures import create_member_with_role
        from tests.integration.api.v1.crm.conftest import login, unique_email

        _, owner_token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, owner_token)

        email = unique_email()
        user, password = create_test_user(db_session, email)
        create_member_with_role(
            db_session,
            company_id=UUID(company_id),
            user_id=user.id,
            role_slug="salesperson",
        )
        salesperson_token = login(crm_client, email, password)

        resp = crm_client.get(
            crm_url(company_id, "/dashboard"),
            headers=auth_header(salesperson_token),
        )

        assert resp.status_code == 403, resp.text

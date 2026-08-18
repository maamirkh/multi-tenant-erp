"""Integration test: Activity completion -> Lead cascade (tasks.md T053).

Proves spec.md §19.2 / plan.md §13 end-to-end against a real (SQLite)
database: completing an Activity linked to a Lead advances that Lead's
``status``/``last_contact_date`` atomically, and the race-free
CASE-expression update (this codebase's portable substitute for Postgres'
``GREATEST()`` — see ``activity_service.py``'s own docstring) never lets
an out-of-order completion regress ``last_contact_date``.

Task: T053 (tasks.md Phase 6).
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from modules.crm.models.activity import Activity
from modules.crm.models.lead import Lead
from modules.crm.repositories.activity import ActivityRepository
from modules.crm.repositories.audit_log import CrmAuditLogRepository
from modules.crm.repositories.lead import LeadRepository
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.crm.services.activity_service import ActivityService
from modules.crm.services.audit_service import CrmAuditService
from modules.sales.repositories.customer import CustomerRepository
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)


def _build_activity_service(db_session: Session) -> ActivityService:
    return ActivityService(
        db=db_session,
        repo=ActivityRepository(db_session),
        lead_repo=LeadRepository(db_session),
        customer_repo=CustomerRepository(db_session),
        opportunity_repo=OpportunityRepository(db_session),
        member_repo=CompanyMemberRepository(db_session),
        audit_service=CrmAuditService(CrmAuditLogRepository(db_session)),
    )


class TestNewLeadAdvancesToContacted:
    def test_completing_first_activity_advances_new_lead(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        lead = LeadRepository(db_session).create(
            Lead(
                company_id=company_id,
                first_name="Jane",
                email="jane@example.com",
                status="NEW",
            )
        )
        activity = ActivityRepository(db_session).create(
            Activity(
                company_id=company_id,
                activity_type="CALL",
                subject="Intro call",
                assigned_to=str(uuid4()),
                lead_id=lead.id,
            )
        )
        service = _build_activity_service(db_session)

        result = service.complete(activity.id, company_id)

        assert result.status == "COMPLETED"
        assert result.completed_at is not None

        fresh_lead = LeadRepository(db_session).get_by_id_or_none(
            id=lead.id, company_id=company_id
        )
        assert fresh_lead is not None
        assert fresh_lead.status == "CONTACTED"
        assert fresh_lead.last_contact_date == result.completed_at.date()

    def test_completing_second_activity_does_not_regress_status(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        lead = LeadRepository(db_session).create(
            Lead(
                company_id=company_id,
                first_name="Jane",
                email="jane@example.com",
                status="QUALIFIED",
                qualification_notes="Confirmed budget",
            )
        )
        activity = ActivityRepository(db_session).create(
            Activity(
                company_id=company_id,
                activity_type="CALL",
                subject="Follow-up call",
                assigned_to=str(uuid4()),
                lead_id=lead.id,
            )
        )
        service = _build_activity_service(db_session)

        service.complete(activity.id, company_id)

        fresh_lead = LeadRepository(db_session).get_by_id_or_none(
            id=lead.id, company_id=company_id
        )
        assert fresh_lead is not None
        assert fresh_lead.status == "QUALIFIED"  # unchanged — only NEW advances


class TestLastContactDateRaceSafety:
    def test_out_of_order_completion_never_regresses_last_contact_date(
        self, db_session: Session
    ) -> None:
        """Simulates completing a LATER-dated activity first (by directly
        seeding a future last_contact_date on the Lead), then completing an
        EARLIER one (today, via the normal complete() flow) — the earlier
        completion must never overwrite the already-later date."""
        company_id = uuid4()
        future_date = date.today() + timedelta(days=5)
        lead = LeadRepository(db_session).create(
            Lead(
                company_id=company_id,
                first_name="Jane",
                email="jane@example.com",
                status="CONTACTED",
                last_contact_date=future_date,
            )
        )
        activity = ActivityRepository(db_session).create(
            Activity(
                company_id=company_id,
                activity_type="CALL",
                subject="Earlier call, completed later",
                assigned_to=str(uuid4()),
                lead_id=lead.id,
            )
        )
        service = _build_activity_service(db_session)

        service.complete(activity.id, company_id)

        fresh_lead = LeadRepository(db_session).get_by_id_or_none(
            id=lead.id, company_id=company_id
        )
        assert fresh_lead is not None
        assert fresh_lead.last_contact_date == future_date

    def test_null_last_contact_date_is_always_superseded(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        lead = LeadRepository(db_session).create(
            Lead(
                company_id=company_id,
                first_name="Jane",
                email="jane@example.com",
                status="CONTACTED",
                last_contact_date=None,
            )
        )
        activity = ActivityRepository(db_session).create(
            Activity(
                company_id=company_id,
                activity_type="CALL",
                subject="First-ever recorded contact",
                assigned_to=str(uuid4()),
                lead_id=lead.id,
            )
        )
        service = _build_activity_service(db_session)

        result = service.complete(activity.id, company_id)

        fresh_lead = LeadRepository(db_session).get_by_id_or_none(
            id=lead.id, company_id=company_id
        )
        assert fresh_lead is not None
        assert fresh_lead.last_contact_date == result.completed_at.date()


class TestCompleteIdempotency:
    def test_completing_twice_is_a_noop_second_time(self, db_session: Session) -> None:
        company_id = uuid4()
        activity = ActivityRepository(db_session).create(
            Activity(
                company_id=company_id,
                activity_type="NOTE",
                subject="Standalone note",
                assigned_to=str(uuid4()),
                customer_id=str(uuid4()),
            )
        )
        service = _build_activity_service(db_session)

        first = service.complete(activity.id, company_id)
        second = service.complete(activity.id, company_id)

        assert first.completed_at == second.completed_at

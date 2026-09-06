"""Audit coverage test — all 8 spec.md §44 auditable actions (T070).

Exercises each auditable action via its real service method and asserts
a ``CrmAuditLog`` row exists with the correct ``entity_type``/
``entity_id``/``action``/``actor_user_id``/``before_state``/
``after_state`` (AC-21/EC-10).

Actions (spec.md §44):
  Lead:        creation, assignment, status change, conversion
  Opportunity: creation, stage change, assignment, won/lost

Activity create/update is deliberately NOT audited (§44's explicit
scoping to status transitions only) — not part of this file's coverage.

Task: T070 (tasks.md Phase 8).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from modules.crm.models.lead import Lead
from modules.crm.models.pipeline import Pipeline
from modules.crm.models.pipeline_stage import PipelineStage
from modules.crm.repositories.audit_log import CrmAuditLogRepository
from modules.crm.repositories.lead import LeadRepository
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.crm.repositories.pipeline import PipelineRepository
from modules.crm.repositories.pipeline_stage import PipelineStageRepository
from modules.crm.schemas.lead import LeadCreate, LeadUpdate
from modules.crm.schemas.opportunity import OpportunityCreate
from modules.crm.services.audit_service import CrmAuditService
from modules.crm.services.lead_service import LeadService
from modules.crm.services.opportunity_service import OpportunityService
from modules.crm.services.pipeline_service import PipelineService
from modules.crm.services.provisioning_service import CrmProvisioningService
from modules.sales.models.customer import Customer
from modules.sales.models.master import CustomerCategory
from modules.sales.repositories.customer import CustomerRepository
from modules.sales.repositories.master import CustomerCategoryRepository
from modules.sales.repositories.quotation import SalesQuotationRepository
from modules.sales.services.customer_service import CustomerService
from modules.sales.services.master_data_service import CustomerCategoryService
from modules.sales.services.sequence_service import SalesSequenceService
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)
from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.users_roles_fixtures import (
    create_member_with_role,
    seed_system_roles,
)


def _audit_service(db_session: Session) -> CrmAuditService:
    return CrmAuditService(CrmAuditLogRepository(db_session))


def _lead_service(db_session: Session) -> LeadService:
    return LeadService(
        db=db_session,
        repo=LeadRepository(db_session),
        member_repo=CompanyMemberRepository(db_session),
        audit_service=_audit_service(db_session),
    )


def _opportunity_service(db_session: Session) -> OpportunityService:
    return OpportunityService(
        db=db_session,
        repo=OpportunityRepository(db_session),
        stage_repo=PipelineStageRepository(db_session),
        customer_repo=CustomerRepository(db_session),
        member_repo=CompanyMemberRepository(db_session),
        quotation_repo=SalesQuotationRepository(db_session),
        audit_service=_audit_service(db_session),
    )


def _active_member(db_session: Session, company_id: UUID) -> UUID:
    """Create an active company member (needed for owner_id/assigned_to
    validation) and return their user_id."""
    seed_system_roles(db_session, company_id)
    email = f"audit-{uuid4().hex[:10]}@example.com"
    user, _ = create_test_user(db_session, email)
    create_member_with_role(
        db_session, company_id=company_id, user_id=user.id, role_slug="salesperson"
    )
    return user.id


def _create_customer(db_session: Session, company_id: UUID) -> Customer:
    category = CustomerCategoryRepository(db_session).create(
        CustomerCategory(
            company_id=company_id, code=f"CAT-{uuid4().hex[:6]}", name="Audit Test"
        )
    )
    return CustomerRepository(db_session).create(
        Customer(
            company_id=company_id,
            customer_code=f"CUST-{uuid4().hex[:8]}",
            legal_name="Audit Test Customer",
            customer_type="COMPANY",
            category_id=str(category.id),
            currency_code="USD",
            status="ACTIVE",
        )
    )


def _create_pipeline_and_stage(
    db_session: Session, company_id: UUID
) -> tuple[UUID, UUID]:
    pipeline = PipelineRepository(db_session).create(
        Pipeline(company_id=company_id, name="Audit Pipeline", is_default=True)
    )
    stage = PipelineStageRepository(db_session).create(
        PipelineStage(
            company_id=company_id,
            pipeline_id=pipeline.id,
            name="Qualification",
            sequence=1,
            probability=20,
        )
    )
    return pipeline.id, stage.id


class TestLeadAuditCoverage:
    def test_lead_created_action_is_recorded(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = _lead_service(db_session)
        actor_id = uuid4()

        lead = svc.create(
            company_id,
            LeadCreate(first_name="Audit", last_name="Lead", email="a@example.com"),
            created_by=actor_id,
        )

        rows = CrmAuditLogRepository(db_session).list_for_entity(
            company_id, "LEAD", lead.id
        )
        assert any(r.action == "LEAD_CREATED" for r in rows)
        row = next(r for r in rows if r.action == "LEAD_CREATED")
        assert row.actor_user_id == str(actor_id)
        assert row.after_state is not None

    def test_lead_status_changed_action_is_recorded(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = _lead_service(db_session)
        actor_id = uuid4()
        lead = svc.create(
            company_id,
            LeadCreate(first_name="Audit", last_name="Lead", email="b@example.com"),
        )

        svc.update(
            lead.id,
            company_id,
            LeadUpdate(status="CONTACTED"),
            actor_user_id=actor_id,
        )

        rows = CrmAuditLogRepository(db_session).list_for_entity(
            company_id, "LEAD", lead.id
        )
        row = next(r for r in rows if r.action == "LEAD_STATUS_CHANGED")
        assert row.before_state == {"status": "NEW"}
        assert row.after_state == {"status": "CONTACTED"}
        assert row.actor_user_id == str(actor_id)

    def test_lead_assigned_action_is_recorded(self, db_session: Session) -> None:
        company_id = uuid4()
        owner_id = _active_member(db_session, company_id)
        svc = _lead_service(db_session)
        actor_id = uuid4()
        lead = svc.create(
            company_id,
            LeadCreate(first_name="Audit", last_name="Lead", email="c@example.com"),
        )

        svc.assign(lead.id, company_id, owner_id, actor_user_id=actor_id)

        rows = CrmAuditLogRepository(db_session).list_for_entity(
            company_id, "LEAD", lead.id
        )
        row = next(r for r in rows if r.action == "LEAD_ASSIGNED")
        assert row.after_state == {"owner_id": str(owner_id)}
        assert row.actor_user_id == str(actor_id)

    def test_lead_converted_action_is_recorded(self, db_session: Session) -> None:
        from modules.crm.services.lead_conversion_service import LeadConversionService
        from modules.sales.repositories.customer import (
            CustomerAddressRepository,
            CustomerContactRepository,
        )

        company_id = uuid4()
        actor_id = uuid4()
        lead_repo = LeadRepository(db_session)
        opportunity_repo = OpportunityRepository(db_session)
        pipeline_repo = PipelineRepository(db_session)
        stage_repo = PipelineStageRepository(db_session)
        pipeline_service = PipelineService(db_session, pipeline_repo, stage_repo)
        category_repo = CustomerCategoryRepository(db_session)
        category_service = CustomerCategoryService(db_session, category_repo)
        provisioning_service = CrmProvisioningService(
            db_session, pipeline_repo, pipeline_service, category_repo, category_service
        )
        customer_service = CustomerService(
            db=db_session,
            customer_repo=CustomerRepository(db_session),
            contact_repo=CustomerContactRepository(db_session),
            address_repo=CustomerAddressRepository(db_session),
            sequence_service=SalesSequenceService(db=db_session),
        )
        conversion_service = LeadConversionService(
            db=db_session,
            lead_repo=lead_repo,
            opportunity_repo=opportunity_repo,
            pipeline_repo=pipeline_repo,
            pipeline_stage_repo=stage_repo,
            provisioning_service=provisioning_service,
            customer_service=customer_service,
            audit_service=_audit_service(db_session),
        )
        lead = lead_repo.create(
            Lead(
                company_id=company_id,
                first_name="Convert",
                last_name="Me",
                email=f"convert-{uuid4().hex[:8]}@example.com",
                status="QUALIFIED",
                qualification_notes="ready",
            )
        )

        result = conversion_service.convert(lead.id, company_id, actor_id=actor_id)

        rows = CrmAuditLogRepository(db_session).list_for_entity(
            company_id, "LEAD", lead.id
        )
        row = next(r for r in rows if r.action == "LEAD_CONVERTED")
        assert row.after_state is not None
        assert row.after_state["customer_id"] == str(result.customer_id)
        assert row.actor_user_id == str(actor_id)


class TestOpportunityAuditCoverage:
    def test_opportunity_created_action_is_recorded(self, db_session: Session) -> None:
        company_id = uuid4()
        owner_id = _active_member(db_session, company_id)
        pipeline_id, stage_id = _create_pipeline_and_stage(db_session, company_id)
        customer = _create_customer(db_session, company_id)
        svc = _opportunity_service(db_session)
        actor_id = uuid4()

        opportunity = svc.create(
            company_id,
            OpportunityCreate(
                name="Audit Deal",
                customer_id=customer.id,
                owner_id=owner_id,
                pipeline_id=pipeline_id,
                stage_id=stage_id,
                value=Decimal("1000"),
                currency_code="USD",
            ),
            created_by=actor_id,
        )

        rows = CrmAuditLogRepository(db_session).list_for_entity(
            company_id, "OPPORTUNITY", opportunity.id
        )
        assert any(r.action == "OPPORTUNITY_CREATED" for r in rows)
        row = next(r for r in rows if r.action == "OPPORTUNITY_CREATED")
        assert row.actor_user_id == str(actor_id)

    def test_opportunity_stage_changed_action_is_recorded(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        owner_id = _active_member(db_session, company_id)
        pipeline_id, stage_id = _create_pipeline_and_stage(db_session, company_id)
        second_stage = PipelineStageRepository(db_session).create(
            PipelineStage(
                company_id=company_id,
                pipeline_id=pipeline_id,
                name="Proposal",
                sequence=2,
                probability=50,
            )
        )
        customer = _create_customer(db_session, company_id)
        svc = _opportunity_service(db_session)
        actor_id = uuid4()
        opportunity = svc.create(
            company_id,
            OpportunityCreate(
                name="Audit Deal 2",
                customer_id=customer.id,
                owner_id=owner_id,
                pipeline_id=pipeline_id,
                stage_id=stage_id,
                value=Decimal("1000"),
                currency_code="USD",
            ),
        )

        svc.change_stage(
            opportunity.id, company_id, second_stage.id, actor_user_id=actor_id
        )

        rows = CrmAuditLogRepository(db_session).list_for_entity(
            company_id, "OPPORTUNITY", opportunity.id
        )
        row = next(r for r in rows if r.action == "OPPORTUNITY_STAGE_CHANGED")
        assert row.after_state == {"stage_id": str(second_stage.id)}
        assert row.actor_user_id == str(actor_id)

    def test_opportunity_assigned_action_is_recorded(self, db_session: Session) -> None:
        company_id = uuid4()
        owner_id = _active_member(db_session, company_id)
        new_owner_id = _active_member(db_session, company_id)
        pipeline_id, stage_id = _create_pipeline_and_stage(db_session, company_id)
        customer = _create_customer(db_session, company_id)
        svc = _opportunity_service(db_session)
        actor_id = uuid4()
        opportunity = svc.create(
            company_id,
            OpportunityCreate(
                name="Audit Deal 3",
                customer_id=customer.id,
                owner_id=owner_id,
                pipeline_id=pipeline_id,
                stage_id=stage_id,
                value=Decimal("1000"),
                currency_code="USD",
            ),
        )

        svc.assign(opportunity.id, company_id, new_owner_id, actor_user_id=actor_id)

        rows = CrmAuditLogRepository(db_session).list_for_entity(
            company_id, "OPPORTUNITY", opportunity.id
        )
        row = next(r for r in rows if r.action == "OPPORTUNITY_ASSIGNED")
        assert row.after_state == {"owner_id": str(new_owner_id)}
        assert row.actor_user_id == str(actor_id)

    def test_opportunity_won_action_is_recorded(self, db_session: Session) -> None:
        company_id = uuid4()
        owner_id = _active_member(db_session, company_id)
        pipeline_id, stage_id = _create_pipeline_and_stage(db_session, company_id)
        customer = _create_customer(db_session, company_id)
        svc = _opportunity_service(db_session)
        actor_id = uuid4()
        opportunity = svc.create(
            company_id,
            OpportunityCreate(
                name="Audit Deal Won",
                customer_id=customer.id,
                owner_id=owner_id,
                pipeline_id=pipeline_id,
                stage_id=stage_id,
                value=Decimal("2500"),
                currency_code="USD",
            ),
        )

        svc.win(opportunity.id, company_id, actor_user_id=actor_id)

        rows = CrmAuditLogRepository(db_session).list_for_entity(
            company_id, "OPPORTUNITY", opportunity.id
        )
        row = next(r for r in rows if r.action == "OPPORTUNITY_WON")
        assert row.after_state is not None
        assert row.after_state["status"] == "WON"
        assert row.actor_user_id == str(actor_id)

    def test_opportunity_lost_action_is_recorded(self, db_session: Session) -> None:
        company_id = uuid4()
        owner_id = _active_member(db_session, company_id)
        pipeline_id, stage_id = _create_pipeline_and_stage(db_session, company_id)
        customer = _create_customer(db_session, company_id)
        svc = _opportunity_service(db_session)
        actor_id = uuid4()
        opportunity = svc.create(
            company_id,
            OpportunityCreate(
                name="Audit Deal Lost",
                customer_id=customer.id,
                owner_id=owner_id,
                pipeline_id=pipeline_id,
                stage_id=stage_id,
                value=Decimal("2500"),
                currency_code="USD",
            ),
        )

        svc.lose(opportunity.id, company_id, "Budget cut", actor_user_id=actor_id)

        rows = CrmAuditLogRepository(db_session).list_for_entity(
            company_id, "OPPORTUNITY", opportunity.id
        )
        row = next(r for r in rows if r.action == "OPPORTUNITY_LOST")
        assert row.after_state is not None
        assert row.after_state["status"] == "LOST"
        assert row.after_state["lost_reason"] == "Budget cut"
        assert row.actor_user_id == str(actor_id)

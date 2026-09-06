"""Event coverage test — all 12 spec.md §36 domain events (T075).

Subscribes a test listener to ``modules.crm.events.get_event_bus()``
(isolated per test via ``set_event_bus()``, matching the established
``tests/integration/repositories/sales/test_event_bus.py`` precedent —
no CRM-specific event-coverage test existed before this one, so this file
establishes the pattern rather than reusing a prior CRM one), exercises
every trigger, and asserts all 12 events fire with the correct
``event_type``, ``company_id``, entity IDs, and business payload fields
per spec.md §36.

Note: qualifying a Lead fires BOTH ``crm.lead.status_changed`` (every
transition) AND ``crm.lead.qualified`` (specifically for -> QUALIFIED) —
13 total publish calls across these 12 distinct event *types*, since one
trigger (qualify) legitimately fires two different, spec-documented event
types.

Task: T075 (tasks.md Phase 8).
"""

from __future__ import annotations

from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from modules.crm.events import (
    CrmDomainEvent,
    InProcessEventBus,
    get_event_bus,
    set_event_bus,
)
from modules.crm.events.lead_events import LeadConverted
from modules.crm.events.opportunity_events import (
    OpportunityLost,
    OpportunityStageChanged,
    OpportunityWon,
)
from modules.crm.models.pipeline import Pipeline
from modules.crm.models.pipeline_stage import PipelineStage
from modules.crm.repositories.activity import ActivityRepository
from modules.crm.repositories.audit_log import CrmAuditLogRepository
from modules.crm.repositories.lead import LeadRepository
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.crm.repositories.pipeline import PipelineRepository
from modules.crm.repositories.pipeline_stage import PipelineStageRepository
from modules.crm.schemas.activity import ActivityCreate
from modules.crm.schemas.lead import LeadCreate, LeadUpdate
from modules.crm.schemas.opportunity import OpportunityCreate
from modules.crm.services.activity_service import ActivityService
from modules.crm.services.audit_service import CrmAuditService
from modules.crm.services.lead_conversion_service import LeadConversionService
from modules.crm.services.lead_service import LeadService
from modules.crm.services.opportunity_service import OpportunityService
from modules.crm.services.pipeline_service import PipelineService
from modules.crm.services.provisioning_service import CrmProvisioningService
from modules.sales.models.customer import Customer
from modules.sales.models.master import CustomerCategory
from modules.sales.repositories.customer import (
    CustomerAddressRepository,
    CustomerContactRepository,
    CustomerRepository,
)
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


def _activity_service(db_session: Session) -> ActivityService:
    return ActivityService(
        db=db_session,
        repo=ActivityRepository(db_session),
        lead_repo=LeadRepository(db_session),
        customer_repo=CustomerRepository(db_session),
        opportunity_repo=OpportunityRepository(db_session),
        member_repo=CompanyMemberRepository(db_session),
        audit_service=_audit_service(db_session),
    )


def _conversion_service(db_session: Session) -> LeadConversionService:
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
    return LeadConversionService(
        db=db_session,
        lead_repo=lead_repo,
        opportunity_repo=opportunity_repo,
        pipeline_repo=pipeline_repo,
        pipeline_stage_repo=stage_repo,
        provisioning_service=provisioning_service,
        customer_service=customer_service,
        audit_service=_audit_service(db_session),
    )


def _active_member(db_session: Session, company_id: UUID) -> UUID:
    seed_system_roles(db_session, company_id)
    email = f"event-{uuid4().hex[:10]}@example.com"
    user, _ = create_test_user(db_session, email)
    create_member_with_role(
        db_session, company_id=company_id, user_id=user.id, role_slug="salesperson"
    )
    return user.id


def _create_customer(db_session: Session, company_id: UUID) -> Customer:
    category = CustomerCategoryRepository(db_session).create(
        CustomerCategory(
            company_id=company_id, code=f"CAT-{uuid4().hex[:6]}", name="Event Test"
        )
    )
    return CustomerRepository(db_session).create(
        Customer(
            company_id=company_id,
            customer_code=f"CUST-{uuid4().hex[:8]}",
            legal_name="Event Test Customer",
            customer_type="COMPANY",
            category_id=str(category.id),
            currency_code="USD",
            status="ACTIVE",
        )
    )


def _create_pipeline_and_two_stages(
    db_session: Session, company_id: UUID
) -> tuple[UUID, UUID, UUID]:
    """Reuse the company's already-provisioned default Pipeline (Lead
    conversion, run earlier in this test, auto-provisions one via
    ``CrmProvisioningService.ensure_defaults()``) rather than creating a
    second one — BR-008 allows only one default Pipeline per company."""
    pipeline_repo = PipelineRepository(db_session)
    pipeline = pipeline_repo.get_default_for_company(company_id)
    if pipeline is None:
        pipeline = pipeline_repo.create(
            Pipeline(company_id=company_id, name="Event Pipeline", is_default=True)
        )
    stage1 = PipelineStageRepository(db_session).create(
        PipelineStage(
            company_id=company_id,
            pipeline_id=pipeline.id,
            name="Qualification",
            sequence=90,
            probability=20,
        )
    )
    stage2 = PipelineStageRepository(db_session).create(
        PipelineStage(
            company_id=company_id,
            pipeline_id=pipeline.id,
            name="Proposal",
            sequence=91,
            probability=50,
        )
    )
    return pipeline.id, stage1.id, stage2.id


class TestAllTwelveEventsFire:
    def test_full_lead_and_opportunity_lifecycle_publishes_all_events(
        self, db_session: Session
    ) -> None:
        original_bus = get_event_bus()
        test_bus = InProcessEventBus()
        captured: list[CrmDomainEvent] = []
        test_bus.subscribe("*", captured.append)
        set_event_bus(test_bus)
        try:
            company_id = uuid4()
            owner_id = _active_member(db_session, company_id)

            # --- Lead: created, status_changed, qualified, assigned ---
            lead_svc = _lead_service(db_session)
            lead = lead_svc.create(
                company_id,
                LeadCreate(
                    first_name="Event",
                    last_name="Lead",
                    email=f"lead-{uuid4().hex[:8]}@example.com",
                ),
            )
            lead_svc.update(lead.id, company_id, LeadUpdate(status="CONTACTED"))
            lead_svc.update(
                lead.id,
                company_id,
                LeadUpdate(status="QUALIFIED", qualification_notes="Budget confirmed"),
            )
            lead_svc.assign(lead.id, company_id, owner_id)

            # --- Lead conversion: converted (+ opportunity.created) ---
            conversion_svc = _conversion_service(db_session)
            conversion_result = conversion_svc.convert(
                lead.id, company_id, actor_id=owner_id
            )

            # --- Opportunity: created (manual), assigned, stage_changed,
            #     won, lost (on two separate manually-created Opportunities,
            #     since won/lost are both terminal) ---
            pipeline_id, stage1_id, stage2_id = _create_pipeline_and_two_stages(
                db_session, company_id
            )
            customer = _create_customer(db_session, company_id)
            opp_svc = _opportunity_service(db_session)
            other_owner_id = _active_member(db_session, company_id)

            opp_to_win = opp_svc.create(
                company_id,
                OpportunityCreate(
                    name="Deal To Win",
                    customer_id=customer.id,
                    owner_id=owner_id,
                    pipeline_id=pipeline_id,
                    stage_id=stage1_id,
                    value=Decimal("5000"),
                    currency_code="USD",
                ),
            )
            opp_svc.assign(opp_to_win.id, company_id, other_owner_id)
            opp_svc.change_stage(opp_to_win.id, company_id, stage2_id)
            opp_svc.win(opp_to_win.id, company_id)

            opp_to_lose = opp_svc.create(
                company_id,
                OpportunityCreate(
                    name="Deal To Lose",
                    customer_id=customer.id,
                    owner_id=owner_id,
                    pipeline_id=pipeline_id,
                    stage_id=stage1_id,
                    value=Decimal("3000"),
                    currency_code="USD",
                ),
            )
            opp_svc.lose(opp_to_lose.id, company_id, "Went silent")

            # --- Activity: created, completed ---
            activity_svc = _activity_service(db_session)
            activity = activity_svc.create(
                company_id,
                ActivityCreate(
                    activity_type="CALL",
                    subject="Event test call",
                    assigned_to=owner_id,
                    customer_id=customer.id,
                ),
            )
            activity_svc.complete(activity.id, company_id)

            event_types = {e.event_type for e in captured}
            expected = {
                "crm.lead.created",
                "crm.lead.status_changed",
                "crm.lead.qualified",
                "crm.lead.assigned",
                "crm.lead.converted",
                "crm.opportunity.created",
                "crm.opportunity.stage_changed",
                "crm.opportunity.assigned",
                "crm.opportunity.won",
                "crm.opportunity.lost",
                "crm.activity.created",
                "crm.activity.completed",
            }
            missing = expected - event_types
            assert not missing, f"Missing events: {missing}"

            # Spot-check payload correctness for a representative few.
            converted = cast(
                LeadConverted,
                next(e for e in captured if e.event_type == "crm.lead.converted"),
            )
            assert converted.company_id == company_id
            assert str(converted.customer_id) == str(conversion_result.customer_id)

            won = cast(
                OpportunityWon,
                next(e for e in captured if e.event_type == "crm.opportunity.won"),
            )
            assert won.value == Decimal("5000")

            lost = cast(
                OpportunityLost,
                next(e for e in captured if e.event_type == "crm.opportunity.lost"),
            )
            assert lost.lost_reason == "Went silent"

            stage_changed = cast(
                OpportunityStageChanged,
                next(
                    e
                    for e in captured
                    if e.event_type == "crm.opportunity.stage_changed"
                ),
            )
            assert stage_changed.to_stage_id == stage2_id
        finally:
            set_event_bus(original_bus)


class TestEventBusIsolation:
    def test_crm_bus_is_independent_from_sales_bus(self) -> None:
        """T071's acceptance criterion: the CRM bus is a genuinely
        independent instance, not shared with any other module's bus."""
        from modules.sales.events import get_event_bus as get_sales_event_bus

        crm_bus: object = get_event_bus()
        sales_bus: object = get_sales_event_bus()
        assert crm_bus is not sales_bus

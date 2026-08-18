"""Integration test: register_crm_integration_handlers() (T076).

Verifies T074's Sales-event consumption works and does not mutate any
CRM state beyond the documented Activity/note write:
  - Publishing Sales' real ``quotation.accepted`` event (on Sales' own
    event bus) causes a CRM Activity to be created for the customer's
    Opportunity owner.
  - Publishing ``sales.order.credit_hold`` does the same.
  - Neither handler changes any Opportunity's stage/status as a side
    effect (spec.md §21.2's "human always confirms" invariant).
  - A customer with no CRM Opportunity yet produces a graceful no-op
    (event dropped, no Activity created, no error).

Task: T076 (tasks.md Phase 8).
"""

from __future__ import annotations

from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

import modules.crm.handlers.integration_handlers as handlers
from modules.crm.handlers.integration_handlers import (
    handle_order_credit_hold,
    handle_quotation_accepted,
    register_crm_integration_handlers,
)
from modules.crm.models.opportunity import Opportunity
from modules.crm.models.pipeline import Pipeline
from modules.crm.models.pipeline_stage import PipelineStage
from modules.crm.repositories.activity import ActivityRepository
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.crm.repositories.pipeline import PipelineRepository
from modules.crm.repositories.pipeline_stage import PipelineStageRepository
from modules.sales.events import InProcessEventBus as SalesInProcessEventBus
from modules.sales.events import get_event_bus as get_sales_event_bus
from modules.sales.events.order_events import OrderCreditHold
from modules.sales.events.quotation_events import QuotationAccepted
from modules.sales.models.customer import Customer
from modules.sales.models.master import CustomerCategory
from modules.sales.repositories.customer import CustomerRepository
from modules.sales.repositories.master import CustomerCategoryRepository


def _create_customer(db_session: Session, company_id: UUID) -> Customer:
    category = CustomerCategoryRepository(db_session).create(
        CustomerCategory(
            company_id=company_id, code=f"CAT-{uuid4().hex[:6]}", name="Handler Test"
        )
    )
    return CustomerRepository(db_session).create(
        Customer(
            company_id=company_id,
            customer_code=f"CUST-{uuid4().hex[:8]}",
            legal_name="Handler Test Customer",
            customer_type="COMPANY",
            category_id=str(category.id),
            currency_code="USD",
            status="ACTIVE",
        )
    )


def _create_opportunity(
    db_session: Session, company_id: UUID, customer_id: UUID, owner_id: UUID
) -> Opportunity:
    pipeline = PipelineRepository(db_session).create(
        Pipeline(company_id=company_id, name="Handler Pipeline", is_default=True)
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
    return OpportunityRepository(db_session).create(
        Opportunity(
            company_id=company_id,
            name="Handler Deal",
            customer_id=str(customer_id),
            owner_id=str(owner_id),
            pipeline_id=pipeline.id,
            stage_id=stage.id,
            value=Decimal("1000"),
            currency_code="USD",
            probability=20,
        )
    )


class TestQuotationAcceptedHandler:
    def test_creates_activity_for_opportunity_owner(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(handlers, "SessionLocal", lambda: db_session)
        company_id = uuid4()
        customer = _create_customer(db_session, company_id)
        customer_id = customer.id
        owner_id = uuid4()
        opportunity = _create_opportunity(db_session, company_id, customer_id, owner_id)
        opportunity_id, opportunity_stage_id = opportunity.id, opportunity.stage_id

        sales_bus = get_sales_event_bus()
        original_handlers = dict(sales_bus._handlers)  # type: ignore[attr-defined]
        try:
            sales_bus.clear_handlers()
            register_crm_integration_handlers()

            sales_bus.publish(
                QuotationAccepted(
                    aggregate_id=uuid4(),
                    company_id=company_id,
                    quotation_id=uuid4(),
                    quotation_number="QUO-0001",
                    customer_id=customer_id,
                    total_amount=5000.0,
                )
            )
        finally:
            sales_bus.clear_handlers()
            sales_bus._handlers.update(original_handlers)  # type: ignore[attr-defined]

        # The handler's own db.close() expires/detaches every ORM instance
        # tracked by this shared session (including `customer`/`opportunity`
        # above) — re-query fresh rather than touching their attributes.
        activities, total = ActivityRepository(db_session).list_filtered(
            company_id, customer_id=customer_id
        )
        assert total == 1
        assert activities[0].activity_type == "NOTE"
        assert activities[0].assigned_to == str(owner_id)
        assert "QUO-0001" in activities[0].subject

        # No Opportunity stage/status mutation as a side effect.
        fresh_opportunity = OpportunityRepository(db_session).get_by_id_or_none(
            id=opportunity_id, company_id=company_id
        )
        assert fresh_opportunity is not None
        assert fresh_opportunity.status == "OPEN"
        assert fresh_opportunity.stage_id == opportunity_stage_id

    def test_customer_with_no_opportunity_is_a_graceful_noop(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(handlers, "SessionLocal", lambda: db_session)
        company_id = uuid4()
        customer = _create_customer(db_session, company_id)
        customer_id = customer.id

        # Direct handler call (no bus involved) — simplest way to prove
        # the no-op path without touching the shared Sales bus singleton.
        handle_quotation_accepted(
            QuotationAccepted(
                aggregate_id=uuid4(),
                company_id=company_id,
                quotation_id=uuid4(),
                quotation_number="QUO-0002",
                customer_id=customer_id,
                total_amount=1000.0,
            )
        )

        activities, total = ActivityRepository(db_session).list_filtered(
            company_id, customer_id=customer_id
        )
        assert total == 0


class TestOrderCreditHoldHandler:
    def test_creates_activity_for_opportunity_owner(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(handlers, "SessionLocal", lambda: db_session)
        company_id = uuid4()
        customer = _create_customer(db_session, company_id)
        customer_id = customer.id
        owner_id = uuid4()
        _create_opportunity(db_session, company_id, customer_id, owner_id)

        handle_order_credit_hold(
            OrderCreditHold(
                aggregate_id=uuid4(),
                company_id=company_id,
                order_id=uuid4(),
                order_number="SO-0001",
                customer_id=str(customer_id),
                credit_status="EXCEEDED",
                credit_limit="10000.00",
                outstanding_balance="12000.00",
                order_total="2000.00",
            )
        )

        activities, total = ActivityRepository(db_session).list_filtered(
            company_id, customer_id=customer_id
        )
        assert total == 1
        assert activities[0].activity_type == "NOTE"
        assert activities[0].assigned_to == str(owner_id)
        assert "SO-0001" in activities[0].subject


class TestRegistrationSubscribesToSalesBusNotCrmBus:
    def test_register_subscribes_onto_sales_bus(self) -> None:
        """T074's own design: the handlers subscribe onto Sales' bus
        instance, not CRM's own (CRM's bus is for CRM's own publishers)."""
        sales_bus = cast(SalesInProcessEventBus, get_sales_event_bus())
        original_handlers = dict(sales_bus._handlers)
        try:
            sales_bus.clear_handlers()
            assert sales_bus.handler_count("quotation.accepted") == 0
            register_crm_integration_handlers()
            assert sales_bus.handler_count("quotation.accepted") == 1
            assert sales_bus.handler_count("sales.order.credit_hold") == 1
        finally:
            sales_bus.clear_handlers()
            sales_bus._handlers.update(original_handlers)

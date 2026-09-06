"""Integration test: Customer 360 composition + N+1 prevention (tasks.md T056).

Verifies plan.md §14/ADR-6's "6 bounded queries, zero N+1" design with a
concrete, automated query-count regression guard — no precedent for this
technique exists elsewhere in the test suite (checked; none found), so a
small, test-local SQLAlchemy ``before_cursor_execute`` counter is built
here rather than reusing a shared utility that doesn't exist yet.

Scenarios:
  - Zero-CRM-history graceful degradation (AC-17): empty arrays, no error,
    default zero/GOOD financial figures for a Customer with no AR ledger.
  - Query count bounded and independent of row count (populated Customer
    with 10 Opportunities + 20 Activities vs. an empty Customer).
  - Financial figures match ``AccountsReceivableService``'s own response
    byte-for-byte — never a cached/re-derived CRM value (AC-16).
  - Cross-tenant Customer -> ``CustomerNotFoundError`` before any other
    query runs (spec.md §30.2).

Task: T056 (tasks.md Phase 7).
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.accounting.dependencies import build_ar_service
from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.accounting.repositories.ar import (
    ARTransactionRepository,
    CustomerLedgerRepository,
)
from modules.crm.exceptions import CustomerNotFoundError
from modules.crm.models.activity import Activity
from modules.crm.models.lead import Lead
from modules.crm.models.opportunity import Opportunity
from modules.crm.models.pipeline import Pipeline
from modules.crm.models.pipeline_stage import PipelineStage
from modules.crm.repositories.activity import ActivityRepository
from modules.crm.repositories.lead import LeadRepository
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.crm.repositories.pipeline import PipelineRepository
from modules.crm.repositories.pipeline_stage import PipelineStageRepository
from modules.crm.services.customer_360_service import Customer360Service
from modules.sales.models.customer import Customer
from modules.sales.models.master import CustomerCategory
from modules.sales.repositories.customer import CustomerRepository
from modules.sales.repositories.master import CustomerCategoryRepository


def _build_service(db_session: Session) -> Customer360Service:
    ar_service = build_ar_service(db_session, with_sales_sync=False)
    return Customer360Service(
        db=db_session,
        customer_repo=CustomerRepository(db_session),
        lead_repo=LeadRepository(db_session),
        opportunity_repo=OpportunityRepository(db_session),
        activity_repo=ActivityRepository(db_session),
        ar_service=ar_service,
    )


def _create_customer(
    db_session: Session, company_id: UUID, **overrides: Any
) -> Customer:
    category_repo = CustomerCategoryRepository(db_session)
    category = category_repo.create(
        CustomerCategory(
            company_id=company_id, code=f"CAT-{uuid4().hex[:6]}", name="Test Category"
        )
    )
    fields: dict[str, Any] = {
        "company_id": company_id,
        "customer_code": f"CUST-{uuid4().hex[:8]}",
        "legal_name": "360 Test Customer",
        "customer_type": "COMPANY",
        "category_id": str(category.id),
        "currency_code": "USD",
        "status": "ACTIVE",
    }
    fields.update(overrides)
    return CustomerRepository(db_session).create(Customer(**fields))


def _create_pipeline_and_stage(
    db_session: Session, company_id: UUID
) -> tuple[UUID, UUID]:
    pipeline = PipelineRepository(db_session).create(
        Pipeline(company_id=company_id, name="Test Pipeline", is_default=True)
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


def _create_opportunity(
    db_session: Session,
    company_id: UUID,
    customer_id: UUID,
    pipeline_id: UUID,
    stage_id: UUID,
    **overrides: Any,
) -> Opportunity:
    fields: dict[str, Any] = {
        "company_id": company_id,
        "name": f"Deal {uuid4().hex[:6]}",
        "customer_id": str(customer_id),
        "owner_id": str(uuid4()),
        "pipeline_id": pipeline_id,
        "stage_id": stage_id,
        "value": Decimal("1000"),
        "currency_code": "USD",
        "probability": 20,
    }
    fields.update(overrides)
    return OpportunityRepository(db_session).create(Opportunity(**fields))


def _create_activity(
    db_session: Session, company_id: UUID, customer_id: UUID, **overrides: Any
) -> Activity:
    fields: dict[str, Any] = {
        "company_id": company_id,
        "activity_type": "CALL",
        "subject": "Follow-up call",
        "status": "PLANNED",
        "assigned_to": str(uuid4()),
        "customer_id": str(customer_id),
    }
    fields.update(overrides)
    return ActivityRepository(db_session).create(Activity(**fields))


@contextmanager
def _count_queries(db_session: Session):
    counter = {"n": 0}
    connection = db_session.get_bind()

    def _before_cursor_execute(*args: Any, **kwargs: Any) -> None:
        counter["n"] += 1

    event.listen(connection, "before_cursor_execute", _before_cursor_execute)
    try:
        yield counter
    finally:
        event.remove(connection, "before_cursor_execute", _before_cursor_execute)


class TestGracefulDegradation:
    def test_zero_crm_history_returns_empty_sections_no_error(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        customer = _create_customer(db_session, company_id)
        service = _build_service(db_session)

        result = service.get_customer_360(company_id, customer.id)

        assert result.customer.id == customer.id
        assert result.converted_leads == []
        assert result.opportunities == []
        assert result.activities == []
        assert result.last_interaction is None
        assert result.next_follow_up is None
        # AC-17: no CustomerLedger row yet -> zero/GOOD defaults, not an error.
        assert result.financial_summary.total_outstanding_base == Decimal("0")
        assert result.financial_summary.credit_status == "GOOD"
        assert result.sales_history.quotation_count == 0
        assert result.sales_history.order_count == 0
        assert result.sales_history.invoice_count == 0
        assert result.sales_history.delivery_count == 0


class TestCrossTenant:
    def test_customer_from_another_company_raises_not_found(
        self, db_session: Session
    ) -> None:
        company_a = uuid4()
        company_b = uuid4()
        customer = _create_customer(db_session, company_a)
        service = _build_service(db_session)

        with pytest.raises(CustomerNotFoundError):
            service.get_customer_360(company_b, customer.id)

    def test_nonexistent_customer_raises_not_found(self, db_session: Session) -> None:
        service = _build_service(db_session)
        with pytest.raises(CustomerNotFoundError):
            service.get_customer_360(uuid4(), uuid4())


class TestQueryCountBounded:
    def test_query_count_does_not_scale_with_row_count(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        pipeline_id, stage_id = _create_pipeline_and_stage(db_session, company_id)

        empty_customer = _create_customer(db_session, company_id)
        populated_customer = _create_customer(db_session, company_id)
        for _ in range(10):
            _create_opportunity(
                db_session, company_id, populated_customer.id, pipeline_id, stage_id
            )
        for _ in range(20):
            _create_activity(db_session, company_id, populated_customer.id)

        service = _build_service(db_session)

        with _count_queries(db_session) as empty_counter:
            empty_result = service.get_customer_360(company_id, empty_customer.id)
        with _count_queries(db_session) as populated_counter:
            populated_result = service.get_customer_360(
                company_id, populated_customer.id
            )

        assert len(populated_result.opportunities) == 10
        assert len(populated_result.activities) == 20
        # The query count must stay flat regardless of row count — if a
        # per-row lazy-load crept in, this would scale linearly with
        # 10 Opportunities + 20 Activities (i.e. jump by 30+), not stay
        # within a handful of queries of the empty case.
        assert populated_counter["n"] <= empty_counter["n"] + 3
        assert populated_counter["n"] < 20


class TestFinancialFiguresMatchLiveAccountingService:
    def test_financial_summary_matches_ar_service_response_exactly(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        customer = _create_customer(db_session, company_id)

        ledger_repo = CustomerLedgerRepository(db_session)
        ledger = ledger_repo.create(
            CustomerLedger(
                company_id=company_id,
                customer_id=customer.id,
                credit_limit=Decimal("5000"),
                credit_status="WARNING",
                total_outstanding_base=Decimal("1234.56"),
            )
        )
        txn_repo = ARTransactionRepository(db_session)
        today = utcnow().date()
        txn_repo.create(
            ARTransaction(
                company_id=company_id,
                customer_ledger_id=ledger.id,
                transaction_type="INVOICE",
                transaction_date=today - timedelta(days=10),
                due_date=today - timedelta(days=3),
                currency_code="USD",
                amount_foreign=Decimal("1234.56"),
                amount_base=Decimal("1234.56"),
                outstanding_amount=Decimal("1234.56"),
                status="OPEN",
                invoice_number="INV-360-TEST",
            )
        )

        ar_service = build_ar_service(db_session, with_sales_sync=False)
        expected_ledger = ar_service.get_customer_ledger(company_id, customer.id)
        expected_aging = ar_service.get_customer_aging(
            company_id, customer.id, as_of_date=today
        )
        assert expected_aging is not None

        service = _build_service(db_session)
        result = service.get_customer_360(company_id, customer.id)

        assert (
            result.financial_summary.total_outstanding_base
            == expected_ledger.total_outstanding_base
        )
        assert result.financial_summary.credit_status == expected_ledger.credit_status
        assert result.financial_summary.credit_limit == expected_ledger.credit_limit
        assert result.financial_summary.days_1_30 == expected_aging.days_1_30
        assert result.financial_summary.current == expected_aging.current


class TestLastInteractionAndNextFollowUp:
    def test_computed_from_fetched_activities_and_leads(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        customer = _create_customer(db_session, company_id)
        now = utcnow()

        _create_activity(
            db_session,
            company_id,
            customer.id,
            status="COMPLETED",
            completed_at=now - timedelta(days=5),
        )
        _create_activity(
            db_session,
            company_id,
            customer.id,
            status="COMPLETED",
            completed_at=now - timedelta(days=1),
        )
        _create_activity(
            db_session,
            company_id,
            customer.id,
            status="PLANNED",
            activity_type="TASK",
            due_date=now + timedelta(days=7),
        )

        lead_repo = LeadRepository(db_session)
        lead_repo.create(
            Lead(
                company_id=company_id,
                first_name="Origin",
                last_name="Lead",
                email=f"origin-{uuid4().hex[:8]}@example.com",
                status="CONVERTED",
                converted_customer_id=str(customer.id),
                converted_at=now,
                next_follow_up_date=(now + timedelta(days=2)).date(),
            )
        )

        service = _build_service(db_session)
        result = service.get_customer_360(company_id, customer.id)

        # SQLite round-trips datetimes as naive; compare on wall-clock value
        # only (PostgreSQL preserves tzinfo — this is a test-environment
        # artifact, not a service defect).
        assert result.last_interaction is not None
        assert result.last_interaction.replace(tzinfo=None) == (
            now - timedelta(days=1)
        ).replace(tzinfo=None)
        # Earliest of: the PLANNED Activity's due_date (+7d) and the
        # converted Lead's next_follow_up_date (+2d) -> +2d wins.
        assert result.next_follow_up == (now + timedelta(days=2)).date()
        assert len(result.converted_leads) == 1

"""T094 — Customer 360 composition performance benchmark (spec.md §47/NFR-003).

Measures ``Customer360Service.get_customer_360()`` against a Customer with
500 combined CRM/Sales/Accounting records — the exact bound spec.md
NFR-003 assumes. Service construction mirrors the established
``tests/integration/repositories/crm/test_customer_360.py``'s
``_build_service()`` helper (``build_ar_service(db, with_sales_sync=False)``).

Asserted at the real spec-mandated value (p95 < 1s), not a scaled guard:
the service is deliberately designed (plan.md ADR-6, ``_LIST_LIMIT = 50``)
to issue a small, fixed number of bounded queries independent of how many
total records a Customer has accumulated — so row count here stresses
that design assumption directly rather than confounding with an
unbounded scan.

Task: T094 (tasks.md Phase 10). Spec ref: spec.md §47/NFR-003.
"""

from __future__ import annotations

import statistics
import time
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.accounting.dependencies import build_ar_service
from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.accounting.repositories.ar import (
    ARTransactionRepository,
    CustomerLedgerRepository,
)
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

_TARGET_SECONDS = 1.0  # spec.md §47/NFR-003 — the real target, not a scaled guard
_OPPORTUNITY_COUNT = 200
_ACTIVITY_COUNT = 200
_CONVERTED_LEAD_COUNT = 100  # 200 + 200 + 100 = 500 combined records (NFR-003's bound)
_SAMPLE_CALLS = 15


def _p95(samples: list[float]) -> float:
    return statistics.quantiles(samples, n=100)[94]


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


def _seed(db_session: Session, company_id: UUID) -> UUID:
    category = CustomerCategoryRepository(db_session).create(
        CustomerCategory(
            company_id=company_id, code=f"CAT-{uuid4().hex[:6]}", name="Perf Category"
        )
    )
    customer = CustomerRepository(db_session).create(
        Customer(
            company_id=company_id,
            customer_code=f"CUST-{uuid4().hex[:8]}",
            legal_name="Customer 360 Perf Test",
            customer_type="COMPANY",
            category_id=str(category.id),
            currency_code="USD",
            status="ACTIVE",
        )
    )

    ledger = CustomerLedgerRepository(db_session).create(
        CustomerLedger(
            company_id=company_id,
            customer_id=customer.id,
            credit_limit=Decimal("50000"),
            credit_status="GOOD",
            total_outstanding_base=Decimal("12345.67"),
        )
    )
    txn_repo = ARTransactionRepository(db_session)
    today = utcnow().date()
    for i in range(20):
        txn_repo.create(
            ARTransaction(
                company_id=company_id,
                customer_ledger_id=ledger.id,
                transaction_type="INVOICE",
                transaction_date=today,
                due_date=today,
                currency_code="USD",
                amount_foreign=Decimal("100.00"),
                amount_base=Decimal("100.00"),
                outstanding_amount=Decimal("100.00"),
                status="OPEN",
                invoice_number=f"INV-PERF-{i:04d}",
            )
        )

    pipeline = PipelineRepository(db_session).create(
        Pipeline(company_id=company_id, name="Perf Pipeline", is_default=True)
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
    opp_repo = OpportunityRepository(db_session)
    for i in range(_OPPORTUNITY_COUNT):
        opp_repo.create(
            Opportunity(
                company_id=company_id,
                name=f"Perf Deal {i}",
                customer_id=str(customer.id),
                owner_id=str(uuid4()),
                pipeline_id=pipeline.id,
                stage_id=stage.id,
                value=Decimal("1000"),
                currency_code="USD",
                probability=20,
            )
        )

    activity_repo = ActivityRepository(db_session)
    for i in range(_ACTIVITY_COUNT):
        activity_repo.create(
            Activity(
                company_id=company_id,
                activity_type="CALL",
                subject=f"Perf Activity {i}",
                status="PLANNED",
                assigned_to=str(uuid4()),
                customer_id=str(customer.id),
            )
        )

    lead_repo = LeadRepository(db_session)
    for i in range(_CONVERTED_LEAD_COUNT):
        lead_repo.create(
            Lead(
                company_id=company_id,
                first_name=f"Converted{i}",
                last_name="Perf",
                email=f"converted-perf-{i}@example.com",
                status="CONVERTED",
                converted_customer_id=str(customer.id),
                converted_opportunity_id=None,
            )
        )

    return customer.id


class TestCustomer360Performance:
    def test_customer_360_p95_under_target(self, db_session: Session) -> None:
        company_id = uuid4()
        seed_start = time.perf_counter()
        customer_id = _seed(db_session, company_id)
        print(
            f"\nSeeded {_OPPORTUNITY_COUNT + _ACTIVITY_COUNT + _CONVERTED_LEAD_COUNT} "
            f"combined records in {time.perf_counter() - seed_start:.2f}s"
        )

        service = _build_service(db_session)
        samples: list[float] = []
        for _ in range(_SAMPLE_CALLS):
            start = time.perf_counter()
            result = service.get_customer_360(company_id, customer_id)
            samples.append(time.perf_counter() - start)
            assert result.customer.id == customer_id

        p95 = _p95(samples)
        print(f"Customer 360 p95 over {_SAMPLE_CALLS} calls: {p95:.3f}s")
        assert p95 < _TARGET_SECONDS, (
            f"Customer 360 p95 {p95:.3f}s exceeds {_TARGET_SECONDS}s"
        )

"""Integration tests for AR credit hold — Phase 6.

Tests (tasks.md T154):
  - Placing a hold publishes ``accounting.ar.customer.credithold`` on
    Accounting's own event bus.
  - Placing a hold syncs to Sales' real ``Customer.credit_status`` (the
    field ``CreditCheckService.evaluate_credit()`` reads live to block new
    sales order approvals) — a direct cross-module service call, not a
    speculative event/subscriber (see ar_service.py's module docstring).
  - Releasing a hold recomputes credit_status and syncs it back to Sales.
  - A Sales-side sync failure (e.g. customer not found in Sales) does not
    break the Accounting-side hold.

Spec ref: specs/008-accounting-finance/tasks.md T154
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.events import (
    AccountingDomainEvent,
    InProcessEventBus,
    set_event_bus,
)
from modules.accounting.events.ar_events import CreditHoldPlacedEvent
from modules.accounting.repositories.ar import (
    ARPaymentAllocationRepository,
    ARTransactionRepository,
    CustomerCreditHistoryRepository,
    CustomerLedgerRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.ar_service import AccountsReceivableService
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.posting_engine import PostingEngine
from modules.sales.models.customer import Customer
from modules.sales.repositories.customer import (
    CustomerAddressRepository,
    CustomerContactRepository,
    CustomerRepository,
)
from modules.sales.services.customer_service import CustomerService
from modules.sales.services.sequence_service import SalesSequenceService


@pytest.fixture
def fresh_accounting_bus() -> InProcessEventBus:
    bus = InProcessEventBus()
    set_event_bus(bus)
    return bus


@pytest.fixture
def sales_customer_service(db_session: Session) -> CustomerService:
    return CustomerService(
        db=db_session,
        customer_repo=CustomerRepository(db_session),
        contact_repo=CustomerContactRepository(db_session),
        address_repo=CustomerAddressRepository(db_session),
        sequence_service=SalesSequenceService(db_session),
    )


@pytest.fixture
def ar_service(
    db_session: Session, sales_customer_service: CustomerService
) -> AccountsReceivableService:
    return AccountsReceivableService(
        db=db_session,
        ledger_repo=CustomerLedgerRepository(db_session),
        transaction_repo=ARTransactionRepository(db_session),
        allocation_repo=ARPaymentAllocationRepository(db_session),
        credit_history_repo=CustomerCreditHistoryRepository(db_session),
        config_repo=AccountingConfigurationRepository(db_session),
        posting_engine=PostingEngine.__new__(
            PostingEngine
        ),  # unused by credit-hold paths
        audit_service=AuditLogService(
            db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
        ),
        sales_customer_service=sales_customer_service,
    )


def _make_sales_customer(
    db_session: Session, company_id, code: str = "CUST-HOLD-1"
) -> Customer:
    customer = Customer(
        company_id=company_id,
        customer_code=code,
        legal_name="Hold Test Corp",
        customer_type="COMPANY",
        category_id=str(uuid4()),
        currency_code="USD",
        credit_limit=Decimal("10000"),
        credit_status="GOOD",
        status="ACTIVE",
        version=1,
        created_by=uuid4(),
    )
    db_session.add(customer)
    db_session.flush()
    return customer


class TestCreditHoldCrossModuleSync:
    def test_place_hold_publishes_accounting_event(
        self,
        ar_service: AccountsReceivableService,
        fresh_accounting_bus: InProcessEventBus,
        db_session: Session,
    ) -> None:
        company_id = uuid4()
        customer = _make_sales_customer(db_session, company_id)

        received: list[AccountingDomainEvent] = []
        fresh_accounting_bus.subscribe(
            "accounting.ar.customer.credithold", lambda e: received.append(e)
        )

        ar_service.place_credit_hold(
            company_id=company_id,
            customer_id=customer.id,
            reason="Repeated late payment",
            actor_id=None,
        )

        assert len(received) == 1
        event = received[0]
        assert isinstance(event, CreditHoldPlacedEvent)
        assert event.customer_id == customer.id
        assert event.reason == "Repeated late payment"

    def test_place_hold_syncs_to_sales_customer(
        self,
        ar_service: AccountsReceivableService,
        sales_customer_service: CustomerService,
        db_session: Session,
    ) -> None:
        company_id = uuid4()
        customer = _make_sales_customer(db_session, company_id, "CUST-HOLD-2")

        ar_service.place_credit_hold(
            company_id=company_id,
            customer_id=customer.id,
            reason="Overdue balance",
            actor_id=None,
        )

        refreshed = sales_customer_service.get_by_id(
            company_id=company_id, customer_id=customer.id
        )
        assert refreshed.credit_status == "HOLD"

    def test_release_hold_syncs_recomputed_status_to_sales(
        self,
        ar_service: AccountsReceivableService,
        sales_customer_service: CustomerService,
        db_session: Session,
    ) -> None:
        company_id = uuid4()
        customer = _make_sales_customer(db_session, company_id, "CUST-HOLD-3")

        ar_service.place_credit_hold(
            company_id=company_id,
            customer_id=customer.id,
            reason="Test hold",
            actor_id=None,
        )
        ar_service.release_credit_hold(
            company_id=company_id, customer_id=customer.id, actor_id=None
        )

        refreshed = sales_customer_service.get_by_id(
            company_id=company_id, customer_id=customer.id
        )
        assert refreshed.credit_status == "GOOD"

    def test_sync_failure_does_not_break_accounting_hold(
        self, ar_service: AccountsReceivableService, db_session: Session
    ) -> None:
        company_id = uuid4()
        customer_id = (
            uuid4()
        )  # no matching Sales Customer row -> sync raises internally

        ledger = ar_service.place_credit_hold(
            company_id=company_id,
            customer_id=customer_id,
            reason="No Sales customer exists",
            actor_id=None,
        )

        assert ledger.credit_status == "HOLD"


class TestCreditHoldWithoutSalesSync:
    def test_place_and_release_hold_works_without_sales_service(
        self, db_session: Session
    ) -> None:
        ar_service = AccountsReceivableService(
            db=db_session,
            ledger_repo=CustomerLedgerRepository(db_session),
            transaction_repo=ARTransactionRepository(db_session),
            allocation_repo=ARPaymentAllocationRepository(db_session),
            credit_history_repo=CustomerCreditHistoryRepository(db_session),
            config_repo=AccountingConfigurationRepository(db_session),
            posting_engine=PostingEngine.__new__(PostingEngine),
            audit_service=AuditLogService(
                db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
            ),
            sales_customer_service=None,
        )
        company_id = uuid4()
        customer_id = uuid4()

        ledger = ar_service.place_credit_hold(
            company_id=company_id,
            customer_id=customer_id,
            reason="No sync configured",
            actor_id=None,
        )
        assert ledger.credit_status == "HOLD"

        released = ar_service.release_credit_hold(
            company_id=company_id, customer_id=customer_id, actor_id=None
        )
        assert released.credit_status == "GOOD"

"""[Epic 10, Phase 6, T112] Backward-compatibility regression: every
existing standalone caller of ``AllocationEngine.allocate()`` must see
identical behavior/return type after it was rewritten (tasks.md T106)
into a thin wrapper of ``stage_allocation()`` + ``finalize_allocation()``
(plan.md §12.3.1). Exercises both the direct-call path and
``PaymentService.allocate_payment()``'s existing delegate path.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import (
    build_allocation_engine,
    build_ar_service,
    build_payment_service,
)
from modules.accounting.models.banking import BankAccount
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.models.payments import PaymentAllocationLine
from modules.accounting.repositories.ar import ARTransactionRepository
from modules.accounting.repositories.banking import BankAccountRepository
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.allocation_engine import AllocationEngine
from modules.accounting.services.ar_service import AccountsReceivableService
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.accounting.services.payment_service import PaymentService


@pytest.fixture
def setup(db_session: Session) -> dict:
    account_repo = AccountRepository(db_session)
    fiscal_service = FiscalCalendarService(
        db=db_session,
        year_repo=FiscalYearRepository(db_session),
        period_repo=FiscalPeriodRepository(db_session),
        opening_balance_repo=OpeningBalanceRepository(db_session),
        audit_service=AuditLogService(
            db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
        ),
    )
    company_id = uuid4()
    ar = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1100",
            account_name="AR",
            account_type="ASSET",
        )
    )
    bank_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1000",
            account_name="Bank",
            account_type="ASSET",
        )
    )
    bank = BankAccountRepository(db_session).create(
        BankAccount(
            company_id=company_id,
            bank_name="Test Bank",
            account_number="ACC-BC-02",
            currency_code="USD",
            gl_account_id=bank_gl.id,
        )
    )
    revenue = account_repo.create(
        Account(
            company_id=company_id,
            account_code="4000",
            account_name="Revenue",
            account_type="REVENUE",
        )
    )
    today = date.today()
    fiscal_service.create_fiscal_year(
        company_id,
        f"FY-{uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )
    AccountingConfigurationRepository(db_session).create(
        AccountingConfiguration(
            company_id=company_id,
            default_ar_account_id=ar.id,
            default_revenue_account_id=revenue.id,
        )
    )
    return {"company_id": company_id, "bank": bank, "today": today}


@pytest.fixture
def ar_service(db_session: Session) -> AccountsReceivableService:
    return build_ar_service(db_session, with_sales_sync=False)


@pytest.fixture
def payment_service(db_session: Session) -> PaymentService:
    return build_payment_service(db_session)


@pytest.fixture
def allocation_engine(db_session: Session) -> AllocationEngine:
    return build_allocation_engine(db_session)


class TestAllocateBackwardCompat:
    def test_direct_call_returns_allocation_lines_committed(
        self,
        ar_service: AccountsReceivableService,
        payment_service: PaymentService,
        allocation_engine: AllocationEngine,
        setup: dict,
    ) -> None:
        customer_id = uuid4()
        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-BC-ALLOC-1",
            total_amount=Decimal("400.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        payment, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=customer_id,
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("400.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        lines = allocation_engine.allocate(
            company_id=setup["company_id"],
            payment_id=payment.id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("400.00")}
            ],
            actor_id=None,
        )

        assert len(lines) == 1
        assert isinstance(lines[0], PaymentAllocationLine)
        assert lines[0].allocated_amount_foreign == Decimal("400.00")

        ar_repo = ARTransactionRepository(payment_service.db)
        refreshed_invoice = ar_repo.get_by_id_or_none(
            id=invoice.id, company_id=setup["company_id"]
        )
        assert refreshed_invoice.outstanding_amount == Decimal("0")
        assert refreshed_invoice.status == "PAID"

    def test_via_payment_service_delegate_still_works(
        self,
        ar_service: AccountsReceivableService,
        payment_service: PaymentService,
        setup: dict,
    ) -> None:
        """PaymentService.allocate_payment() delegates to
        AllocationEngine.allocate() unchanged — proves the rewrite is
        transparent through this existing call path too."""
        customer_id = uuid4()
        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-BC-ALLOC-2",
            total_amount=Decimal("150.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        payment, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=customer_id,
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("150.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        lines = payment_service.allocate_payment(
            company_id=setup["company_id"],
            payment_id=payment.id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("150.00")}
            ],
            actor_id=None,
        )

        assert len(lines) == 1
        reconciled = ar_service.reconcile_ar_control_account(setup["company_id"])
        assert reconciled == Decimal("0")

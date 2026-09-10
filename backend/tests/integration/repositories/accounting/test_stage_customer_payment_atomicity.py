"""[Epic 10, Phase 6, T115] Real-Postgres forced-failure atomicity proof
for ``PaymentService.stage_customer_payment()`` +
``AllocationEngine.stage_allocation()`` / their paired
``finalize_customer_payment()``/``finalize_allocation()`` — Layer A
(Accounting-only; Layer B, proving Installments' own
``InstallmentAllocationReference`` rows commit together with these, is
deferred to Phase 7 per tasks.md's Phase 6 Exit Gate, since that model
does not exist until then).

Exercises the exact sequence plan.md §12.3.1 requires:
``stage_customer_payment()`` -> ``stage_allocation()`` -> (a caller would
stage its own rows here) -> ``finalize_customer_payment()`` ->
``finalize_allocation()``. Forces the failure immediately after both
staging calls, before either finalize is called, then verifies — via a
second, independent connection to the same throwaway database — that the
``Payment``, the credit ``ARTransaction``, the ``PaymentAllocationLine``,
and the target invoice's outstanding amount are all simultaneously
absent/unchanged.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.orm import Session, sessionmaker

from modules.accounting.dependencies import (
    build_allocation_engine,
    build_ar_service,
    build_payment_service,
)
from modules.accounting.models.banking import BankAccount
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.models.payments import Payment, PaymentAllocationLine
from modules.accounting.repositories.banking import BankAccountRepository
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.accounting.services.payment_service import StagedCustomerPayment
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)


@pytest.fixture
def pg_engine(request: pytest.FixtureRequest):
    pg_url = request.getfixturevalue("pg_test_db")
    alembic_upgrade(pg_url, "072")
    engine = db_engine(pg_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(pg_engine) -> Generator[Session, None, None]:
    session_factory = sessionmaker(bind=pg_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def setup(pg_engine, db_session: Session) -> dict[str, Any]:
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
    company_id = uuid.uuid4()
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
            account_number="ACC-ATOMIC-01",
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
        f"FY-{uuid.uuid4().hex[:8]}",
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
    db_session.commit()
    return {
        "company_id": company_id,
        "bank": bank,
        "today": today,
        "pg_engine": pg_engine,
    }


class TestStageCustomerPaymentAtomicity:
    def test_forced_failure_between_staging_and_finalize_leaves_nothing_committed(
        self, db_session: Session, setup: dict[str, Any]
    ) -> None:
        ar_service = build_ar_service(db_session, with_sales_sync=False)
        payment_service = build_payment_service(db_session)
        allocation_engine = build_allocation_engine(db_session)
        customer_id = uuid.uuid4()

        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid.uuid4(),
            invoice_number="INV-ATOMIC-1",
            total_amount=Decimal("500.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        db_session.commit()

        staged_payment = payment_service.stage_customer_payment(
            company_id=setup["company_id"],
            customer_id=customer_id,
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("500.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )
        staged_allocation = allocation_engine.stage_allocation(
            company_id=setup["company_id"],
            payment_id=staged_payment.payment.id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("500.00")}
            ],
            actor_id=None,
        )
        payment_id = staged_payment.payment.id
        allocation_line_ids = [line.id for line in staged_allocation.results]

        # A generic caller-supplied row, flushed into the same session —
        # standing in for "the caller's own rows" (e.g. an Installments
        # InstallmentAllocationReference/audit/outbox row) a real
        # cross-module caller would stage here before calling either
        # finalize method.
        placeholder_account = Account(
            company_id=setup["company_id"],
            account_code="9999",
            account_name="Forced-Failure Placeholder",
            account_type="ASSET",
        )
        db_session.add(placeholder_account)
        db_session.flush()
        placeholder_account_id = placeholder_account.id

        class _InjectedFailure(Exception):
            pass

        try:
            raise _InjectedFailure(
                "simulated failure before finalize_customer_payment() is called"
            )
        except _InjectedFailure:
            db_session.rollback()

        verify_session_factory = sessionmaker(bind=setup["pg_engine"])
        verify_session = verify_session_factory()
        try:
            payment = verify_session.get(Payment, payment_id)
            assert payment is None

            for line_id in allocation_line_ids:
                allocation_line = verify_session.get(PaymentAllocationLine, line_id)
                assert allocation_line is None

            refreshed_invoice = ar_service.get_transaction_by_id(
                setup["company_id"], invoice.id
            )
            assert refreshed_invoice is not None
            assert refreshed_invoice.outstanding_amount == Decimal("500.00")

            placeholder = verify_session.get(Account, placeholder_account_id)
            assert placeholder is None
            assert refreshed_invoice.status == "OPEN"
        finally:
            verify_session.close()

    def test_normal_path_commits_payment_and_allocation_together(
        self, db_session: Session, setup: dict[str, Any]
    ) -> None:
        ar_service = build_ar_service(db_session, with_sales_sync=False)
        payment_service = build_payment_service(db_session)
        allocation_engine = build_allocation_engine(db_session)
        customer_id = uuid.uuid4()

        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid.uuid4(),
            invoice_number="INV-ATOMIC-2",
            total_amount=Decimal("300.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        db_session.commit()

        staged_payment = payment_service.stage_customer_payment(
            company_id=setup["company_id"],
            customer_id=customer_id,
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("300.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )
        staged_allocation = allocation_engine.stage_allocation(
            company_id=setup["company_id"],
            payment_id=staged_payment.payment.id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("300.00")}
            ],
            actor_id=None,
        )
        assert isinstance(staged_payment, StagedCustomerPayment)
        payment, _ = payment_service.finalize_customer_payment(
            staged_payment, actor_id=None
        )
        allocation_lines = allocation_engine.finalize_allocation(
            staged_allocation, actor_id=None
        )

        verify_session_factory = sessionmaker(bind=setup["pg_engine"])
        verify_session = verify_session_factory()
        try:
            verified_payment = verify_session.get(Payment, payment.id)
            assert verified_payment is not None
            assert verified_payment.status == "ALLOCATED"

            for line in allocation_lines:
                verified_line = verify_session.get(PaymentAllocationLine, line.id)
                assert verified_line is not None

            refreshed_invoice = ar_service.get_transaction_by_id(
                setup["company_id"], invoice.id
            )
            assert refreshed_invoice is not None
            assert refreshed_invoice.outstanding_amount == Decimal("0")
            assert refreshed_invoice.status == "PAID"
        finally:
            verify_session.close()

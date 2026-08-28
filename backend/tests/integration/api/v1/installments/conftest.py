"""Shared real-Postgres fixtures for Epic 10 Phase 7 (Collections) tests.

``InstallmentScheduleLine``/``InstallmentScheduleVersion`` rely on
``server_default=text("now()")``, which SQLite's in-memory test engine
cannot resolve (established in Phase 6 verification) — every test that
touches a schedule line therefore needs the real-Postgres throwaway-
database fixtures already established by
``test_schedule_persistence.py``/``test_outstanding_service.py``.

``build_active_contract_with_schedule()`` bypasses
``InstallmentContractService.create_draft()``/``activate()`` (which
require a real ``modules.sales`` invoice/customer via
``SalesInvoiceReadGateway``/``SalesCustomerReadGateway``) and instead
constructs an already-``ACTIVE`` contract + schedule directly — the
narrower concern Phase 7's collection/reversal tests need is
``InstallmentCollectionService`` behavior against an existing active
contract, not activation itself (T124's own dedicated concern).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker

from core.events.outbox import EventOutboxRepository
from modules.accounting.dependencies import (
    build_allocation_engine,
    build_ar_service,
    build_payment_service,
)
from modules.accounting.models.banking import BankAccount
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
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
from modules.installments.models.contract import InstallmentContract
from modules.installments.models.schedule import (
    InstallmentScheduleLine,
    InstallmentScheduleVersion,
)
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.late_charge import (
    InstallmentLateChargeRepository,
)
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.collection_service import (
    InstallmentCollectionService,
)
from modules.installments.services.contract_service import InstallmentContractService
from modules.installments.services.delinquency_service import (
    InstallmentDelinquencyService,
)
from modules.installments.services.idempotency_service import (
    InstallmentIdempotencyService,
)
from modules.installments.services.outstanding_service import (
    InstallmentOutstandingService,
)
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)


@pytest.fixture
def pg_engine(request: pytest.FixtureRequest):
    pg_url = request.getfixturevalue("pg_test_db")
    alembic_upgrade(pg_url, "071")
    engine = db_engine(pg_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(pg_engine) -> Session:
    session_factory = sessionmaker(bind=pg_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def build_collection_service(db_session: Session) -> InstallmentCollectionService:
    ar_service = build_ar_service(db_session, with_sales_sync=False)
    payment_service = build_payment_service(db_session)
    allocation_engine = build_allocation_engine(db_session)
    gateway = AccountingIntegrationGateway(
        ar_service=ar_service,
        payment_service=payment_service,
        allocation_engine=allocation_engine,
    )
    schedule_repo = InstallmentScheduleRepository(db_session)
    contract_repo = InstallmentContractRepository(db_session)
    allocation_ref_repo = InstallmentAllocationReferenceRepository(db_session)
    late_charge_repo = InstallmentLateChargeRepository(db_session)
    outstanding_service = InstallmentOutstandingService(
        schedule_repo=schedule_repo,
        accounting_gateway=gateway,
        allocation_ref_repo=allocation_ref_repo,
        late_charge_repo=late_charge_repo,
    )
    audit_service = InstallmentAuditService(
        db=db_session, audit_repo=InstallmentAuditLogRepository(db_session)
    )
    contract_service = InstallmentContractService(
        repo=contract_repo,
        sequence_repo=None,  # type: ignore[arg-type]
        eligibility_service=None,  # type: ignore[arg-type]
        accounting_gateway=gateway,
        configuration_service=None,  # type: ignore[arg-type]
        audit_service=audit_service,
        schedule_repo=schedule_repo,
        idempotency_service=InstallmentIdempotencyService(db_session),
        outbox_repo=EventOutboxRepository(db_session),
    )
    return InstallmentCollectionService(
        db=db_session,
        contract_repo=contract_repo,
        schedule_repo=schedule_repo,
        allocation_ref_repo=allocation_ref_repo,
        accounting_gateway=gateway,
        outstanding_service=outstanding_service,
        idempotency_service=InstallmentIdempotencyService(db_session),
        audit_service=audit_service,
        outbox_repo=EventOutboxRepository(db_session),
        contract_service=contract_service,
        late_charge_repo=late_charge_repo,
    )


def build_delinquency_service(db_session: Session) -> InstallmentDelinquencyService:
    ar_service = build_ar_service(db_session, with_sales_sync=False)
    payment_service = build_payment_service(db_session)
    allocation_engine = build_allocation_engine(db_session)
    gateway = AccountingIntegrationGateway(
        ar_service=ar_service,
        payment_service=payment_service,
        allocation_engine=allocation_engine,
    )
    return InstallmentDelinquencyService(
        db=db_session,
        contract_repo=InstallmentContractRepository(db_session),
        schedule_repo=InstallmentScheduleRepository(db_session),
        allocation_ref_repo=InstallmentAllocationReferenceRepository(db_session),
        late_charge_repo=InstallmentLateChargeRepository(db_session),
        accounting_gateway=gateway,
        audit_service=InstallmentAuditService(
            db=db_session, audit_repo=InstallmentAuditLogRepository(db_session)
        ),
        outbox_repo=EventOutboxRepository(db_session),
    )


def build_active_contract_with_schedule(
    db_session: Session,
    *,
    installment_count: int = 3,
    installment_amount: Decimal = Decimal("100.00"),
    down_payment_amount: Decimal = Decimal("0"),
    grace_period_days: int = 0,
    late_charge_policy: dict | None = None,
) -> dict:
    """Build a fully self-contained, real-Postgres-backed ACTIVE
    installment contract with an active schedule version, ready for
    ``InstallmentCollectionService.record_collection()``/
    ``reverse_collection()`` to operate against — accounts, fiscal year,
    AccountingConfiguration, a real Accounting ``ARTransaction`` (the
    invoice), the contract row, and the schedule version+lines, all
    committed.
    """
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
    customer_id = uuid.uuid4()
    ar_account = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1100",
            account_name="AR",
            account_type="ASSET",
        )
    )
    revenue_account = account_repo.create(
        Account(
            company_id=company_id,
            account_code="4000",
            account_name="Revenue",
            account_type="REVENUE",
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
    late_fee_account = account_repo.create(
        Account(
            company_id=company_id,
            account_code="4100",
            account_name="Late Fee Income",
            account_type="REVENUE",
        )
    )
    bank_account = BankAccountRepository(db_session).create(
        BankAccount(
            company_id=company_id,
            bank_name="Test Bank",
            account_number=f"ACC-{uuid.uuid4().hex[:8]}",
            currency_code="USD",
            gl_account_id=bank_gl.id,
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
            default_ar_account_id=ar_account.id,
            default_revenue_account_id=revenue_account.id,
        )
    )
    db_session.commit()

    ar_service = build_ar_service(db_session, with_sales_sync=False)
    sales_invoice_id = uuid.uuid4()
    contractual_total = installment_amount * installment_count
    invoice_total = contractual_total + down_payment_amount
    invoice, _ = ar_service.record_sales_invoice(
        company_id=company_id,
        customer_id=customer_id,
        invoice_id=sales_invoice_id,
        invoice_number=f"INV-{uuid.uuid4().hex[:8]}",
        total_amount=invoice_total,
        currency_code="USD",
        transaction_date=today,
        due_date=today,
        actor_id=None,
    )
    if down_payment_amount > 0:
        # A real, committed down payment allocation, exactly mirroring
        # what activate() would have staged — reduces the invoice's
        # outstanding to contractual_total before collections begin.
        payment_service = build_payment_service(db_session)
        allocation_engine = build_allocation_engine(db_session)
        payment, _ = payment_service.create_customer_payment(
            company_id=company_id,
            customer_id=customer_id,
            payment_method="BANK_TRANSFER",
            payment_date=today,
            amount=down_payment_amount,
            currency_code="USD",
            bank_account_id=bank_account.id,
            actor_id=None,
        )
        allocation_engine.allocate(
            company_id=company_id,
            payment_id=payment.id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": down_payment_amount}
            ],
            actor_id=None,
        )

    effective_late_charge_policy = None
    if late_charge_policy is not None:
        effective_late_charge_policy = dict(late_charge_policy)
        effective_late_charge_policy.setdefault(
            "contra_account_id", str(late_fee_account.id)
        )

    contract_repo = InstallmentContractRepository(db_session)
    contract = InstallmentContract(
        company_id=company_id,
        contract_number=f"IC-{uuid.uuid4().hex[:8]}",
        customer_id=customer_id,
        sales_invoice_id=sales_invoice_id,
        contract_date=today,
        principal_amount=contractual_total,
        down_payment_amount=down_payment_amount,
        markup_amount=Decimal("0"),
        contractual_total=contractual_total,
        installment_count=installment_count,
        frequency="MONTHLY",
        first_due_date=today,
        maturity_date=today,
        currency_code="USD",
        status="ACTIVE",
        terms_snapshot={
            "note": "Phase 7/8 collection/delinquency-test fixture",
            "grace_period_days": grace_period_days,
            "late_charge_policy": effective_late_charge_policy,
        },
    )
    contract = contract_repo.create(contract)

    schedule_repo = InstallmentScheduleRepository(db_session)
    version = InstallmentScheduleVersion(
        company_id=company_id,
        contract_id=contract.id,
        version_number=1,
        status="ACTIVE",
    )
    # Distinct, strictly-increasing due dates (30 days apart) so
    # oldest-due-first ordering is meaningfully exercised, without
    # needing calendar-month arithmetic here.
    lines = [
        InstallmentScheduleLine(
            company_id=company_id,
            sequence=i + 1,
            due_date=date.fromordinal(today.toordinal() + i * 30),
            scheduled_amount=installment_amount,
        )
        for i in range(installment_count)
    ]
    schedule_repo.create_version_with_lines(version, lines)

    contract.active_schedule_version_id = version.id
    db_session.add(contract)
    db_session.commit()
    db_session.refresh(contract)

    return {
        "company_id": company_id,
        "customer_id": customer_id,
        "contract": contract,
        "invoice": invoice,
        "sales_invoice_id": sales_invoice_id,
        "schedule_version": version,
        "schedule_lines": lines,
        "bank_account": bank_account,
        "late_fee_account": late_fee_account,
        "ar_account": ar_account,
        "revenue_account": revenue_account,
        "today": today,
    }

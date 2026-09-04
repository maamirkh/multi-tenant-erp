"""[Epic 10, Phase 14 — Exit Gate gap-closure, plan.md §19] Real-Postgres
concurrency test — duplicate activation race. Named explicitly in
plan.md §19's race table ("Same contract-row lock + `_LEGAL_TRANSITIONS`
guard under the lock (`APPROVED -> ACTIVE` only)") but not assigned its
own dedicated row-lock race test by any earlier phase or by tasks.md's
literal T236-T241 enumeration — `test_idempotency_concurrency.py`
(T089-T091) proves the idempotency-KEY layer's protection using
"contract.activate" only as a generic operation-name placeholder, never
racing two concurrent `activate()` calls with DIFFERENT idempotency
keys against the SAME contract's `FOR UPDATE` lock, which is the
distinct protection layer plan.md §19's row actually names. Phase 14's
own stated Purpose — "closing any remaining gap" — and its Exit Gate's
"every critical race named in plan.md §19/§31" both require this
be proven before the phase can close, so it is added here rather than
left for a future phase to rediscover as a correction pass.

Two different idempotency keys deliberately isolate the proof to the
`FOR UPDATE` lock alone (mirroring `test_settlement_concurrency.py`'s
own documented technique): distinct keys never conflict with each other
at the reservation step, so if the race is correctly resolved, only the
row lock can be doing it.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
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
from modules.installments.exceptions import InstallmentIllegalTransitionError
from modules.installments.models.contract import InstallmentContract
from modules.installments.models.schedule import InstallmentScheduleVersion
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.repositories.sequence import InstallmentSequenceRepository
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.contract_service import InstallmentContractService
from modules.installments.services.idempotency_service import (
    InstallmentIdempotencyService,
)
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)

_REPETITIONS = 5


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


@dataclass
class _FakeConfig:
    rounding_policy: str = "ROUND_HALF_UP"


class _NoOpEligibilityService:
    def check_invoice_eligibility(self, company_id, sales_invoice_id):
        return None


class _FakeConfigurationService:
    def get_effective_config(self, company_id, branch_id=None):
        return _FakeConfig()


def _build_approved_contract(db_session, *, installment_count: int = 2) -> dict:
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
    BankAccountRepository(db_session).create(
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
    installment_amount = Decimal("100.00")
    contractual_total = installment_amount * installment_count
    sales_invoice_id = uuid.uuid4()
    ar_service.record_sales_invoice(
        company_id=company_id,
        customer_id=customer_id,
        invoice_id=sales_invoice_id,
        invoice_number=f"INV-{uuid.uuid4().hex[:8]}",
        total_amount=contractual_total,
        currency_code="USD",
        transaction_date=today,
        due_date=today,
        actor_id=None,
    )

    contract = InstallmentContractRepository(db_session).create(
        InstallmentContract(
            company_id=company_id,
            contract_number=f"IC-{uuid.uuid4().hex[:8]}",
            customer_id=customer_id,
            sales_invoice_id=sales_invoice_id,
            contract_date=today,
            principal_amount=contractual_total,
            down_payment_amount=Decimal("0"),
            markup_amount=Decimal("0"),
            contractual_total=contractual_total,
            installment_count=installment_count,
            frequency="MONTHLY",
            first_due_date=today,
            maturity_date=today,
            currency_code="USD",
            status="APPROVED",
            terms_snapshot={"note": "Phase 14 activation-race fixture"},
        )
    )

    return {"company_id": company_id, "customer_id": customer_id, "contract": contract}


def _build_contract_service(session) -> InstallmentContractService:
    ar_service = build_ar_service(session, with_sales_sync=False)
    payment_service = build_payment_service(session)
    allocation_engine = build_allocation_engine(session)
    gateway = AccountingIntegrationGateway(
        ar_service=ar_service,
        payment_service=payment_service,
        allocation_engine=allocation_engine,
    )
    return InstallmentContractService(
        repo=InstallmentContractRepository(session),
        sequence_repo=InstallmentSequenceRepository(session),
        eligibility_service=_NoOpEligibilityService(),
        accounting_gateway=gateway,
        configuration_service=_FakeConfigurationService(),
        audit_service=InstallmentAuditService(
            db=session, audit_repo=InstallmentAuditLogRepository(session)
        ),
        schedule_repo=InstallmentScheduleRepository(session),
        idempotency_service=InstallmentIdempotencyService(session),
        outbox_repo=EventOutboxRepository(session),
    )


class TestDuplicateActivationRaceAtScale:
    def test_five_repetitions_exactly_one_activation_succeeds(
        self, db_session, pg_engine
    ) -> None:
        session_factory = sessionmaker(bind=pg_engine)

        for rep in range(_REPETITIONS):
            ctx = _build_approved_contract(db_session, installment_count=3)
            company_id = ctx["company_id"]
            contract_id = ctx["contract"].id

            session_a = session_factory()
            session_b = session_factory()
            results: dict[str, object] = {}

            def _activate(label: str, session) -> None:
                try:
                    svc = _build_contract_service(session)
                    updated = svc.activate(
                        company_id,
                        contract_id,
                        idempotency_key=str(uuid.uuid4()),
                        actor_id=None,
                    )
                    results[label] = ("success", updated.status)
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    results[label] = ("error", exc)

            thread_a = threading.Thread(target=_activate, args=("a", session_a))
            thread_b = threading.Thread(target=_activate, args=("b", session_b))
            thread_a.start()
            thread_b.start()
            thread_a.join(timeout=30)
            thread_b.join(timeout=30)
            session_a.close()
            session_b.close()

            outcomes = [results["a"][0], results["b"][0]]
            assert outcomes.count("success") == 1, f"repetition {rep}: {results}"
            assert outcomes.count("error") == 1, f"repetition {rep}: {results}"

            loser_label = "a" if results["a"][0] == "error" else "b"
            assert isinstance(
                results[loser_label][1], InstallmentIllegalTransitionError
            ), f"repetition {rep}: {results}"

            verify_session = session_factory()
            try:
                refreshed = verify_session.get(InstallmentContract, contract_id)
                assert refreshed.status == "ACTIVE", f"repetition {rep}"

                versions = (
                    verify_session.execute(
                        select(InstallmentScheduleVersion).where(
                            InstallmentScheduleVersion.company_id == company_id,
                            InstallmentScheduleVersion.contract_id == contract_id,
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(versions) == 1, (
                    f"repetition {rep}: expected exactly 1 schedule version, "
                    f"found {len(versions)} (a second activation would have "
                    f"generated a duplicate schedule)"
                )
            finally:
                verify_session.close()

"""[Epic 10, Phase 7, T124] Service tests for
``InstallmentContractService.activate()`` — down payment collection,
schedule generation/persistence, BR-INST-005 reconciliation, and the
frozen commit-ownership sequence (plan.md §21's Activation row).

Real Postgres (schedule tables require it). Uses a fake, duck-typed
``eligibility_service``/``configuration_service`` (mirroring
``test_contract_creation.py``'s established convention for
``create_draft()`` tests) so these tests exercise
``InstallmentContractService.activate()``'s own orchestration logic
without needing a real ``modules.sales`` invoice/customer row — live
Sales-gateway wiring was already proven for ``create_draft()`` by T053
(real Postgres) and is not re-proven per-method here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, cast

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
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.repositories.sequence import InstallmentSequenceRepository
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.configuration_service import (
    InstallmentConfigurationService,
)
from modules.installments.services.contract_service import InstallmentContractService
from modules.installments.services.eligibility_service import (
    InstallmentEligibilityService,
)
from modules.installments.services.idempotency_service import (
    InstallmentIdempotencyService,
)


@dataclass
class _FakeConfig:
    rounding_policy: str = "ROUND_HALF_UP"


class _NoOpEligibilityService:
    def check_invoice_eligibility(self, company_id, sales_invoice_id):
        return None


class _FakeConfigurationService:
    def get_effective_config(self, company_id, branch_id=None):
        return _FakeConfig()


def _build_approved_contract(
    db_session,
    *,
    installment_count: int = 2,
    down_payment_amount: Decimal = Decimal("0"),
) -> dict[str, Any]:
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
    installment_amount = Decimal("100.00")
    contractual_total = installment_amount * installment_count
    invoice_total = contractual_total + down_payment_amount
    sales_invoice_id = uuid.uuid4()
    ar_service.record_sales_invoice(
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
        status="APPROVED",
        terms_snapshot={"note": "T124 activation-test fixture"},
    )
    contract = contract_repo.create(contract)

    return {
        "company_id": company_id,
        "customer_id": customer_id,
        "contract": contract,
        "bank_account": bank_account,
        "today": today,
    }


def _build_contract_service(db_session) -> InstallmentContractService:
    ar_service = build_ar_service(db_session, with_sales_sync=False)
    payment_service = build_payment_service(db_session)
    allocation_engine = build_allocation_engine(db_session)
    gateway = AccountingIntegrationGateway(
        ar_service=ar_service,
        payment_service=payment_service,
        allocation_engine=allocation_engine,
    )
    audit_service = InstallmentAuditService(
        db=db_session, audit_repo=InstallmentAuditLogRepository(db_session)
    )
    return InstallmentContractService(
        repo=InstallmentContractRepository(db_session),
        sequence_repo=InstallmentSequenceRepository(db_session),
        eligibility_service=cast(
            InstallmentEligibilityService, _NoOpEligibilityService()
        ),
        accounting_gateway=gateway,
        configuration_service=cast(
            InstallmentConfigurationService, _FakeConfigurationService()
        ),
        audit_service=audit_service,
        schedule_repo=InstallmentScheduleRepository(db_session),
        idempotency_service=InstallmentIdempotencyService(db_session),
        outbox_repo=EventOutboxRepository(db_session),
    )


class TestActivateContract:
    def test_activate_without_down_payment_generates_schedule_and_commits(
        self, db_session
    ) -> None:
        ctx = _build_approved_contract(
            db_session, installment_count=3, down_payment_amount=Decimal("0")
        )
        service = _build_contract_service(db_session)

        activated = service.activate(
            ctx["company_id"],
            ctx["contract"].id,
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )

        assert activated.status == "ACTIVE"
        assert activated.activated_at is not None
        assert activated.active_schedule_version_id is not None

        schedule_repo = InstallmentScheduleRepository(db_session)
        version = schedule_repo.get_active_version(
            ctx["company_id"], ctx["contract"].id
        )
        assert version is not None
        lines = schedule_repo.get_lines(ctx["company_id"], version.id)
        assert len(lines) == 3
        assert sum(line.scheduled_amount for line in lines) == Decimal("300.00")

    def test_activate_with_down_payment_posts_to_accounting_and_reduces_outstanding(
        self, db_session
    ) -> None:
        ctx = _build_approved_contract(
            db_session, installment_count=2, down_payment_amount=Decimal("50.00")
        )
        service = _build_contract_service(db_session)

        activated = service.activate(
            ctx["company_id"],
            ctx["contract"].id,
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        assert activated.status == "ACTIVE"

        ar_service = build_ar_service(db_session, with_sales_sync=False)
        invoice = ar_service.find_transaction_by_source_document(
            ctx["company_id"], "SalesInvoice", ctx["contract"].sales_invoice_id
        )
        assert invoice is not None
        # invoice_total (250) - down payment (50) = 200 remaining,
        # matching the contract's own contractual_total (2 x 100).
        assert invoice.outstanding_amount == Decimal("200.00")

    def test_activate_is_idempotent_on_replay(self, db_session) -> None:
        ctx = _build_approved_contract(
            db_session, installment_count=1, down_payment_amount=Decimal("0")
        )
        service = _build_contract_service(db_session)
        key = str(uuid.uuid4())

        first = service.activate(
            ctx["company_id"], ctx["contract"].id, idempotency_key=key, actor_id=None
        )
        second = service.activate(
            ctx["company_id"], ctx["contract"].id, idempotency_key=key, actor_id=None
        )

        assert first.status == "ACTIVE"
        assert second.status == "ACTIVE"
        assert first.id == second.id

        schedule_repo = InstallmentScheduleRepository(db_session)
        version = schedule_repo.get_active_version(
            ctx["company_id"], ctx["contract"].id
        )
        assert version is not None
        lines = schedule_repo.get_lines(ctx["company_id"], version.id)
        # Replay must not generate a second schedule version/duplicate lines.
        assert len(lines) == 1

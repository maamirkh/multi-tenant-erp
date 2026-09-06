"""Integration tests for FX settlement — Phase 12 (US12 Independent Test).

"A EUR invoice is raised at rate 1.10; payment received at rate 1.15; system
automatically posts a realized FX gain of (1.15 - 1.10) * invoice_amount."
(tasks.md Phase 12 Story Goal). Realized FX gain/loss itself was built in
Phase 10 (``AllocationEngine``) — these tests exercise it end-to-end through
the full AR/AP settlement flow with control-account reconciliation, the
level of coverage tasks.md T254 asks for specifically for this phase.

Spec ref: specs/008-accounting-finance/tasks.md T254
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_payment_service
from modules.accounting.models.ap import APTransaction, SupplierLedger
from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.accounting.models.banking import BankAccount
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.repositories.ap import (
    APTransactionRepository,
    SupplierLedgerRepository,
)
from modules.accounting.repositories.ar import (
    ARTransactionRepository,
    CustomerLedgerRepository,
)
from modules.accounting.repositories.banking import BankAccountRepository
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import (
    AccountingAuditLogRepository,
    GLReportRepository,
)
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
    ap = account_repo.create(
        Account(
            company_id=company_id,
            account_code="2000",
            account_name="AP",
            account_type="LIABILITY",
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
    exchange_gain = account_repo.create(
        Account(
            company_id=company_id,
            account_code="7100",
            account_name="Realized Exchange Gain",
            account_type="REVENUE",
        )
    )
    exchange_loss = account_repo.create(
        Account(
            company_id=company_id,
            account_code="8100",
            account_name="Realized Exchange Loss",
            account_type="EXPENSE",
        )
    )
    bank = BankAccountRepository(db_session).create(
        BankAccount(
            company_id=company_id,
            bank_name="Test Bank",
            account_number="ACC-EUR-0001",
            currency_code="EUR",
            gl_account_id=bank_gl.id,
        )
    )

    AccountingConfigurationRepository(db_session).create(
        AccountingConfiguration(
            company_id=company_id,
            base_currency_code="USD",
            default_ar_account_id=ar.id,
            default_ap_account_id=ap.id,
            default_exchange_gain_account_id=exchange_gain.id,
            default_exchange_loss_account_id=exchange_loss.id,
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

    return {
        "company_id": company_id,
        "ar": ar,
        "ap": ap,
        "bank": bank,
        "exchange_gain": exchange_gain,
        "exchange_loss": exchange_loss,
        "today": today,
    }


@pytest.fixture
def payment_service(db_session: Session) -> PaymentService:
    return build_payment_service(db_session)


def _make_ar_invoice(
    db_session: Session, setup: dict, amount: Decimal, rate: Decimal
) -> ARTransaction:
    ledger = CustomerLedgerRepository(db_session).create(
        CustomerLedger(company_id=setup["company_id"], customer_id=uuid4())
    )
    return ARTransactionRepository(db_session).create(
        ARTransaction(
            company_id=setup["company_id"],
            customer_ledger_id=ledger.id,
            transaction_type="INVOICE",
            transaction_date=setup["today"],
            currency_code="EUR",
            exchange_rate=rate,
            amount_foreign=amount,
            amount_base=amount * rate,
            outstanding_amount=amount * rate,
            status="OPEN",
            invoice_number=f"INV-{uuid4().hex[:6]}",
        )
    )


def _make_ap_bill(
    db_session: Session, setup: dict, amount: Decimal, rate: Decimal
) -> APTransaction:
    ledger = SupplierLedgerRepository(db_session).create(
        SupplierLedger(company_id=setup["company_id"], supplier_id=uuid4())
    )
    return APTransactionRepository(db_session).create(
        APTransaction(
            company_id=setup["company_id"],
            supplier_ledger_id=ledger.id,
            transaction_type="BILL",
            transaction_date=setup["today"],
            currency_code="EUR",
            exchange_rate=rate,
            amount_foreign=amount,
            amount_base=amount * rate,
            outstanding_amount=amount * rate,
            status="OPEN",
            bill_number=f"BILL-{uuid4().hex[:6]}",
        )
    )


class TestARFXSettlementGain:
    def test_eur_invoice_booked_at_1_10_settled_at_1_15_posts_realized_gain(
        self, payment_service: PaymentService, setup: dict
    ) -> None:
        invoice = _make_ar_invoice(
            payment_service.db, setup, amount=Decimal("1000.00"), rate=Decimal("1.10")
        )

        payment, _ = payment_service.create_customer_payment(
            company_id=setup["company_id"],
            customer_id=uuid4(),
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("1000.00"),
            currency_code="EUR",
            exchange_rate=Decimal("1.15"),
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        lines = payment_service.allocate_payment(
            company_id=setup["company_id"],
            payment_id=payment.id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("1000.00")}
            ],
            actor_id=None,
        )

        assert lines[0].gain_loss_amount == Decimal("50.00")
        assert lines[0].gain_loss_journal_entry_id is not None

        ar_repo = ARTransactionRepository(payment_service.db)
        refreshed_invoice = ar_repo.get_by_id_or_none(
            id=invoice.id, company_id=setup["company_id"]
        )
        assert refreshed_invoice.outstanding_amount == Decimal("0")
        assert refreshed_invoice.status == "PAID"

        gl_reports = GLReportRepository(payment_service.db)
        gain_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["exchange_gain"].id
        )
        assert gain_balance["total_credit"] - gain_balance["total_debit"] == Decimal(
            "50.00"
        )


class TestAPFXSettlementLoss:
    def test_eur_bill_booked_at_1_10_settled_at_1_15_posts_realized_loss(
        self, payment_service: PaymentService, setup: dict
    ) -> None:
        bill = _make_ap_bill(
            payment_service.db, setup, amount=Decimal("1000.00"), rate=Decimal("1.10")
        )

        payment, _ = payment_service.create_supplier_payment(
            company_id=setup["company_id"],
            supplier_id=uuid4(),
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("1000.00"),
            currency_code="EUR",
            exchange_rate=Decimal("1.15"),
            bank_account_id=setup["bank"].id,
            actor_id=None,
        )

        lines = payment_service.allocate_payment(
            company_id=setup["company_id"],
            payment_id=payment.id,
            allocation_lines=[
                {"transaction_id": bill.id, "amount_foreign": Decimal("1000.00")}
            ],
            actor_id=None,
        )

        # AP booked at 1.10, settled at the higher rate 1.15 -> costs more
        # base currency to pay off -> a loss.
        assert lines[0].gain_loss_amount == Decimal("-50.00")
        assert lines[0].gain_loss_journal_entry_id is not None

        ap_repo = APTransactionRepository(payment_service.db)
        refreshed_bill = ap_repo.get_by_id_or_none(
            id=bill.id, company_id=setup["company_id"]
        )
        assert refreshed_bill.outstanding_amount == Decimal("0")
        assert refreshed_bill.status == "PAID"

        gl_reports = GLReportRepository(payment_service.db)
        loss_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["exchange_loss"].id
        )
        assert loss_balance["total_debit"] - loss_balance["total_credit"] == Decimal(
            "50.00"
        )

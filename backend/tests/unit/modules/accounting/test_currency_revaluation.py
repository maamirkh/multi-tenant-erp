"""Unit tests for CurrencyRevaluationService — Phase 12.

Tests (tasks.md T253) — the phase's own Independent Test, literally:
  - EUR invoice booked at rate 1.10, revalued at rate 1.15 -> unrealized
    gain = 0.05 * outstanding amount; revaluation creates the correct GL entry
  - EUR bill (AP) booked at rate 1.15, revalued at rate 1.10 -> unrealized
    gain for the payable (liability decreased in base-currency terms)
  - A transaction in the base currency is never revalued
  - A fully-settled (outstanding = 0) transaction is skipped
  - Running with no open foreign-currency exposure posts nothing

Spec ref: specs/008-accounting-finance/tasks.md T253
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_currency_revaluation_service
from modules.accounting.events import (
    AccountingDomainEvent,
    InProcessEventBus,
    set_event_bus,
)
from modules.accounting.exceptions import FiscalPeriodNotFoundError
from modules.accounting.models.ap import APTransaction, SupplierLedger
from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.repositories.ap import SupplierLedgerRepository
from modules.accounting.repositories.ar import (
    ARTransactionRepository,
    CustomerLedgerRepository,
)
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
from modules.accounting.services.currency_revaluation_service import (
    CurrencyRevaluationService,
)
from modules.accounting.services.currency_service import CurrencyService
from modules.accounting.services.fiscal_service import FiscalCalendarService


@pytest.fixture
def fresh_accounting_bus() -> InProcessEventBus:
    """A clean, isolated event bus for this test — mirrors the established
    pattern in test_credit_hold.py (module-level singleton swap so published
    events can be captured deterministically).
    """
    bus = InProcessEventBus()
    set_event_bus(bus)
    return bus


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
    exchange_gain = account_repo.create(
        Account(
            company_id=company_id,
            account_code="7100",
            account_name="Unrealized Exchange Gain",
            account_type="REVENUE",
        )
    )
    exchange_loss = account_repo.create(
        Account(
            company_id=company_id,
            account_code="8100",
            account_name="Unrealized Exchange Loss",
            account_type="EXPENSE",
        )
    )

    today = date.today()
    fiscal_year = fiscal_service.create_fiscal_year(
        company_id,
        f"FY-{uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )
    periods = fiscal_service.list_periods(company_id, fiscal_year.id)
    period = next(p for p in periods if p.start_date <= today <= p.end_date)

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

    return {
        "company_id": company_id,
        "ar": ar,
        "ap": ap,
        "exchange_gain": exchange_gain,
        "exchange_loss": exchange_loss,
        "period": period,
        "today": today,
    }


@pytest.fixture
def service(db_session: Session) -> CurrencyRevaluationService:
    return build_currency_revaluation_service(db_session)


@pytest.fixture
def currency_service(db_session: Session) -> CurrencyService:
    from modules.accounting.repositories.foundation import (
        CurrencyRepository,
        ExchangeRateRepository,
    )

    return CurrencyService(
        db=db_session,
        currency_repo=CurrencyRepository(db_session),
        exchange_rate_repo=ExchangeRateRepository(db_session),
    )


def _make_ar_invoice(
    db_session: Session,
    setup: dict,
    amount_foreign: Decimal,
    exchange_rate: Decimal,
    currency_code: str,
) -> ARTransaction:
    ledger = CustomerLedgerRepository(db_session).create(
        CustomerLedger(company_id=setup["company_id"], customer_id=uuid4())
    )
    amount_base = amount_foreign * exchange_rate
    return ARTransactionRepository(db_session).create(
        ARTransaction(
            company_id=setup["company_id"],
            customer_ledger_id=ledger.id,
            transaction_type="INVOICE",
            transaction_date=setup["today"],
            currency_code=currency_code,
            exchange_rate=exchange_rate,
            amount_foreign=amount_foreign,
            amount_base=amount_base,
            outstanding_amount=amount_base,
            status="OPEN",
            invoice_number=f"INV-{uuid4().hex[:6]}",
        )
    )


def _make_ap_bill(
    db_session: Session,
    setup: dict,
    amount_foreign: Decimal,
    exchange_rate: Decimal,
    currency_code: str,
) -> APTransaction:
    from modules.accounting.repositories.ap import APTransactionRepository

    ledger = SupplierLedgerRepository(db_session).create(
        SupplierLedger(company_id=setup["company_id"], supplier_id=uuid4())
    )
    amount_base = amount_foreign * exchange_rate
    return APTransactionRepository(db_session).create(
        APTransaction(
            company_id=setup["company_id"],
            supplier_ledger_id=ledger.id,
            transaction_type="BILL",
            transaction_date=setup["today"],
            currency_code=currency_code,
            exchange_rate=exchange_rate,
            amount_foreign=amount_foreign,
            amount_base=amount_base,
            outstanding_amount=amount_base,
            status="OPEN",
            bill_number=f"BILL-{uuid4().hex[:6]}",
        )
    )


class TestARRevaluationGain:
    def test_eur_invoice_at_1_10_revalued_at_1_15_is_a_gain(
        self,
        service: CurrencyRevaluationService,
        currency_service: CurrencyService,
        setup: dict,
    ) -> None:
        invoice = _make_ar_invoice(
            service.db,
            setup,
            amount_foreign=Decimal("1000.00"),
            exchange_rate=Decimal("1.10"),
            currency_code="EUR",
        )
        currency_service.set_exchange_rate(
            setup["company_id"], "EUR", "USD", setup["today"], Decimal("1.15")
        )

        run = service.run_revaluation(
            company_id=setup["company_id"],
            period_id=setup["period"].id,
            revaluation_date=setup["today"],
        )

        assert run.total_unrealized_gain_base == Decimal("50.00")
        assert run.total_unrealized_loss_base == Decimal("0")
        assert run.net_gain_loss_base == Decimal("50.00")
        assert run.journal_entry_id is not None

        # Regression: 1100.00 / 1.10 == 1000 exactly, and Python's Decimal
        # normalizes such an exact quotient to scientific notation
        # ("1E+3") — caught via live PostgreSQL/API verification, where the
        # unquantized string was persisted into the JSONB `lines` column and
        # echoed back verbatim in the API response instead of "1000.000000".
        assert run.lines[0]["outstanding_foreign"] == "1000.000000"
        assert "E" not in run.lines[0]["outstanding_foreign"]
        assert run.lines[0]["booking_rate"] == "1.1000000000"
        assert run.lines[0]["current_rate"] == "1.1500000000"
        assert len(run.lines) == 1
        assert run.lines[0]["transaction_id"] == str(invoice.id)
        assert Decimal(run.lines[0]["gain_loss_amount"]) == Decimal("50.00")

        gl_reports = GLReportRepository(service.db)
        gain_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["exchange_gain"].id
        )
        assert gain_balance["total_credit"] - gain_balance["total_debit"] == Decimal(
            "50.00"
        )

        ar_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["ar"].id
        )
        assert ar_balance["total_debit"] - ar_balance["total_credit"] == Decimal(
            "50.00"
        )


class TestAPRevaluationGain:
    def test_eur_bill_at_1_15_revalued_at_1_10_is_a_gain_for_ap(
        self,
        service: CurrencyRevaluationService,
        currency_service: CurrencyService,
        setup: dict,
    ) -> None:
        _make_ap_bill(
            service.db,
            setup,
            amount_foreign=Decimal("1000.00"),
            exchange_rate=Decimal("1.15"),
            currency_code="EUR",
        )
        currency_service.set_exchange_rate(
            setup["company_id"], "EUR", "USD", setup["today"], Decimal("1.10")
        )

        run = service.run_revaluation(
            company_id=setup["company_id"],
            period_id=setup["period"].id,
            revaluation_date=setup["today"],
        )

        # Liability booked at 1.15, now worth less at 1.10 -> gain for the payer.
        assert run.total_unrealized_gain_base == Decimal("50.00")
        assert run.total_unrealized_loss_base == Decimal("0")

        gl_reports = GLReportRepository(service.db)
        ap_balance = gl_reports.account_balance_query(
            company_id=setup["company_id"], account_id=setup["ap"].id
        )
        # AP control is credit-normal; a gain reduces the liability -> net debit.
        assert ap_balance["total_debit"] - ap_balance["total_credit"] == Decimal(
            "50.00"
        )


class TestNoRevaluationNeeded:
    def test_base_currency_transaction_is_never_revalued(
        self, service: CurrencyRevaluationService, setup: dict
    ) -> None:
        _make_ar_invoice(
            service.db,
            setup,
            amount_foreign=Decimal("500.00"),
            exchange_rate=Decimal("1"),
            currency_code="USD",
        )

        run = service.run_revaluation(
            company_id=setup["company_id"],
            period_id=setup["period"].id,
            revaluation_date=setup["today"],
        )

        assert run.net_gain_loss_base == Decimal("0")
        assert run.journal_entry_id is None
        assert run.lines == []

    def test_settled_transaction_is_skipped(
        self,
        service: CurrencyRevaluationService,
        currency_service: CurrencyService,
        setup: dict,
    ) -> None:
        invoice = _make_ar_invoice(
            service.db,
            setup,
            amount_foreign=Decimal("200.00"),
            exchange_rate=Decimal("1.10"),
            currency_code="EUR",
        )
        invoice.outstanding_amount = Decimal("0")
        service.db.add(invoice)
        service.db.commit()

        currency_service.set_exchange_rate(
            setup["company_id"], "EUR", "USD", setup["today"], Decimal("1.20")
        )

        run = service.run_revaluation(
            company_id=setup["company_id"],
            period_id=setup["period"].id,
            revaluation_date=setup["today"],
        )

        assert run.lines == []
        assert run.journal_entry_id is None


class TestInvalidPeriod:
    def test_unknown_period_id_raises(
        self, service: CurrencyRevaluationService, setup: dict
    ) -> None:
        with pytest.raises(FiscalPeriodNotFoundError):
            service.run_revaluation(
                company_id=setup["company_id"],
                period_id=uuid4(),
                revaluation_date=setup["today"],
            )


class TestRevaluationCompletedEvent:
    """T249 — ``accounting.revaluation.completed`` must be published on
    completion. Live PostgreSQL/Docker verification confirmed the journal
    entry and API response are correct, but publish/subscribe is only
    observable in-process (no subscriber is wired up in this Epic yet — see
    module docstring in events/__init__.py: "future message-broker
    implementation" placeholder) — this test captures the event directly,
    mirroring the established ``fresh_accounting_bus`` pattern from
    test_credit_hold.py.
    """

    def test_publishes_event_with_correct_payload_on_completion(
        self,
        service: CurrencyRevaluationService,
        currency_service: CurrencyService,
        fresh_accounting_bus: InProcessEventBus,
        setup: dict,
    ) -> None:
        _make_ar_invoice(
            service.db,
            setup,
            amount_foreign=Decimal("1000.00"),
            exchange_rate=Decimal("1.10"),
            currency_code="EUR",
        )
        currency_service.set_exchange_rate(
            setup["company_id"], "EUR", "USD", setup["today"], Decimal("1.15")
        )

        received: list[AccountingDomainEvent] = []
        fresh_accounting_bus.subscribe(
            "accounting.revaluation.completed", lambda e: received.append(e)
        )

        run = service.run_revaluation(
            company_id=setup["company_id"],
            period_id=setup["period"].id,
            revaluation_date=setup["today"],
        )

        assert len(received) == 1
        event = received[0]
        assert event.company_id == setup["company_id"]
        assert event.aggregate_type == "CurrencyRevaluationRun"
        assert event.aggregate_id == run.id
        assert event.fiscal_period_id == setup["period"].id
        assert event.revaluation_date == setup["today"].isoformat()
        assert event.currencies_revalued == ["EUR"]
        assert event.total_unrealized_gain_base == Decimal("50.00")
        assert event.total_unrealized_loss_base == Decimal("0")
        assert event.net_gain_loss_base == Decimal("50.00")
        assert event.journal_entry_id == run.journal_entry_id

    def test_publishes_event_even_when_nothing_to_post(
        self,
        service: CurrencyRevaluationService,
        fresh_accounting_bus: InProcessEventBus,
        setup: dict,
    ) -> None:
        received: list[AccountingDomainEvent] = []
        fresh_accounting_bus.subscribe(
            "accounting.revaluation.completed", lambda e: received.append(e)
        )

        run = service.run_revaluation(
            company_id=setup["company_id"],
            period_id=setup["period"].id,
            revaluation_date=setup["today"],
        )

        assert len(received) == 1
        assert received[0].journal_entry_id is None
        assert run.journal_entry_id is None

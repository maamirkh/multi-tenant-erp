"""Integration tests for the 8 inbound integration event handlers — Phase 4/6.

Per the module docstring in ``handlers/integration_handlers.py`` and
quickstart.md's "Phase 0 Verification Findings", only 2 of the 8 handlers
named in tasks.md T099 have a real, live event to respond to today
(Sales invoice issued / credit note issued). The other 6 are documented
stubs — this test file verifies that honestly:
  - The 2 live handlers, given a real event, create the correct balanced
    GL entry AND the correct ``ARTransaction`` in the customer's ledger,
    atomically (Phase 6, T141/T142).
  - The 6 stub handlers accept a call without raising and create no GL
    entry — proving they are safe no-ops, not silently broken integrations.

Spec ref: specs/008-accounting-finance/tasks.md T113, T141, T142
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.accounting.handlers import integration_handlers as handlers
from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.accounting.models.coa import Account
from modules.accounting.models.gl import JournalEntry, JournalLine
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
from modules.sales.events.invoice_events import InvoiceCreditNoteIssued, InvoiceIssued


def _setup_company_for_gl(db_session: Session) -> dict[str, Any]:
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

    config_repo = AccountingConfigurationRepository(db_session)
    from modules.accounting.models.foundation import AccountingConfiguration

    config_repo.create(
        AccountingConfiguration(
            company_id=company_id,
            default_ar_account_id=ar.id,
            default_revenue_account_id=revenue.id,
        )
    )
    return {"company_id": company_id, "ar": ar, "revenue": revenue}


class TestLiveSalesInvoiceHandler:
    def test_handle_sales_invoice_posted_creates_balanced_gl_entry(
        self, db_session: Session, monkeypatch
    ) -> None:
        setup = _setup_company_for_gl(db_session)
        ar_id, revenue_id = setup["ar"].id, setup["revenue"].id
        monkeypatch.setattr(handlers, "SessionLocal", lambda: db_session)
        monkeypatch.setattr(
            "modules.accounting.dependencies.SessionLocal",
            lambda: db_session,
            raising=False,
        )

        customer_id = uuid4()
        event = InvoiceIssued(
            aggregate_id=uuid4(),
            company_id=setup["company_id"],
            invoice_id=uuid4(),
            invoice_number="INV-0001",
            customer_id=str(customer_id),
            due_date=date.today().isoformat(),
            total_amount="1500.00",
            currency_code="USD",
            issued_by=str(uuid4()),
        )
        handlers.handle_sales_invoice_posted(event)

        entries = list(
            db_session.execute(
                select(JournalEntry).where(
                    JournalEntry.company_id == setup["company_id"],
                    JournalEntry.source_document_id == event.invoice_id,
                )
            )
            .scalars()
            .all()
        )
        assert len(entries) == 1
        entry = entries[0]
        assert entry.status == "POSTED"
        assert entry.total_debit_base == entry.total_credit_base == Decimal("1500.00")

        lines = list(
            db_session.execute(
                select(JournalLine).where(JournalLine.journal_entry_id == entry.id)
            )
            .scalars()
            .all()
        )
        debit_line = next(line for line in lines if line.debit_amount > 0)
        credit_line = next(line for line in lines if line.credit_amount > 0)
        assert debit_line.account_id == ar_id
        assert credit_line.account_id == revenue_id

        ledger = db_session.execute(
            select(CustomerLedger).where(
                CustomerLedger.company_id == setup["company_id"],
                CustomerLedger.customer_id == customer_id,
            )
        ).scalar_one()
        assert ledger.total_outstanding_base == Decimal("1500.00")

        ar_txn = db_session.execute(
            select(ARTransaction).where(ARTransaction.customer_ledger_id == ledger.id)
        ).scalar_one()
        assert ar_txn.transaction_type == "INVOICE"
        assert ar_txn.status == "OPEN"
        assert ar_txn.outstanding_amount == Decimal("1500.00")
        assert ar_txn.journal_entry_id == entry.id
        assert ar_txn.invoice_number == "INV-0001"

    def test_handle_sales_credit_note_posted_reverses_correctly(
        self, db_session: Session, monkeypatch
    ) -> None:
        setup = _setup_company_for_gl(db_session)
        ar_id, revenue_id = setup["ar"].id, setup["revenue"].id
        monkeypatch.setattr(handlers, "SessionLocal", lambda: db_session)

        customer_id = uuid4()
        event = InvoiceCreditNoteIssued(
            aggregate_id=uuid4(),
            company_id=setup["company_id"],
            invoice_id=uuid4(),
            invoice_number="INV-0002",
            customer_id=str(customer_id),
            credit_note_amount="200.00",
            issued_by=str(uuid4()),
        )
        handlers.handle_sales_credit_note_posted(event)

        entries = list(
            db_session.execute(
                select(JournalEntry).where(
                    JournalEntry.company_id == setup["company_id"],
                    JournalEntry.source_document_id == event.invoice_id,
                )
            )
            .scalars()
            .all()
        )
        assert len(entries) == 1
        entry = entries[0]
        assert entry.total_debit_base == entry.total_credit_base == Decimal("200.00")

        lines = list(
            db_session.execute(
                select(JournalLine).where(JournalLine.journal_entry_id == entry.id)
            )
            .scalars()
            .all()
        )
        debit_line = next(line for line in lines if line.debit_amount > 0)
        credit_line = next(line for line in lines if line.credit_amount > 0)
        assert debit_line.account_id == revenue_id
        assert credit_line.account_id == ar_id

        ledger = db_session.execute(
            select(CustomerLedger).where(
                CustomerLedger.company_id == setup["company_id"],
                CustomerLedger.customer_id == customer_id,
            )
        ).scalar_one()
        assert ledger.total_outstanding_base == Decimal("-200.00")

        ar_txn = db_session.execute(
            select(ARTransaction).where(ARTransaction.customer_ledger_id == ledger.id)
        ).scalar_one()
        assert ar_txn.transaction_type == "CREDIT_NOTE"
        assert ar_txn.outstanding_amount == Decimal("-200.00")
        assert ar_txn.journal_entry_id == entry.id


class TestStubHandlersAreSafeNoOps:
    def test_all_six_stubs_accept_a_call_without_raising_and_create_no_gl_entry(
        self, db_session: Session
    ) -> None:
        before_count = db_session.execute(select(JournalEntry)).scalars().all()

        for stub in (
            handlers.handle_purchase_bill_posted,
            handlers.handle_purchase_credit_note_posted,
            handlers.handle_inventory_adjustment_posted,
            handlers.handle_inventory_cost_updated,
            handlers.handle_sales_payment_received,
            handlers.handle_supplier_payment_made,
        ):
            stub(object())  # arbitrary placeholder event — stubs never inspect it

        after_count = db_session.execute(select(JournalEntry)).scalars().all()
        assert len(after_count) == len(before_count)


class TestRegisterIntegrationHandlers:
    def test_registers_exactly_two_subscriptions_on_sales_bus(self) -> None:
        from modules.sales.events import InProcessEventBus as SalesInProcessEventBus
        from modules.sales.events import set_event_bus as set_sales_event_bus

        fresh_bus = SalesInProcessEventBus()
        set_sales_event_bus(fresh_bus)

        handlers.register_integration_handlers()

        assert fresh_bus.handler_count("sales.invoice.issued") == 1
        assert fresh_bus.handler_count("sales.invoice.credit_note_issued") == 1

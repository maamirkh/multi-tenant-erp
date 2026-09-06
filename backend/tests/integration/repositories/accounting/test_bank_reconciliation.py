"""Integration tests for bank reconciliation — Phase 8.

Tests (tasks.md T190) — the phase's own Independent Test, literally:
  - Import 100 bank statement lines -> run auto-match -> verify matched count
  - Complete reconciliation -> verify statement_balance == GL_balance
  - Lock reconciliation -> verify no further modifications allowed

Also covers bank transfer atomicity (two-leg balanced journal) and the
cheque status state machine, since both are exercised via
``BankAccountService`` alongside the reconciliation workflow.

Spec ref: specs/008-accounting-finance/tasks.md T190
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import (
    build_bank_account_service,
    build_bank_reconciliation_service,
)
from modules.accounting.exceptions import (
    ReconciliationLockedError,
    ReconciliationNotBalancedError,
)
from modules.accounting.models.coa import Account
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.bank_service import (
    BankAccountService,
    BankReconciliationService,
)
from modules.accounting.services.fiscal_service import FiscalCalendarService


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
    bank_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1000",
            account_name="Bank",
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
    other_bank_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1001",
            account_name="Savings Bank",
            account_type="ASSET",
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
        "bank_gl": bank_gl,
        "revenue": revenue,
        "other_bank_gl": other_bank_gl,
        "today": today,
    }


@pytest.fixture
def bank_account_service(db_session: Session) -> BankAccountService:
    return build_bank_account_service(db_session)


@pytest.fixture
def reconciliation_service(db_session: Session) -> BankReconciliationService:
    return build_bank_reconciliation_service(db_session)


def _make_bank_account(bank_account_service: BankAccountService, setup: dict):
    return bank_account_service.create_bank_account(
        company_id=setup["company_id"],
        bank_name="Main Current Account",
        account_number="ACC-0001",
        currency_code="USD",
        gl_account_id=setup["bank_gl"].id,
    )


class TestBankReconciliationFullWorkflow:
    def test_import_100_lines_auto_match_complete_and_lock(
        self,
        bank_account_service: BankAccountService,
        reconciliation_service: BankReconciliationService,
        setup: dict,
    ) -> None:
        account = _make_bank_account(bank_account_service, setup)

        total = Decimal("0")
        for i in range(100):
            amount = Decimal("10.00") + Decimal(i)
            bank_account_service.record_bank_deposit(
                company_id=setup["company_id"],
                bank_account_id=account.id,
                total_amount=amount,
                contra_account_id=setup["revenue"].id,
                deposit_date=setup["today"],
                reference=f"DEP-{i}",
                actor_id=None,
            )
            total += amount

        reconciliation = reconciliation_service.start_reconciliation(
            company_id=setup["company_id"],
            bank_account_id=account.id,
            statement_date=setup["today"],
            statement_closing_balance=total,
            actor_id=None,
        )
        assert reconciliation.status == "IN_PROGRESS"

        lines = [
            {
                "statement_date": setup["today"],
                "amount": Decimal("10.00") + Decimal(i),
                "reference": f"DEP-{i}",
            }
            for i in range(100)
        ]
        imported = reconciliation_service.import_statement_lines(
            company_id=setup["company_id"],
            bank_account_id=account.id,
            lines=lines,
            actor_id=None,
        )
        assert len(imported) == 100

        match_result = reconciliation_service.run_auto_match(
            company_id=setup["company_id"],
            reconciliation_id=reconciliation.id,
            actor_id=None,
        )
        assert match_result["matched_count"] == 100
        assert match_result["unmatched_count"] == 0

        completed = reconciliation_service.complete_reconciliation(
            company_id=setup["company_id"],
            reconciliation_id=reconciliation.id,
            actor_id=None,
        )
        assert completed.status == "COMPLETED"
        assert completed.statement_closing_balance == completed.gl_balance_at_date
        assert completed.difference == Decimal("0")

        locked = reconciliation_service.lock_reconciliation(
            company_id=setup["company_id"],
            reconciliation_id=reconciliation.id,
            actor_id=None,
        )
        assert locked.status == "LOCKED"

        with pytest.raises(ReconciliationLockedError):
            reconciliation_service.run_auto_match(
                company_id=setup["company_id"],
                reconciliation_id=reconciliation.id,
                actor_id=None,
            )

    def test_complete_fails_when_difference_nonzero(
        self,
        bank_account_service: BankAccountService,
        reconciliation_service: BankReconciliationService,
        setup: dict,
    ) -> None:
        account = _make_bank_account(bank_account_service, setup)
        bank_account_service.record_bank_deposit(
            company_id=setup["company_id"],
            bank_account_id=account.id,
            total_amount=Decimal("500.00"),
            contra_account_id=setup["revenue"].id,
            deposit_date=setup["today"],
            actor_id=None,
        )

        reconciliation = reconciliation_service.start_reconciliation(
            company_id=setup["company_id"],
            bank_account_id=account.id,
            statement_date=setup["today"],
            statement_closing_balance=Decimal("999.00"),
            actor_id=None,
        )

        with pytest.raises(ReconciliationNotBalancedError):
            reconciliation_service.complete_reconciliation(
                company_id=setup["company_id"],
                reconciliation_id=reconciliation.id,
                actor_id=None,
            )

    def test_manual_match_and_unmatch(
        self,
        bank_account_service: BankAccountService,
        reconciliation_service: BankReconciliationService,
        setup: dict,
    ) -> None:
        account = _make_bank_account(bank_account_service, setup)
        transaction, _ = bank_account_service.record_bank_deposit(
            company_id=setup["company_id"],
            bank_account_id=account.id,
            total_amount=Decimal("300.00"),
            contra_account_id=setup["revenue"].id,
            deposit_date=setup["today"],
            actor_id=None,
        )
        reconciliation = reconciliation_service.start_reconciliation(
            company_id=setup["company_id"],
            bank_account_id=account.id,
            statement_date=setup["today"],
            statement_closing_balance=Decimal("300.00"),
            actor_id=None,
        )
        lines = reconciliation_service.import_statement_lines(
            company_id=setup["company_id"],
            bank_account_id=account.id,
            lines=[{"statement_date": setup["today"], "amount": Decimal("300.00")}],
            actor_id=None,
        )

        match = reconciliation_service.manual_match(
            company_id=setup["company_id"],
            reconciliation_id=reconciliation.id,
            bank_transaction_id=transaction.id,
            statement_line_id=lines[0].id,
            actor_id=None,
        )
        assert match.match_type == "MANUAL"

        report = reconciliation_service.get_reconciliation_report(
            company_id=setup["company_id"], reconciliation_id=reconciliation.id
        )
        assert len(report["matches"]) == 1
        assert len(report["unmatched_transactions"]) == 0

        reconciliation_service.unmatch(
            company_id=setup["company_id"],
            reconciliation_id=reconciliation.id,
            match_id=match.id,
            actor_id=None,
        )
        report_after = reconciliation_service.get_reconciliation_report(
            company_id=setup["company_id"], reconciliation_id=reconciliation.id
        )
        assert len(report_after["matches"]) == 0
        assert len(report_after["unmatched_transactions"]) == 1


class TestBankTransfer:
    def test_transfer_creates_balanced_two_leg_journal(
        self, bank_account_service: BankAccountService, setup: dict
    ) -> None:
        from_account = bank_account_service.create_bank_account(
            company_id=setup["company_id"],
            bank_name="Main Current Account",
            account_number="ACC-FROM",
            currency_code="USD",
            gl_account_id=setup["bank_gl"].id,
        )
        to_account = bank_account_service.create_bank_account(
            company_id=setup["company_id"],
            bank_name="Savings Account",
            account_number="ACC-TO",
            currency_code="USD",
            gl_account_id=setup["other_bank_gl"].id,
        )
        bank_account_service.record_bank_deposit(
            company_id=setup["company_id"],
            bank_account_id=from_account.id,
            total_amount=Decimal("1000.00"),
            contra_account_id=setup["revenue"].id,
            deposit_date=setup["today"],
            actor_id=None,
        )

        from_txn, to_txn, result = bank_account_service.record_bank_transfer(
            company_id=setup["company_id"],
            from_bank_account_id=from_account.id,
            to_bank_account_id=to_account.id,
            amount=Decimal("400.00"),
            transfer_date=setup["today"],
            actor_id=None,
        )

        assert from_txn.amount == Decimal("-400.00")
        assert to_txn.amount == Decimal("400.00")
        assert (
            from_txn.journal_entry_id
            == to_txn.journal_entry_id
            == result.journal_entry_id
        )

        refreshed_from = bank_account_service.get_bank_account(
            setup["company_id"], from_account.id
        )
        refreshed_to = bank_account_service.get_bank_account(
            setup["company_id"], to_account.id
        )
        assert refreshed_from.current_gl_balance == Decimal("600.00")
        assert refreshed_to.current_gl_balance == Decimal("400.00")


class TestChequeLifecycle:
    def test_cheque_status_transitions(
        self, bank_account_service: BankAccountService, setup: dict
    ) -> None:
        account = _make_bank_account(bank_account_service, setup)
        cheque = bank_account_service.issue_cheque(
            company_id=setup["company_id"],
            bank_account_id=account.id,
            cheque_number="CHQ-0001",
            payee_name="Acme Supplies",
            cheque_date=setup["today"],
            amount=Decimal("250.00"),
            actor_id=None,
        )
        assert cheque.status == "ISSUED"

        presented = bank_account_service.update_cheque_status(
            company_id=setup["company_id"],
            cheque_id=cheque.id,
            new_status="PRESENTED",
            actor_id=None,
        )
        assert presented.status == "PRESENTED"

        cleared = bank_account_service.update_cheque_status(
            company_id=setup["company_id"],
            cheque_id=cheque.id,
            new_status="CLEARED",
            actor_id=None,
        )
        assert cleared.status == "CLEARED"

    def test_illegal_transition_raises(
        self, bank_account_service: BankAccountService, setup: dict
    ) -> None:
        account = _make_bank_account(bank_account_service, setup)
        cheque = bank_account_service.issue_cheque(
            company_id=setup["company_id"],
            bank_account_id=account.id,
            cheque_number="CHQ-0002",
            payee_name="Acme Supplies",
            cheque_date=setup["today"],
            amount=Decimal("100.00"),
            actor_id=None,
        )
        bank_account_service.update_cheque_status(
            company_id=setup["company_id"],
            cheque_id=cheque.id,
            new_status="CANCELLED",
            actor_id=None,
        )

        from modules.accounting.exceptions import PostingValidationError

        with pytest.raises(PostingValidationError):
            bank_account_service.update_cheque_status(
                company_id=setup["company_id"],
                cheque_id=cheque.id,
                new_status="CLEARED",
                actor_id=None,
            )

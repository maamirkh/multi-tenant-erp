"""[Epic 10, Phase 6, T109] Backward-compatibility regression: every
existing standalone caller of ``AccountsReceivableService.adjust_receivable()``
must see identical behavior, return type, and single-call ergonomics
after it was rewritten (tasks.md T096) into a thin wrapper of
``stage_adjustment()`` + ``finalize_adjustment()`` (plan.md §12.1).

Only test-level callers exist for this method (confirmed by repo-wide
grep — it is not wired to any REST endpoint), so this file both *is*
that caller and proves its own continued correctness end-to-end,
including the GL/AR/ledger reconciliation invariant the pre-existing
``test_ar_repository.py::test_reconciliation_holds_after_adjustment``
already exercises.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_ar_service
from modules.accounting.models.ar import ARTransaction
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.ar_service import AccountsReceivableService
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService


@pytest.fixture
def setup(db_session: Session) -> dict[str, Any]:
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
    rounding = account_repo.create(
        Account(
            company_id=company_id,
            account_code="7900",
            account_name="Rounding",
            account_type="EXPENSE",
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
    return {"company_id": company_id, "rounding": rounding, "today": today}


@pytest.fixture
def ar_service(db_session: Session) -> AccountsReceivableService:
    return build_ar_service(db_session, with_sales_sync=False)


class TestAdjustReceivableBackwardCompat:
    def test_returns_ar_transaction_and_commits_immediately(
        self, ar_service: AccountsReceivableService, setup: dict[str, Any]
    ) -> None:
        """The public wrapper's contract is unchanged: one call returns a
        committed, refreshed ARTransaction — the caller never needs to
        know stage_adjustment()/finalize_adjustment() exist."""
        customer_id = uuid4()
        transaction = ar_service.adjust_receivable(
            company_id=setup["company_id"],
            customer_id=customer_id,
            amount=Decimal("100.00"),
            contra_account_id=setup["rounding"].id,
            reason="Backward-compat regression",
            posting_date=setup["today"],
            actor_id=None,
        )

        assert isinstance(transaction, ARTransaction)
        assert transaction.status == "OPEN"
        assert transaction.outstanding_amount == Decimal("100.00")
        assert transaction.journal_entry_id is not None

        ledger = ar_service.get_customer_ledger(setup["company_id"], customer_id)
        assert ledger.total_outstanding_base == Decimal("100.00")

    def test_negative_amount_reduces_receivable(
        self, ar_service: AccountsReceivableService, setup: dict[str, Any]
    ) -> None:
        customer_id = uuid4()
        ar_service.adjust_receivable(
            company_id=setup["company_id"],
            customer_id=customer_id,
            amount=Decimal("-25.00"),
            contra_account_id=setup["rounding"].id,
            reason="Discount",
            posting_date=setup["today"],
            actor_id=None,
        )
        ledger = ar_service.get_customer_ledger(setup["company_id"], customer_id)
        assert ledger.total_outstanding_base == Decimal("-25.00")

    def test_reconciliation_still_holds(
        self, ar_service: AccountsReceivableService, setup: dict[str, Any]
    ) -> None:
        customer_id = uuid4()
        ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-BC-1",
            total_amount=Decimal("1000.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        ar_service.adjust_receivable(
            company_id=setup["company_id"],
            customer_id=customer_id,
            amount=Decimal("-50.00"),
            contra_account_id=setup["rounding"].id,
            reason="Rounding adjustment",
            posting_date=setup["today"],
            actor_id=None,
        )
        balance = ar_service.reconcile_ar_control_account(setup["company_id"])
        assert balance == Decimal("950.00")

"""[Epic 10, Phase 6, T110] Backward-compatibility regression: every
existing standalone caller of ``AccountsReceivableService.confirm_write_off()``
must see identical behavior after it was rewritten (tasks.md T100) into a
thin wrapper of ``stage_write_off()`` + ``finalize_write_off()`` (plan.md
§12.3.3) — this eliminated the pre-existing three-separate-commit defect
without changing the public contract.

The one production caller is ``modules/accounting/router.py``'s write-off
endpoint (already regression-proven by
``tests/integration/api/v1/accounting/test_ar_api.py::TestWriteOffEndpoint``,
re-run and confirmed passing during this phase); this file additionally
proves the service-layer contract directly.
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
    bad_debt = account_repo.create(
        Account(
            company_id=company_id,
            account_code="6900",
            account_name="Bad Debt Expense",
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
            default_bad_debt_account_id=bad_debt.id,
            default_revenue_account_id=revenue.id,
        )
    )
    return {"company_id": company_id, "today": today}


@pytest.fixture
def ar_service(db_session: Session) -> AccountsReceivableService:
    return build_ar_service(db_session, with_sales_sync=False)


class TestConfirmWriteOffBackwardCompat:
    def test_returns_written_off_transaction_committed(
        self, ar_service: AccountsReceivableService, setup: dict[str, Any]
    ) -> None:
        customer_id = uuid4()
        transaction, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-BC-WO-1",
            total_amount=Decimal("300.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )

        written_off = ar_service.confirm_write_off(
            company_id=setup["company_id"],
            ar_transaction_id=transaction.id,
            reason="Uncollectible — backward-compat regression",
            actor_id=None,
        )

        assert isinstance(written_off, ARTransaction)
        assert written_off.status == "WRITTEN_OFF"
        assert written_off.outstanding_amount == Decimal("0")

    def test_reconciliation_and_ledger_still_hold(
        self, ar_service: AccountsReceivableService, setup: dict[str, Any]
    ) -> None:
        customer_id = uuid4()
        transaction, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-BC-WO-2",
            total_amount=Decimal("200.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        ar_service.confirm_write_off(
            company_id=setup["company_id"],
            ar_transaction_id=transaction.id,
            reason="Uncollectible",
            actor_id=None,
        )

        ledger = ar_service.get_customer_ledger(setup["company_id"], customer_id)
        assert ledger.total_outstanding_base == Decimal("0")

        balance = ar_service.reconcile_ar_control_account(setup["company_id"])
        assert balance == Decimal("0")

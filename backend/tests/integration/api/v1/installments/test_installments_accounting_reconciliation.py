"""T117 (US-6, corrected — adapter-level, no HTTP) — with a fixture
overdue obligation, ``InstallmentsAdapter.run("installments.aging", ...)``
and ``AccountingAdapter.run("accounting.ar_aging", ...)`` (both called
directly, no HTTP) reflect a consistent outstanding amount for the same
customer: the installment contract's schedule-line outstanding total
(Installments' own authoritative source) equals the underlying Sales
invoice's AR-transaction outstanding balance (Accounting's own
authoritative source) — both trace back to the exact same
``contractual_total`` since ``build_active_contract_with_schedule``'s
default ``down_payment_amount=0`` makes ``invoice_total ==
contractual_total`` (plan.md §25).

Real PostgreSQL (reuses this directory's own fixture — schedule
persistence requires it, matching every other test in this file's
sibling ``test_reporting_service.py``).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.installments.models.schedule import InstallmentScheduleLine
from modules.installments.services.business_date import get_business_date
from modules.reports.schemas.accounting import ArAgingFilter
from modules.reports.schemas.installments import InstallmentAgingFilter
from modules.reports.services.adapters.accounting_adapter import AccountingAdapter
from modules.reports.services.adapters.base import PaginatedReportResult
from modules.reports.services.adapters.installments_adapter import InstallmentsAdapter
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)


def test_installments_aging_and_accounting_ar_aging_agree_on_outstanding(
    db_session: Session,
) -> None:
    ctx = build_active_contract_with_schedule(
        db_session, installment_count=1, installment_amount=Decimal("100.00")
    )
    business_date = get_business_date()
    line = (
        db_session.query(InstallmentScheduleLine)
        .filter_by(schedule_version_id=ctx["schedule_version"].id)
        .one()
    )
    line.due_date = business_date - timedelta(days=45)
    db_session.add(line)
    db_session.commit()

    installments_result = InstallmentsAdapter().run(
        db_session,
        ctx["company_id"],
        "installments.aging",
        InstallmentAgingFilter(as_of_date=business_date),
        page=1,
        page_size=20,
        sort=None,
        comparison=None,
    )
    assert isinstance(installments_result, PaginatedReportResult)
    installments_outstanding = sum(
        (
            Decimal(str(row.model_dump()["outstanding_amount"]))
            for row in installments_result.items
        ),
        Decimal("0"),
    )

    accounting_result = AccountingAdapter().run(
        db_session,
        ctx["company_id"],
        "accounting.ar_aging",
        ArAgingFilter(as_of_date=business_date),
        page=1,
        page_size=20,
        sort=None,
        comparison=None,
    )
    assert isinstance(accounting_result, PaginatedReportResult)
    matching_ar_rows = [
        r for r in accounting_result.items if r.customer_id == ctx["customer_id"]
    ]
    assert len(matching_ar_rows) == 1
    accounting_outstanding = matching_ar_rows[0].total

    assert installments_outstanding == accounting_outstanding == Decimal("100.000000")

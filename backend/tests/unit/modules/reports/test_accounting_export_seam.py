"""T061/T062 — Export-seam tests: ``count_export_rows()``/``iter_export_rows()``
for ``ar_aging``/``ap_aging``/``bank_cash_book`` (genuine Category A) and
the pure page-by-page cursor iterator for ``accounting.gl`` (no count seam
— T062, mid-stream abort-on-overflow is Phase 6's concern)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.reports.schemas.accounting import ArAgingFilter, GlFilter
from modules.reports.services.adapters.accounting_adapter import AccountingAdapter

AS_OF = date(2026, 6, 30)


def test_ar_aging_export_seam_counts_and_iterates(db_session: Session) -> None:
    company_id = uuid.uuid4()
    for i in range(5):
        ledger = CustomerLedger(company_id=company_id, customer_id=uuid.uuid4())
        db_session.add(ledger)
        db_session.flush()
        db_session.add(
            ARTransaction(
                company_id=company_id,
                customer_ledger_id=ledger.id,
                transaction_type="INVOICE",
                transaction_date=date(2026, 1, 1),
                due_date=date(2026, 1, 1) + timedelta(days=i),
                currency_code="USD",
                amount_foreign=Decimal(f"{100 + i}.00"),
                amount_base=Decimal(f"{100 + i}.00"),
                outstanding_amount=Decimal(f"{100 + i}.00"),
                status="OPEN",
            )
        )
    db_session.commit()

    adapter = AccountingAdapter()
    filters = ArAgingFilter(as_of_date=AS_OF)

    count = adapter.count_export_rows(
        db_session, company_id, "accounting.ar_aging", filters
    )
    assert count == 5

    batches = list(
        adapter.iter_export_rows(
            db_session, company_id, "accounting.ar_aging", filters, None, batch_size=2
        )
    )
    total_rows = sum(len(b) for b in batches)
    assert total_rows == 5
    assert all(len(b) <= 2 for b in batches)


def test_gl_export_seam_has_no_count_and_paginates_by_cursor(
    db_session: Session,
) -> None:
    from tests.integration.api.v1.accounting.test_reports_api import _setup

    company_id = uuid.uuid4()
    _setup(db_session, company_id)

    adapter = AccountingAdapter()
    filters = GlFilter()
    batches = list(
        adapter.iter_export_rows(
            db_session, company_id, "accounting.gl", filters, None, batch_size=1
        )
    )
    # 3 posted journal entries x 2 lines each = 6 GL lines, batched 1-at-a-time.
    total_rows = sum(len(b) for b in batches)
    assert total_rows == 6
    assert all(len(b) == 1 for b in batches)

    with pytest.raises(ValueError, match="no export-row count seam"):
        adapter.count_export_rows(db_session, company_id, "accounting.gl", filters)

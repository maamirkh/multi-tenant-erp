"""T059 — the union of all pages from ``count_ar_aging_rows()``/
``get_ar_aging_page()`` (and AP equivalents) must equal
``AccountsReceivableService.get_aging_report()``/
``AccountsPayableService.get_aging_report()``'s existing, untouched
full/unpaginated calculation — proving the new bounded seam is a pure
re-slicing of the identical formula, not a new calculation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from modules.accounting.models.ap import APTransaction, SupplierLedger
from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.accounting.repositories.ap import SupplierLedgerRepository
from modules.accounting.repositories.ar import CustomerLedgerRepository
from modules.accounting.services.ap_service import AccountsPayableService
from modules.accounting.services.ar_service import AccountsReceivableService

AS_OF = date(2026, 6, 30)


def _seed_ar_customers(db: Session, company_id, count: int) -> None:
    for i in range(count):
        ledger = CustomerLedger(company_id=company_id, customer_id=uuid4())
        db.add(ledger)
        db.flush()
        db.add(
            ARTransaction(
                company_id=company_id,
                customer_ledger_id=ledger.id,
                transaction_type="INVOICE",
                transaction_date=date(2026, 1, 1),
                due_date=date(2026, 1, 1) + __import__("datetime").timedelta(days=i),
                currency_code="USD",
                amount_foreign=Decimal(f"{100 + i}.00"),
                amount_base=Decimal(f"{100 + i}.00"),
                outstanding_amount=Decimal(f"{100 + i}.00"),
                status="OPEN",
            )
        )
    db.commit()


def _seed_ap_suppliers(db: Session, company_id, count: int) -> None:
    for i in range(count):
        ledger = SupplierLedger(company_id=company_id, supplier_id=uuid4())
        db.add(ledger)
        db.flush()
        db.add(
            APTransaction(
                company_id=company_id,
                supplier_ledger_id=ledger.id,
                transaction_type="BILL",
                transaction_date=date(2026, 1, 1),
                due_date=date(2026, 1, 1) + __import__("datetime").timedelta(days=i),
                currency_code="USD",
                amount_foreign=Decimal(f"{200 + i}.00"),
                amount_base=Decimal(f"{200 + i}.00"),
                outstanding_amount=Decimal(f"{200 + i}.00"),
                status="OPEN",
            )
        )
    db.commit()


def test_ar_paginated_union_matches_full_aging_report(db_session: Session) -> None:
    company_id = uuid4()
    _seed_ar_customers(db_session, company_id, count=5)

    ar_service = AccountsReceivableService(
        db=db_session,
        ledger_repo=CustomerLedgerRepository(db_session),
        transaction_repo=MagicMock(),
        allocation_repo=MagicMock(),
        credit_history_repo=MagicMock(),
        config_repo=MagicMock(),
        posting_engine=MagicMock(),
        audit_service=MagicMock(),
    )
    full_report = ar_service.get_aging_report(company_id, AS_OF)

    assert ar_service.count_aging_rows(company_id, AS_OF) == 5

    page_1 = ar_service.get_aging_page(company_id, AS_OF, limit=2, offset=0)
    page_2 = ar_service.get_aging_page(company_id, AS_OF, limit=2, offset=2)
    page_3 = ar_service.get_aging_page(company_id, AS_OF, limit=2, offset=4)

    union_rows = {r.customer_ledger_id: r for r in page_1.rows}
    union_rows.update({r.customer_ledger_id: r for r in page_2.rows})
    union_rows.update({r.customer_ledger_id: r for r in page_3.rows})

    full_rows_by_id = {r.customer_ledger_id: r for r in full_report.rows}
    assert set(union_rows.keys()) == set(full_rows_by_id.keys())
    for ledger_id, paged_row in union_rows.items():
        full_row = full_rows_by_id[ledger_id]
        assert paged_row.current == full_row.current
        assert paged_row.days_1_30 == full_row.days_1_30
        assert paged_row.total == full_row.total


def test_ap_paginated_union_matches_full_aging_report(db_session: Session) -> None:
    company_id = uuid4()
    _seed_ap_suppliers(db_session, company_id, count=4)

    ap_service = AccountsPayableService(
        db=db_session,
        ledger_repo=SupplierLedgerRepository(db_session),
        transaction_repo=MagicMock(),
        allocation_repo=MagicMock(),
        reconciliation_repo=MagicMock(),
        reconciliation_item_repo=MagicMock(),
        config_repo=MagicMock(),
        posting_engine=MagicMock(),
        audit_service=MagicMock(),
    )
    full_report = ap_service.get_aging_report(company_id, AS_OF)

    assert ap_service.count_aging_rows(company_id, AS_OF) == 4

    page_1 = ap_service.get_aging_page(company_id, AS_OF, limit=3, offset=0)
    page_2 = ap_service.get_aging_page(company_id, AS_OF, limit=3, offset=3)

    union_rows = {r.supplier_ledger_id: r for r in page_1.rows}
    union_rows.update({r.supplier_ledger_id: r for r in page_2.rows})

    full_rows_by_id = {r.supplier_ledger_id: r for r in full_report.rows}
    assert set(union_rows.keys()) == set(full_rows_by_id.keys())
    for ledger_id, paged_row in union_rows.items():
        assert paged_row.total == full_rows_by_id[ledger_id].total

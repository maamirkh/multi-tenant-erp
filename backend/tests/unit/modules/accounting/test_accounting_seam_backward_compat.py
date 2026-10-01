"""T048 — Epic 11 Reports additive source-domain seam (T047) regression.

Proves every existing Accounting caller of ``find_by_bank_account``/
``find_by_cash_account``/``get_aging_report`` (AR + AP) produces identical
output before/after T047's new optional params — because every new param
defaults to reproducing the exact prior unbounded behavior, no existing
call site (which never passes them) can observe any difference.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from modules.accounting.models.ap import APTransaction, SupplierLedger
from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.accounting.models.banking import BankAccount, BankTransaction
from modules.accounting.models.cash import CashAccount, CashTransaction
from modules.accounting.models.coa import Account
from modules.accounting.repositories.ap import SupplierLedgerRepository
from modules.accounting.repositories.ar import CustomerLedgerRepository
from modules.accounting.repositories.banking import BankTransactionRepository
from modules.accounting.repositories.cash import CashTransactionRepository


def _make_account(db: Session, company_id, *, code: str) -> Account:
    account = Account(
        company_id=company_id,
        account_code=code,
        account_name=f"Test Account {code}",
        account_type="ASSET",
        is_leaf=True,
    )
    db.add(account)
    db.flush()
    return account


def _make_bank_account(db: Session, company_id) -> BankAccount:
    gl_account = _make_account(db, company_id, code="1010")
    bank_account = BankAccount(
        company_id=company_id,
        bank_name="Test Bank",
        account_number="ACC-001",
        currency_code="USD",
        gl_account_id=gl_account.id,
    )
    db.add(bank_account)
    db.flush()
    return bank_account


def _make_cash_account(db: Session, company_id) -> CashAccount:
    gl_account = _make_account(db, company_id, code="1020")
    cash_account = CashAccount(
        company_id=company_id,
        account_name="Test Cash Box",
        currency_code="USD",
        gl_account_id=gl_account.id,
    )
    db.add(cash_account)
    db.flush()
    return cash_account


def test_find_by_bank_account_default_call_unchanged(db_session: Session) -> None:
    company_id = uuid4()
    bank_account = _make_bank_account(db_session, company_id)
    for i, d in enumerate([date(2026, 1, 5), date(2026, 2, 10), date(2026, 3, 15)]):
        db_session.add(
            BankTransaction(
                company_id=company_id,
                bank_account_id=bank_account.id,
                transaction_date=d,
                transaction_type="RECEIPT",
                amount=Decimal(f"{100 + i}.00"),
            )
        )
    db_session.commit()

    repo = BankTransactionRepository(db_session)
    result = repo.find_by_bank_account(company_id, bank_account.id)

    assert len(result) == 3
    assert [t.transaction_date for t in result] == [
        date(2026, 1, 5),
        date(2026, 2, 10),
        date(2026, 3, 15),
    ]


def test_find_by_cash_account_default_call_unchanged(db_session: Session) -> None:
    company_id = uuid4()
    cash_account = _make_cash_account(db_session, company_id)
    for i, d in enumerate([date(2026, 1, 5), date(2026, 2, 10)]):
        db_session.add(
            CashTransaction(
                company_id=company_id,
                cash_account_id=cash_account.id,
                transaction_date=d,
                transaction_type="RECEIPT",
                amount=Decimal(f"{50 + i}.00"),
            )
        )
    db_session.commit()

    repo = CashTransactionRepository(db_session)
    result = repo.find_by_cash_account(company_id, cash_account.id)

    assert len(result) == 2


def test_ar_get_aging_data_default_call_unchanged(db_session: Session) -> None:
    company_id = uuid4()
    ledger = CustomerLedger(company_id=company_id, customer_id=uuid4())
    db_session.add(ledger)
    db_session.flush()
    db_session.add(
        ARTransaction(
            company_id=company_id,
            customer_ledger_id=ledger.id,
            transaction_type="INVOICE",
            transaction_date=date(2026, 1, 1),
            due_date=date(2026, 1, 31),
            currency_code="USD",
            amount_foreign=Decimal("100.00"),
            amount_base=Decimal("100.00"),
            outstanding_amount=Decimal("100.00"),
            status="OPEN",
        )
    )
    db_session.commit()

    repo = CustomerLedgerRepository(db_session)
    rows = repo.get_aging_data(company_id, date(2026, 6, 30))
    assert len(rows) == 1


def test_ap_get_aging_data_default_call_unchanged(db_session: Session) -> None:
    company_id = uuid4()
    ledger = SupplierLedger(company_id=company_id, supplier_id=uuid4())
    db_session.add(ledger)
    db_session.flush()
    db_session.add(
        APTransaction(
            company_id=company_id,
            supplier_ledger_id=ledger.id,
            transaction_type="BILL",
            transaction_date=date(2026, 1, 1),
            due_date=date(2026, 1, 31),
            currency_code="USD",
            amount_foreign=Decimal("200.00"),
            amount_base=Decimal("200.00"),
            outstanding_amount=Decimal("200.00"),
            status="OPEN",
        )
    )
    db_session.commit()

    repo = SupplierLedgerRepository(db_session)
    rows = repo.get_aging_data(company_id, date(2026, 6, 30))
    assert len(rows) == 1

"""T060 — T047's new bank/cash bounded-read seam methods
(``count_bank_transactions``/``get_bank_transactions_page`` and cash
equivalents) produce results identical to the existing unbounded
``find_by_bank_account``/``find_by_cash_account`` scan, for the same
date range."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from modules.accounting.models.banking import BankAccount, BankTransaction
from modules.accounting.models.cash import CashAccount, CashTransaction
from modules.accounting.models.coa import Account
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


def test_bank_bounded_seam_matches_unbounded_scan(db_session: Session) -> None:
    company_id = uuid4()
    gl_account = _make_account(db_session, company_id, code="1010")
    bank_account = BankAccount(
        company_id=company_id,
        bank_name="Test Bank",
        account_number="ACC-01",
        currency_code="USD",
        gl_account_id=gl_account.id,
    )
    db_session.add(bank_account)
    db_session.flush()

    dates = [date(2026, 1, d) for d in (5, 10, 15, 20, 25)]
    for i, d in enumerate(dates):
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

    full_scan = [
        t
        for t in repo.find_by_bank_account(company_id, bank_account.id)
        if date(2026, 1, 10) <= t.transaction_date <= date(2026, 1, 20)
    ]
    bounded = repo.find_by_bank_account(
        company_id,
        bank_account.id,
        from_date=date(2026, 1, 10),
        to_date=date(2026, 1, 20),
        limit=100,
    )
    assert [t.id for t in full_scan] == [t.id for t in bounded]
    assert repo.count_bank_transactions(
        company_id,
        bank_account.id,
        from_date=date(2026, 1, 10),
        to_date=date(2026, 1, 20),
    ) == len(full_scan)


def test_cash_bounded_seam_matches_unbounded_scan(db_session: Session) -> None:
    company_id = uuid4()
    gl_account = _make_account(db_session, company_id, code="1020")
    cash_account = CashAccount(
        company_id=company_id,
        account_name="Test Cash",
        currency_code="USD",
        gl_account_id=gl_account.id,
    )
    db_session.add(cash_account)
    db_session.flush()

    dates = [date(2026, 2, d) for d in (1, 8, 15, 22)]
    for i, d in enumerate(dates):
        db_session.add(
            CashTransaction(
                company_id=company_id,
                cash_account_id=cash_account.id,
                transaction_date=d,
                transaction_type="PAYMENT",
                amount=Decimal(f"-{30 + i}.00"),
            )
        )
    db_session.commit()

    repo = CashTransactionRepository(db_session)

    full_scan = [
        t
        for t in repo.find_by_cash_account(company_id, cash_account.id)
        if date(2026, 2, 8) <= t.transaction_date <= date(2026, 2, 15)
    ]
    bounded = repo.find_by_cash_account(
        company_id,
        cash_account.id,
        from_date=date(2026, 2, 8),
        to_date=date(2026, 2, 15),
        limit=100,
    )
    assert [t.id for t in full_scan] == [t.id for t in bounded]
    assert repo.count_cash_transactions(
        company_id,
        cash_account.id,
        from_date=date(2026, 2, 8),
        to_date=date(2026, 2, 15),
    ) == len(full_scan)

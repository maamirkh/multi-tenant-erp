"""AgingCalculator — AR and AP aging bucket calculation — Phases 6 & 7.

Aging is calculated from the invoice/bill ``due_date``, not the transaction
date (spec.md §18.3 / §19.3). Buckets:
  Current (Not Yet Due)  — days_overdue <= 0 (or due_date is NULL)
  1-30 Days Overdue      — 1  <= days_overdue <= 30
  31-60 Days Overdue     — 31 <= days_overdue <= 60
  61-90 Days Overdue     — 61 <= days_overdue <= 90
  91-120 Days Overdue    — 91 <= days_overdue <= 120
  120+ Days Overdue      — days_overdue > 120

``AgingCalculator`` (AR, Phase 6) and ``APAgingCalculator`` (AP, Phase 7)
share the identical bucket-boundary logic (``_bucket_for``) but are kept as
separate small classes rather than one generic engine — the two ledger
repositories expose differently-named FK columns (``customer_ledger_id``/
``customer_id`` vs ``supplier_ledger_id``/``supplier_id``), so a shared
generic base would need more indirection than the ~20 duplicated lines it
would save.

Spec ref: specs/008-accounting-finance/tasks.md T138, T162/T165
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

from modules.accounting.repositories.ap import SupplierLedgerRepository
from modules.accounting.repositories.ar import CustomerLedgerRepository

_BUCKET_FIELDS = (
    "current",
    "days_1_30",
    "days_31_60",
    "days_61_90",
    "days_91_120",
    "days_120_plus",
)


@dataclass
class AgingRow:
    """Aging bucket totals for one customer (or the aggregate, when
    ``customer_ledger_id``/``customer_id`` are ``None``).
    """

    customer_ledger_id: UUID | None
    customer_id: UUID | None
    current: Decimal = Decimal("0")
    days_1_30: Decimal = Decimal("0")
    days_31_60: Decimal = Decimal("0")
    days_61_90: Decimal = Decimal("0")
    days_91_120: Decimal = Decimal("0")
    days_120_plus: Decimal = Decimal("0")

    @property
    def total(self) -> Decimal:
        return sum((getattr(self, f) for f in _BUCKET_FIELDS), Decimal("0"))


@dataclass
class AgingReport:
    as_of_date: date
    rows: list[AgingRow] = field(default_factory=list)
    totals: AgingRow = field(default_factory=lambda: AgingRow(None, None))


class AgingCalculator:
    """Domain service computing AR aging buckets per customer and in aggregate."""

    def __init__(self, ledger_repo: CustomerLedgerRepository) -> None:
        self._ledgers = ledger_repo

    def calculate_ar_aging(self, company_id: UUID, as_of_date: date) -> AgingReport:
        transactions = self._ledgers.get_aging_data(company_id, as_of_date)
        ledgers_by_id = {
            ledger.id: ledger for ledger in self._ledgers.list_all(company_id)
        }

        rows_by_ledger: dict[UUID, AgingRow] = {}
        for txn in transactions:
            ledger = ledgers_by_id.get(txn.customer_ledger_id)
            customer_id = ledger.customer_id if ledger else None
            row = rows_by_ledger.setdefault(
                txn.customer_ledger_id,
                AgingRow(
                    customer_ledger_id=txn.customer_ledger_id, customer_id=customer_id
                ),
            )
            bucket = self._bucket_for(txn.due_date, as_of_date)
            setattr(row, bucket, getattr(row, bucket) + txn.outstanding_amount)

        totals = AgingRow(None, None)
        for row in rows_by_ledger.values():
            for f in _BUCKET_FIELDS:
                setattr(totals, f, getattr(totals, f) + getattr(row, f))

        return AgingReport(
            as_of_date=as_of_date, rows=list(rows_by_ledger.values()), totals=totals
        )

    @staticmethod
    def _bucket_for(due_date: date | None, as_of_date: date) -> str:
        return _bucket_for(due_date, as_of_date)


@dataclass
class APAgingRow:
    """Aging bucket totals for one supplier (or the aggregate, when
    ``supplier_ledger_id``/``supplier_id`` are ``None``).
    """

    supplier_ledger_id: UUID | None
    supplier_id: UUID | None
    current: Decimal = Decimal("0")
    days_1_30: Decimal = Decimal("0")
    days_31_60: Decimal = Decimal("0")
    days_61_90: Decimal = Decimal("0")
    days_91_120: Decimal = Decimal("0")
    days_120_plus: Decimal = Decimal("0")

    @property
    def total(self) -> Decimal:
        return sum((getattr(self, f) for f in _BUCKET_FIELDS), Decimal("0"))


@dataclass
class APAgingReport:
    as_of_date: date
    rows: list[APAgingRow] = field(default_factory=list)
    totals: APAgingRow = field(default_factory=lambda: APAgingRow(None, None))


class APAgingCalculator:
    """Domain service computing AP aging buckets per supplier and in aggregate."""

    def __init__(self, ledger_repo: SupplierLedgerRepository) -> None:
        self._ledgers = ledger_repo

    def calculate_ap_aging(self, company_id: UUID, as_of_date: date) -> APAgingReport:
        transactions = self._ledgers.get_aging_data(company_id, as_of_date)
        ledgers_by_id = {
            ledger.id: ledger for ledger in self._ledgers.list_all(company_id)
        }

        rows_by_ledger: dict[UUID, APAgingRow] = {}
        for txn in transactions:
            ledger = ledgers_by_id.get(txn.supplier_ledger_id)
            supplier_id = ledger.supplier_id if ledger else None
            row = rows_by_ledger.setdefault(
                txn.supplier_ledger_id,
                APAgingRow(
                    supplier_ledger_id=txn.supplier_ledger_id, supplier_id=supplier_id
                ),
            )
            bucket = _bucket_for(txn.due_date, as_of_date)
            setattr(row, bucket, getattr(row, bucket) + txn.outstanding_amount)

        totals = APAgingRow(None, None)
        for row in rows_by_ledger.values():
            for f in _BUCKET_FIELDS:
                setattr(totals, f, getattr(totals, f) + getattr(row, f))

        return APAgingReport(
            as_of_date=as_of_date, rows=list(rows_by_ledger.values()), totals=totals
        )

    @staticmethod
    def _bucket_for(due_date: date | None, as_of_date: date) -> str:
        return _bucket_for(due_date, as_of_date)


def _bucket_for(due_date: date | None, as_of_date: date) -> str:
    if due_date is None:
        return "current"
    days_overdue = (as_of_date - due_date).days
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "days_1_30"
    if days_overdue <= 60:
        return "days_31_60"
    if days_overdue <= 90:
        return "days_61_90"
    if days_overdue <= 120:
        return "days_91_120"
    return "days_120_plus"

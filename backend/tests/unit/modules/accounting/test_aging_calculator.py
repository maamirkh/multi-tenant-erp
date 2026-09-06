"""Unit tests for AgingCalculator (AR) and APAgingCalculator (AP) — Phases 6 & 7.

Tests (tasks.md T151) — bucket assignment for boundary dates:
  - Invoice due today            -> Current
  - Invoice 30 days overdue      -> 1-30
  - Invoice 31 days overdue      -> 31-60
  - Invoice 60/61 days overdue   -> 31-60 / 61-90 boundary
  - Invoice 90/91 days overdue   -> 61-90 / 91-120 boundary
  - Invoice 120/121 days overdue -> 91-120 / 120+ boundary
  - Invoice with no due_date     -> Current

``TestAPAgingCalculator`` (Phase 7) re-verifies the identical boundary
behavior through ``APAgingCalculator`` — the two classes share the same
underlying ``_bucket_for()`` helper (see aging_calculator.py's module
docstring), so this is a wiring/regression check rather than a full
re-derivation of every boundary.

Spec ref: specs/008-accounting-finance/tasks.md T151
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from modules.accounting.services.aging_calculator import (
    AgingCalculator,
    APAgingCalculator,
)


@dataclass
class _FakeTransaction:
    customer_ledger_id: UUID
    due_date: date | None
    outstanding_amount: Decimal


@dataclass
class _FakeLedger:
    id: UUID
    customer_id: UUID


class _FakeLedgerRepo:
    """Minimal stand-in for CustomerLedgerRepository — AgingCalculator only
    calls ``get_aging_data()`` and ``list_all()``.
    """

    def __init__(
        self, ledgers: list[_FakeLedger], transactions: list[_FakeTransaction]
    ) -> None:
        self._ledgers = ledgers
        self._transactions = transactions

    def get_aging_data(
        self, company_id: UUID, as_of_date: date
    ) -> list[_FakeTransaction]:
        return self._transactions

    def list_all(self, company_id: UUID) -> list[_FakeLedger]:
        return self._ledgers


AS_OF = date(2026, 6, 30)


def _txn(
    days_overdue: int | None, amount: str = "100.00"
) -> tuple[_FakeLedger, _FakeTransaction]:
    ledger = _FakeLedger(id=uuid4(), customer_id=uuid4())
    due_date = None if days_overdue is None else AS_OF - timedelta(days=days_overdue)
    txn = _FakeTransaction(
        customer_ledger_id=ledger.id,
        due_date=due_date,
        outstanding_amount=Decimal(amount),
    )
    return ledger, txn


class TestAgingBucketBoundaries:
    @pytest.mark.parametrize(
        "days_overdue,expected_bucket",
        [
            (None, "current"),
            (0, "current"),
            (-5, "current"),
            (1, "days_1_30"),
            (30, "days_1_30"),
            (31, "days_31_60"),
            (60, "days_31_60"),
            (61, "days_61_90"),
            (90, "days_61_90"),
            (91, "days_91_120"),
            (120, "days_91_120"),
            (121, "days_120_plus"),
            (365, "days_120_plus"),
        ],
    )
    def test_bucket_for_boundary(
        self, days_overdue: int | None, expected_bucket: str
    ) -> None:
        ledger, txn = _txn(days_overdue)
        repo = _FakeLedgerRepo([ledger], [txn])
        report = AgingCalculator(repo).calculate_ar_aging(uuid4(), AS_OF)

        row = next(r for r in report.rows if r.customer_ledger_id == ledger.id)
        assert getattr(row, expected_bucket) == Decimal("100.00")
        assert row.total == Decimal("100.00")

    def test_aggregate_totals_sum_across_customers(self) -> None:
        ledger1, txn1 = _txn(0, "100.00")
        ledger2, txn2 = _txn(31, "250.00")
        repo = _FakeLedgerRepo([ledger1, ledger2], [txn1, txn2])
        report = AgingCalculator(repo).calculate_ar_aging(uuid4(), AS_OF)

        assert report.totals.current == Decimal("100.00")
        assert report.totals.days_31_60 == Decimal("250.00")
        assert report.totals.total == Decimal("350.00")

    def test_multiple_transactions_same_customer_accumulate_in_bucket(self) -> None:
        ledger = _FakeLedger(id=uuid4(), customer_id=uuid4())
        txn_a = _FakeTransaction(
            customer_ledger_id=ledger.id,
            due_date=AS_OF,
            outstanding_amount=Decimal("40.00"),
        )
        txn_b = _FakeTransaction(
            customer_ledger_id=ledger.id,
            due_date=AS_OF,
            outstanding_amount=Decimal("60.00"),
        )
        repo = _FakeLedgerRepo([ledger], [txn_a, txn_b])
        report = AgingCalculator(repo).calculate_ar_aging(uuid4(), AS_OF)

        row = report.rows[0]
        assert row.current == Decimal("100.00")

    def test_no_open_transactions_returns_empty_rows(self) -> None:
        repo = _FakeLedgerRepo([], [])
        report = AgingCalculator(repo).calculate_ar_aging(uuid4(), AS_OF)
        assert report.rows == []
        assert report.totals.total == Decimal("0")


@dataclass
class _FakeAPTransaction:
    supplier_ledger_id: UUID
    due_date: date | None
    outstanding_amount: Decimal


@dataclass
class _FakeSupplierLedger:
    id: UUID
    supplier_id: UUID


class _FakeSupplierLedgerRepo:
    """Minimal stand-in for SupplierLedgerRepository — APAgingCalculator
    only calls ``get_aging_data()`` and ``list_all()``.
    """

    def __init__(
        self, ledgers: list[_FakeSupplierLedger], transactions: list[_FakeAPTransaction]
    ) -> None:
        self._ledgers = ledgers
        self._transactions = transactions

    def get_aging_data(
        self, company_id: UUID, as_of_date: date
    ) -> list[_FakeAPTransaction]:
        return self._transactions

    def list_all(self, company_id: UUID) -> list[_FakeSupplierLedger]:
        return self._ledgers


def _ap_txn(
    days_overdue: int | None, amount: str = "100.00"
) -> tuple[_FakeSupplierLedger, _FakeAPTransaction]:
    ledger = _FakeSupplierLedger(id=uuid4(), supplier_id=uuid4())
    due_date = None if days_overdue is None else AS_OF - timedelta(days=days_overdue)
    txn = _FakeAPTransaction(
        supplier_ledger_id=ledger.id,
        due_date=due_date,
        outstanding_amount=Decimal(amount),
    )
    return ledger, txn


class TestAPAgingCalculator:
    @pytest.mark.parametrize(
        "days_overdue,expected_bucket",
        [
            (None, "current"),
            (0, "current"),
            (30, "days_1_30"),
            (31, "days_31_60"),
            (91, "days_91_120"),
            (121, "days_120_plus"),
        ],
    )
    def test_bucket_for_boundary(
        self, days_overdue: int | None, expected_bucket: str
    ) -> None:
        ledger, txn = _ap_txn(days_overdue)
        repo = _FakeSupplierLedgerRepo([ledger], [txn])
        report = APAgingCalculator(repo).calculate_ap_aging(uuid4(), AS_OF)

        row = next(r for r in report.rows if r.supplier_ledger_id == ledger.id)
        assert getattr(row, expected_bucket) == Decimal("100.00")

    def test_aggregate_totals_sum_across_suppliers(self) -> None:
        ledger1, txn1 = _ap_txn(0, "300.00")
        ledger2, txn2 = _ap_txn(31, "150.00")
        repo = _FakeSupplierLedgerRepo([ledger1, ledger2], [txn1, txn2])
        report = APAgingCalculator(repo).calculate_ap_aging(uuid4(), AS_OF)

        assert report.totals.current == Decimal("300.00")
        assert report.totals.days_31_60 == Decimal("150.00")
        assert report.totals.total == Decimal("450.00")

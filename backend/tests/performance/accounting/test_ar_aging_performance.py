"""AR aging performance benchmark — Phase 18 (T314).

Verifies plan.md Phase 12/18 acceptance criterion: "AR aging 10,000
customers < 5 seconds." Unlike the GL report/trial-balance benchmarks
(``test_report_performance.py``, T270), aging calculation is a single flat
query (``ARTransactionRepository.get_aging_data`` — one table, no joins)
followed by O(N) in-memory Python bucketing (``AgingCalculator``), so it
does not suffer the SQLite nested-loop-planner scaling problem documented
there — this benchmark runs at the full literal 10,000-customer scale
directly, no extrapolation needed.

Spec ref: specs/008-accounting-finance/tasks.md T314
Plan ref: specs/008-accounting-finance/plan.md Phase 18 Scope
"""

from __future__ import annotations

import time
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import insert
from sqlalchemy.orm import Session

from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.accounting.repositories.ar import CustomerLedgerRepository
from modules.accounting.services.aging_calculator import AgingCalculator

_CUSTOMER_COUNT = 10_000
_TARGET_SECONDS = 5


def _seed_customers(db: Session, company_id: uuid.UUID, as_of_date: date) -> None:
    """Bulk-insert one CustomerLedger + one open ARTransaction per customer
    via SQLAlchemy Core, spreading due dates across every aging bucket."""
    ledger_ids = [uuid.uuid4() for _ in range(_CUSTOMER_COUNT)]
    ledger_rows = [
        {
            "id": ledger_ids[i],
            "company_id": company_id,
            "customer_id": uuid.uuid4(),
            "credit_limit": Decimal("10000.00"),
            "total_outstanding_base": Decimal("500.00"),
            "credit_status": "GOOD",
        }
        for i in range(_CUSTOMER_COUNT)
    ]
    db.execute(insert(CustomerLedger), ledger_rows)

    # Spread due dates across current / 30 / 60 / 90+ day buckets.
    bucket_offsets = [10, -10, -45, -75, -120]
    txn_rows = [
        {
            "company_id": company_id,
            "customer_ledger_id": ledger_ids[i],
            "transaction_type": "INVOICE",
            "transaction_date": as_of_date - timedelta(days=30),
            "due_date": as_of_date
            + timedelta(days=bucket_offsets[i % len(bucket_offsets)]),
            "currency_code": "USD",
            "exchange_rate": Decimal("1"),
            "amount_foreign": Decimal("500.00"),
            "amount_base": Decimal("500.00"),
            "outstanding_amount": Decimal("500.00"),
            "status": "OPEN",
            "invoice_number": f"PERF-AR-{i:07d}",
        }
        for i in range(_CUSTOMER_COUNT)
    ]
    db.execute(insert(ARTransaction), txn_rows)
    db.commit()


class TestARAgingPerformance:
    def test_10000_customers_aging_under_5_seconds(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        as_of_date = date.today()

        seed_start = time.perf_counter()
        _seed_customers(db_session, company_id, as_of_date)
        seed_elapsed = time.perf_counter() - seed_start
        print(
            f"\nSeeded {_CUSTOMER_COUNT} customers + open invoices in {seed_elapsed:.2f}s"
        )

        ledger_repo = CustomerLedgerRepository(db_session)
        calculator = AgingCalculator(ledger_repo)
        assert (
            len(ledger_repo.get_aging_data(company_id, as_of_date)) == _CUSTOMER_COUNT
        )

        start = time.perf_counter()
        report = calculator.calculate_ar_aging(company_id, as_of_date)
        elapsed = time.perf_counter() - start

        print(f"AR aging over {_CUSTOMER_COUNT} customers: {elapsed:.3f}s")
        assert len(report.rows) == _CUSTOMER_COUNT
        assert elapsed < _TARGET_SECONDS, (
            f"AR aging over {_CUSTOMER_COUNT} customers took {elapsed:.2f}s, "
            f"exceeding the {_TARGET_SECONDS}s target."
        )

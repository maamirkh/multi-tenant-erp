"""T270 — representative scale on real PostgreSQL: offset pagination, GL
cursor continuity and export batching stay correct — every row exactly
once, totals reconciled, batches bounded.

Every dataset is seeded with **deliberate sort-key ties** (bulk inserts
share one ``now()``; many rows share a date or an amount). That is what
first exposed the platform-wide defect fixed in this phase: source queries
ordered by non-unique keys with no tiebreaker, so Postgres returned tied
rows in a different order per ``OFFSET`` page and pages overlapped/skipped
(sales.by_customer: 10,500 rows paged → 10,414 unique). Each report below
is walked end to end and must now return exactly its total, no duplicate.

Evidence-recorded, not a timing gate: elapsed times print with ``-s``.
"""

from __future__ import annotations

import math
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

import modules.reports.registry.load_all  # noqa: F401 — populates the registry
from modules.reports.registry.definitions import REPORT_REGISTRY
from modules.reports.services.adapters.base import (
    ADAPTER_REGISTRY,
    CursorReportResult,
    PaginatedReportResult,
)
from tests.integration.migrations.conftest import (
    _admin_engine,
    _real_database_url,
    _with_dbname,
    alembic_upgrade,
    db_engine,
)

SALES_ROWS = 10_500
CONTRACTS = 10_000
GL_ENTRIES = 5_500  # 2 lines each -> 11,000 GL lines
DOMAIN_ROWS = 3_000  # Purchase / Inventory / bank book
BATCH = 1_000
_C = "CAST(:c AS uuid)"


@dataclass
class Seeded:
    db: Session
    company: uuid.UUID
    bank_account: uuid.UUID


def _seed(conn: sa.Connection, company: str) -> str:
    def run(sql: str, **params: object) -> None:
        conn.execute(sa.text(sql), params)

    # Sales — 97 distinct totals across 10,500 customers -> heavy ties.
    run(
        f"""INSERT INTO sales_invoices (company_id, invoice_number, customer_id,
               invoice_date, due_date, currency_code, status, subtotal,
               discount_amount, tax_amount, charges_amount, total_amount, version)
           SELECT {_C}, 'INV-'||i, gen_random_uuid(), '2026-01-15', '2026-02-14', 'USD',
                  'ISSUED', 10 + (i % 97), 0, 0, 0, 10 + (i % 97), 1
           FROM generate_series(1, :n) i""",
        c=company,
        n=SALES_ROWS,
    )
    # Purchase — one statement each -> identical created_at / expected date.
    run(
        f"""INSERT INTO purchase_orders (company_id, po_number, supplier_id, status,
               currency_code, subtotal, total, expected_delivery_date)
           SELECT {_C}, 'PO-'||i, gen_random_uuid(), 'APPROVED', 'USD', 100, 100,
                  DATE '2026-01-10'
           FROM generate_series(1, :n) i""",
        c=company,
        n=DOMAIN_ROWS,
    )
    run(
        f"""INSERT INTO vendor_returns (company_id, rma_number, gr_id, supplier_id, status)
           SELECT {_C}, 'RMA-'||i, gen_random_uuid(), gen_random_uuid(), 'DRAFT'
           FROM generate_series(1, :n) i""",
        c=company,
        n=DOMAIN_ROWS,
    )
    run(
        f"""INSERT INTO purchase_cost_entries (company_id, gr_id, po_id, supplier_id,
               cost_date, subtotal, total_charges, total_discounts, tax_amount, total,
               currency_code)
           SELECT {_C}, gen_random_uuid(), gen_random_uuid(), gen_random_uuid(),
                  DATE '2026-01-05', 10 + (i % 50), 0, 0, 0, 10 + (i % 50), 'USD'
           FROM generate_series(1, :n) i""",
        c=company,
        n=DOMAIN_ROWS,
    )
    # Inventory alerts — identical created_at.
    run(
        f"""INSERT INTO inventory_low_stock_alerts (company_id, product_id, warehouse_id,
               alert_type, status, current_quantity, threshold_quantity)
           SELECT {_C}, gen_random_uuid(), gen_random_uuid(), 'OUT_OF_STOCK', 'OPEN', 0, 5
           FROM generate_series(1, :n) i""",
        c=company,
        n=DOMAIN_ROWS,
    )
    # Accounting — GL (unique cursor key) + a bank book with one shared date.
    cash, revenue, bank = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    run(
        f"""INSERT INTO accounting_accounts (id, company_id, account_code, account_name,
               account_type) VALUES (CAST(:a AS uuid), {_C}, '1000', 'Cash', 'ASSET'),
                                    (CAST(:r AS uuid), {_C}, '4000', 'Revenue', 'REVENUE')""",
        a=cash,
        r=revenue,
        c=company,
    )
    run(
        f"""INSERT INTO accounting_journal_entries (id, company_id, journal_number,
               journal_type, posting_source, posting_date, currency_code, status)
           SELECT md5('je'||i)::uuid, {_C}, 'JE-'||i, 'STANDARD', 'MANUAL',
                  DATE '2026-01-01' + (i % 60), 'USD', 'POSTED'
           FROM generate_series(1, :n) i""",
        c=company,
        n=GL_ENTRIES,
    )
    run(
        f"""INSERT INTO accounting_journal_lines (company_id, journal_entry_id, line_number,
               account_id, account_code, currency_code, debit_amount, credit_amount)
           SELECT {_C}, md5('je'||i)::uuid, 1, CAST(:a AS uuid), '1000', 'USD', 5, 0
           FROM generate_series(1, :n) i
           UNION ALL
           SELECT {_C}, md5('je'||i)::uuid, 2, CAST(:r AS uuid), '4000', 'USD', 0, 5
           FROM generate_series(1, :n) i""",
        c=company,
        a=cash,
        r=revenue,
        n=GL_ENTRIES,
    )
    run(
        f"""INSERT INTO accounting_bank_accounts (id, company_id, bank_name, account_number,
               currency_code, gl_account_id)
           VALUES (CAST(:b AS uuid), {_C}, 'T270 Bank', '0001', 'USD', CAST(:a AS uuid))""",
        b=bank,
        c=company,
        a=cash,
    )
    run(
        f"""INSERT INTO accounting_bank_transactions (company_id, bank_account_id,
               transaction_date, transaction_type, amount)
           SELECT {_C}, CAST(:b AS uuid), DATE '2026-01-15', 'RECEIPT', 10
           FROM generate_series(1, :n) i""",
        c=company,
        b=bank,
        n=DOMAIN_ROWS,
    )
    # Installments — identical contract_date; one line each, identical due_date.
    run(
        f"""INSERT INTO installment_contracts (id, company_id, contract_number, customer_id,
               sales_invoice_id, contract_date, principal_amount, down_payment_amount,
               contractual_total, installment_count, frequency, first_due_date,
               maturity_date, currency_code, terms_snapshot, status)
           SELECT md5('k'||i)::uuid, {_C}, 'IC-'||i, gen_random_uuid(), gen_random_uuid(),
                  DATE '2026-01-01', 100, 0, 100, 1, 'MONTHLY', DATE '2026-02-01',
                  DATE '2026-02-01', 'USD', '{{}}'::jsonb, 'ACTIVE'
           FROM generate_series(1, :n) i""",
        c=company,
        n=CONTRACTS,
    )
    run(
        f"""INSERT INTO installment_schedule_versions (id, company_id, contract_id,
               version_number, status)
           SELECT md5('v'||i)::uuid, {_C}, md5('k'||i)::uuid, 1, 'ACTIVE'
           FROM generate_series(1, :n) i""",
        c=company,
        n=CONTRACTS,
    )
    run(
        f"""UPDATE installment_contracts SET active_schedule_version_id =
               md5('v'||substr(contract_number, 4))::uuid WHERE company_id = {_C}""",
        c=company,
    )
    run(
        f"""INSERT INTO installment_schedule_lines (company_id, schedule_version_id,
               sequence, due_date, scheduled_amount)
           SELECT {_C}, md5('v'||i)::uuid, 1, DATE '2026-02-01', 100
           FROM generate_series(1, :n) i""",
        c=company,
        n=CONTRACTS,
    )
    conn.execute(sa.text("ANALYZE"))
    return bank


def _seed_stock_ledger(db: Session, company: uuid.UUID) -> None:
    """Stock ledger rows need a real product/warehouse (FKs); one shared
    performed_at makes every row a tie."""
    from tests.unit.modules.inventory.test_inventory_service_backward_compat import (
        _make_product,
        _make_warehouse,
    )

    warehouse = _make_warehouse(db, company)
    product = _make_product(db, company)
    db.commit()
    db.execute(
        sa.text(
            """INSERT INTO inventory_stock_movements (company_id, product_id,
                   warehouse_id, movement_type, direction, quantity, unit_cost,
                   performed_at)
               SELECT CAST(:c AS uuid), CAST(:p AS uuid), CAST(:w AS uuid), 'OPENING',
                      'IN', 1, 1, TIMESTAMPTZ '2026-01-15 12:00:00+00'
               FROM generate_series(1, :n) i"""
        ),
        {
            "c": str(company),
            "p": str(product.id),
            "w": str(warehouse.id),
            "n": DOMAIN_ROWS,
        },
    )
    db.commit()


def _create_company(engine: sa.Engine) -> uuid.UUID:
    """A real ``companies`` row — some domains (e.g. Inventory) carry a real
    FK to it in Postgres."""
    from modules.auth.models.user import User
    from modules.companies.models.company import Company

    suffix = uuid.uuid4().hex[:10]
    with sessionmaker(bind=engine)() as db:
        owner = User(email=f"t270-{suffix}@example.test", display_name="T270 Owner")
        db.add(owner)
        db.flush()
        company = Company(
            legal_name=f"T270 Scale Co {suffix}",
            slug=f"t270-scale-co-{suffix}",
            owner_id=owner.id,
            email=f"t270-{suffix}@example.com",
            status="active",
        )
        db.add(company)
        db.commit()
        return company.id


@pytest.fixture(scope="module")
def scaled() -> Iterator[Seeded]:
    """One throwaway database, seeded once (~60K rows) and shared by every
    test in this module; dropped afterwards. Same lifecycle as
    ``pg_test_db``, at module scope."""
    dbname = f"test_t270_{uuid.uuid4().hex[:12]}"
    admin = _admin_engine()
    with admin.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE "{dbname}"'))
    url = _with_dbname(_real_database_url(), dbname)
    engine = db_engine(url)
    db: Session | None = None
    try:
        alembic_upgrade(url, "head")
        company = _create_company(engine)
        with engine.begin() as conn:
            bank = _seed(conn, str(company))
        db = sessionmaker(bind=engine)()
        _seed_stock_ledger(db, company)
        yield Seeded(db=db, company=company, bank_account=uuid.UUID(bank))
    finally:
        if db is not None:
            db.close()
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :d AND pid <> pg_backend_pid()"
                ),
                {"d": dbname},
            )
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{dbname}"'))


def _filters(key: str, **values: object) -> BaseModel:
    return REPORT_REGISTRY[key].supported_filters(**values)


def _walk_pages(
    seeded: Seeded, key: str, identity: str, page_size: int, **filter_values: object
) -> tuple[list[str], int]:
    """Every offset page of *key*; returns (row identities, reported total)."""
    adapter = ADAPTER_REGISTRY[REPORT_REGISTRY[key].domain]
    filters = _filters(key, **filter_values)
    seen: list[str] = []
    total = -1
    page = 1
    while True:
        result = adapter.run(
            seeded.db, seeded.company, key, filters, page, page_size, None, None
        )
        assert isinstance(result, PaginatedReportResult)
        total = result.total
        rows = [str(r.model_dump()[identity]) for r in result.items]
        if not rows:
            return seen, total
        seen.extend(rows)
        page += 1
        assert page <= total + 2  # safety valve


# (report key, identity field, page size, expected rows)
_OFFSET_CASES: list[tuple[str, str, int, int]] = [
    ("sales.by_customer", "customer_id", 100, SALES_ROWS),
    ("purchase.summary", "po_id", 100, DOMAIN_ROWS),
    ("purchase.pending_deliveries", "po_id", 100, DOMAIN_ROWS),
    ("purchase.vendor_returns", "rma_id", 100, DOMAIN_ROWS),
    ("purchase.by_supplier", "supplier_id", 100, DOMAIN_ROWS),
    ("inventory.stock_position", "movement_id", 100, DOMAIN_ROWS),
    ("inventory.low_stock", "alert_id", 100, DOMAIN_ROWS),
    ("installments.register", "contract_id", 500, CONTRACTS),
    ("installments.due_overdue", "schedule_line_id", 500, CONTRACTS),
    ("installments.aging", "schedule_line_id", 500, CONTRACTS),
]


@pytest.mark.parametrize(
    ("key", "identity", "page_size", "expected"),
    _OFFSET_CASES,
    ids=[case[0] for case in _OFFSET_CASES],
)
def test_offset_pagination_has_no_duplicate_or_skip_under_ties(
    scaled: Seeded, key: str, identity: str, page_size: int, expected: int
) -> None:
    started = time.perf_counter()
    seen, total = _walk_pages(scaled, key, identity, page_size)
    print(
        f"\nT270 {key}: {len(seen)} rows / {math.ceil(len(seen) / page_size)} pages "
        f"in {time.perf_counter() - started:.2f}s"
    )
    assert total == expected, key
    assert len(seen) == expected, key
    duplicated = expected - len(set(seen))
    assert duplicated == 0, (
        f"{key}: {duplicated} row(s) duplicated/skipped across pages"
    )


def test_bank_book_pagination_under_same_day_ties(scaled: Seeded) -> None:
    seen, total = _walk_pages(
        scaled,
        "accounting.bank_cash_book",
        "transaction_id",
        100,
        account_type="bank",
        account_id=scaled.bank_account,
        from_date="2026-01-01",
        to_date="2026-01-31",
    )
    assert total == len(seen) == len(set(seen)) == DOMAIN_ROWS


def test_sales_export_batching_at_scale(scaled: Seeded) -> None:
    key = "sales.by_customer"
    adapter = ADAPTER_REGISTRY[REPORT_REGISTRY[key].domain]
    db, company = scaled.db, scaled.company
    assert adapter.count_export_rows(db, company, key, _filters(key)) == SALES_ROWS
    started = time.perf_counter()
    batches = list(
        adapter.iter_export_rows(db, company, key, _filters(key), None, BATCH)
    )
    print(
        f"\nT270 sales export: {len(batches)} batches "
        f"in {time.perf_counter() - started:.2f}s"
    )
    assert all(len(b) <= BATCH for b in batches)
    assert len(batches) == math.ceil(SALES_ROWS / BATCH)
    ids = [str(row.model_dump()["customer_id"]) for batch in batches for row in batch]
    assert len(ids) == len(set(ids)) == SALES_ROWS


def test_gl_cursor_continuity_at_scale(scaled: Seeded) -> None:
    key = "accounting.gl"
    adapter = ADAPTER_REGISTRY[REPORT_REGISTRY[key].domain]
    db, company = scaled.db, scaled.company
    expected = GL_ENTRIES * 2
    seen: list[tuple[str, str, int]] = []
    cursor: str | None = None
    pages = 0
    started = time.perf_counter()
    while True:
        result = adapter.run(
            db, company, key, _filters(key, cursor=cursor), 1, 500, None, None
        )
        assert isinstance(result, CursorReportResult)
        pages += 1
        for row in result.items:
            data = row.model_dump()
            seen.append(
                (
                    str(data["posting_date"]),
                    str(data["journal_entry_id"]),
                    data["line_number"],
                )
            )
        if not result.has_more:
            break
        cursor = result.next_cursor
        assert pages <= expected  # safety valve
    print(
        f"\nT270 GL cursor: {len(seen)} lines / {pages} pages "
        f"in {time.perf_counter() - started:.2f}s"
    )
    assert len(seen) == len(set(seen)) == expected
    assert seen == sorted(seen)  # stable, monotonic cursor order

    batches = list(
        adapter.iter_export_rows(db, company, key, _filters(key), None, BATCH)
    )
    assert all(len(b) <= BATCH for b in batches)
    assert sum(len(b) for b in batches) == expected

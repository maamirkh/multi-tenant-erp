"""T269 — no N+1: each list-shaped report's adapter call issues a fixed,
bounded number of SQL statements regardless of how many rows it returns.

Method (SQLAlchemy ``before_cursor_execute`` counting, never wall-clock):
seed ``N`` real rows for the report, then run the adapter once for a
1-row result and once for an ``N``-row result. Any per-row query makes the
second count grow with ``N``, so it must never exceed the first. (It may
be *lower*: when a page comes back short, several services skip their
separate count query — a legitimate optimization, not a variation.)
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.orm import Session

import modules.reports.registry.load_all  # noqa: F401 — populates the registry
from modules.reports.registry.definitions import REPORT_REGISTRY
from modules.reports.services.adapters.base import ADAPTER_REGISTRY
from tests.integration.api.v1.reports.conftest import (
    create_sales_customer,
    seed_sales_invoice,
)
from tests.unit.modules.inventory.test_inventory_service_backward_compat import (
    _seed as seed_inventory,
)
from tests.unit.modules.purchase.test_purchase_service_backward_compat import (
    _make_confirmed_gr,
    _make_po,
)

N = 6


@contextmanager
def count_queries(db: Session) -> Iterator[list[str]]:
    statements: list[str] = []
    engine = db.get_bind()

    def on_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(statement)

    sa.event.listen(engine, "before_cursor_execute", on_execute)
    try:
        yield statements
    finally:
        sa.event.remove(engine, "before_cursor_execute", on_execute)


# Reports whose result size is set by a filter rather than the page size.
_SIZE_FILTER = {"sales.top_customers": "limit"}
# Required filters (the schemas are extra="forbid" with no default).
_REQUIRED_FILTERS: dict[str, dict[str, object]] = {
    "accounting.ar_aging": {"as_of_date": date(2026, 3, 31)},
    "accounting.ap_aging": {"as_of_date": date(2026, 3, 31)},
}


def _run(
    db: Session, company_id: uuid.UUID, key: str, page_size: int
) -> tuple[int, int]:
    """(rows returned, statements issued) for one adapter call."""
    definition = REPORT_REGISTRY[key]
    kwargs: dict[str, object] = dict(_REQUIRED_FILTERS.get(key, {}))
    size_field = _SIZE_FILTER.get(key)
    if size_field:
        kwargs[size_field] = page_size
    filters: BaseModel = definition.supported_filters(**kwargs)
    adapter = ADAPTER_REGISTRY[definition.domain]
    db.expire_all()  # no identity-map hits hiding a per-row query
    with count_queries(db) as statements:
        result = adapter.run(db, company_id, key, filters, 1, page_size, None, None)
    items = getattr(result, "items", [])
    return len(items), len(statements)


# ---------------------------------------------------------------------------
# Seeders — each produces ≥ N rows for its report(s)
# ---------------------------------------------------------------------------


def _sales_by_date(db: Session, company_id: uuid.UUID) -> None:
    for i in range(N):
        seed_sales_invoice(
            db, company_id, amount="10.00", invoice_date=f"2026-01-{10 + i:02d}"
        )


def _sales_by_customer(db: Session, company_id: uuid.UUID) -> None:
    for _ in range(N):
        customer = create_sales_customer(db, company_id)
        seed_sales_invoice(db, company_id, amount="10.00", customer_id=customer.id)


def _purchase_orders(db: Session, company_id: uuid.UUID) -> None:
    for _ in range(N):
        _make_po(db, company_id, str(uuid.uuid4()))
    db.commit()


def _purchase_receipts(db: Session, company_id: uuid.UUID) -> None:
    for _ in range(N):
        supplier = str(uuid.uuid4())
        po = _make_po(db, company_id, supplier)
        _make_confirmed_gr(
            db,
            company_id,
            po_id=po.id,
            supplier_id=supplier,
            received_at=datetime(2026, 1, 5, tzinfo=UTC),
        )
    db.commit()


def _purchase_cost_entries(db: Session, company_id: uuid.UUID) -> None:
    from modules.purchase.models.cost import PurchaseCostEntry

    for i in range(N):
        db.add(
            PurchaseCostEntry(
                company_id=company_id,
                gr_id=str(uuid.uuid4()),
                po_id=str(uuid.uuid4()),
                supplier_id=str(uuid.uuid4()),
                cost_date=date(2026, 1, 5),
                subtotal=Decimal(f"{100 + i}.00"),
                total_charges=Decimal("0"),
                total_discounts=Decimal("0"),
                tax_amount=Decimal("0"),
                total=Decimal(f"{100 + i}.00"),
                currency_code="USD",
            )
        )
    db.commit()


def _inventory_recent_movements(db: Session, company_id: uuid.UUID) -> None:
    """Movements inside movement_velocity's default 90-day window."""
    from tests.unit.modules.inventory.test_inventory_service_backward_compat import (
        _make_movement,
        _make_product,
        _make_warehouse,
    )

    for _ in range(N):
        warehouse = _make_warehouse(db, company_id)
        product = _make_product(db, company_id)
        _make_movement(
            db,
            company_id,
            str(product.id),
            str(warehouse.id),
            performed_at=datetime.now(UTC) - timedelta(days=5),
        )
    db.commit()


def _inventory(db: Session, company_id: uuid.UUID) -> None:
    seed_inventory(db, company_id, n=N)


def _accounting_ar(db: Session, company_id: uuid.UUID) -> None:
    from modules.accounting.models.ar import ARTransaction, CustomerLedger

    for _ in range(N):
        ledger = CustomerLedger(company_id=company_id, customer_id=uuid.uuid4())
        db.add(ledger)
        db.flush()
        db.add(
            ARTransaction(
                company_id=company_id,
                customer_ledger_id=ledger.id,
                transaction_type="INVOICE",
                transaction_date=date(2026, 1, 1),
                due_date=date(2026, 1, 1) + timedelta(days=30),
                currency_code="USD",
                exchange_rate=Decimal("1"),
                amount_foreign=Decimal("100.00"),
                amount_base=Decimal("100.00"),
                outstanding_amount=Decimal("100.00"),
                status="OPEN",
            )
        )
    db.commit()


def _accounting_ap(db: Session, company_id: uuid.UUID) -> None:
    from modules.accounting.models.ap import APTransaction, SupplierLedger

    for _ in range(N):
        ledger = SupplierLedger(company_id=company_id, supplier_id=uuid.uuid4())
        db.add(ledger)
        db.flush()
        db.add(
            APTransaction(
                company_id=company_id,
                supplier_ledger_id=ledger.id,
                transaction_type="BILL",
                transaction_date=date(2026, 1, 1),
                due_date=date(2026, 1, 1) + timedelta(days=30),
                currency_code="USD",
                exchange_rate=Decimal("1"),
                amount_foreign=Decimal("100.00"),
                amount_base=Decimal("100.00"),
                outstanding_amount=Decimal("100.00"),
                status="OPEN",
            )
        )
    db.commit()


def _accounting_gl(db: Session, company_id: uuid.UUID) -> None:
    """Accounting's own report fixture: 3 posted entries = 6 GL lines."""
    from tests.integration.api.v1.accounting.test_reports_api import _setup

    _setup(db, company_id)
    db.commit()


CASES: list[tuple[str, Callable[[Session, uuid.UUID], None]]] = [
    ("sales.summary", _sales_by_date),
    ("sales.trend", _sales_by_date),
    ("sales.by_customer", _sales_by_customer),
    ("sales.top_customers", _sales_by_customer),
    ("purchase.summary", _purchase_orders),
    ("purchase.pending_deliveries", _purchase_orders),
    ("purchase.by_supplier", _purchase_cost_entries),
    ("purchase.supplier_performance", _purchase_receipts),
    ("inventory.stock_position", _inventory),
    ("inventory.dead_stock", _inventory),
    ("inventory.stock_aging", _inventory),
    ("inventory.movement_velocity", _inventory_recent_movements),
    ("accounting.ar_aging", _accounting_ar),
    ("accounting.ap_aging", _accounting_ap),
    ("accounting.gl", _accounting_gl),
]


@pytest.mark.parametrize(("key", "seed"), CASES, ids=[c[0] for c in CASES])
def test_query_count_is_independent_of_rows_returned(
    key: str, seed: Callable[[Session, uuid.UUID], None], db_session: Session
) -> None:
    company_id = uuid.uuid4()
    seed(db_session, company_id)

    one_row, one_row_queries = _run(db_session, company_id, key, page_size=1)
    many_rows, many_row_queries = _run(db_session, company_id, key, page_size=N)

    assert one_row == 1, f"{key}: seed produced no rows"
    assert many_rows > 1, f"{key}: seed produced only {many_rows} row(s)"
    assert many_row_queries <= one_row_queries, (
        f"{key}: {one_row_queries} statements for 1 row but "
        f"{many_row_queries} for {many_rows} rows — per-row queries (N+1)"
    )


# ---------------------------------------------------------------------------
# Structural guard for every list report (including those without a real-
# data case above): the only code an adapter runs per row may validate or
# map already-fetched data — never a call that can reach the database.
# ---------------------------------------------------------------------------

_PER_ROW_ALLOWED = {
    "model_validate",  # Pydantic validation of an already-fetched row
    "BankCashBookRow",  # Pydantic constructor
    "_alert_row",  # column-attribute mapping of an already-loaded ORM row
    "_parse_customer_uuid",  # pure string parsing
    "get",  # dict lookups on already-fetched data
    "Decimal",  # value constructor
    # FR-RPT-152 per-currency blocks: one entry per currency present in the
    # period (a handful), never per row.
    "PurchaseCurrencyAmounts",  # Pydantic constructor
    "SalesCurrencyKpis",  # Pydantic constructor
    "get_money_kpis",  # Sales money KPIs — one call per currency, not per row
    "CrmPipelineCurrency",  # Pydantic constructor
    "CrmPipelineValues",  # Pydantic constructor
    "CurrencyAmount",  # Pydantic constructor
    "get_pipeline_report",  # CRM pipeline — one call per currency, not per row
    "get_pipeline_values",  # CRM pipeline values — one call per currency
}


def _per_row_calls(source: str) -> set[str]:
    import ast

    calls: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(
            node, ast.ListComp | ast.GeneratorExp | ast.SetComp | ast.DictComp
        ):
            parts = (
                [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
            )
            for part in parts:
                for sub in ast.walk(part):
                    if isinstance(sub, ast.Call):
                        func = sub.func
                        name = (
                            func.attr
                            if isinstance(func, ast.Attribute)
                            else ast.unparse(func)
                        )
                        calls.add(name)
    return calls


def test_adapters_run_no_database_capable_call_per_row() -> None:
    import inspect

    from modules.inventory.models.alerts import LowStockAlert
    from modules.reports.services.adapters import (
        accounting_adapter,
        crm_adapter,
        installments_adapter,
        inventory_adapter,
        purchase_adapter,
        sales_adapter,
    )

    for module in (
        accounting_adapter,
        crm_adapter,
        installments_adapter,
        inventory_adapter,
        purchase_adapter,
        sales_adapter,
    ):
        unexpected = _per_row_calls(inspect.getsource(module)) - _PER_ROW_ALLOWED
        assert unexpected == set(), f"{module.__name__}: per-row calls {unexpected}"

    # _alert_row only reads plain columns: LowStockAlert has no relationship
    # attribute that could lazy-load per row.
    assert not sa.inspect(LowStockAlert).relationships

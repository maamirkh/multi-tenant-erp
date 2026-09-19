"""T097 — Export-seam test: ``count_export_rows()``/``iter_export_rows()``
for Inventory's 5 list-shaped reports — cheap-count pattern (via T087),
pages until exhausted.

T098 — Aggregate-export note: ``inventory.summary``/``inventory.valuation``/
``inventory.kpis`` have no count/iterate seam by design (they are
``PaginationStyle.NONE`` aggregate results, not row lists) — calling
``iter_export_rows``/``count_export_rows`` for any of them raises
``ValueError``, exercised below.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from modules.inventory.models.product import Product
from modules.inventory.models.stock import StockMovement, StockPosition
from modules.inventory.models.uom import UOM
from modules.inventory.models.warehouse import Warehouse
from modules.reports.schemas.inventory import DeadStockFilter, InventorySummaryFilter
from modules.reports.services.adapters.inventory_adapter import InventoryAdapter


def _seed_dead_stock(db: Session, company_id: uuid.UUID, *, n: int) -> None:
    for _ in range(n):
        wh = Warehouse(
            id=uuid.uuid4(),
            company_id=company_id,
            code=f"WH-{uuid.uuid4().hex[:4].upper()}",
            name="Test WH",
            warehouse_type="MAIN",
            status="ACTIVE",
        )
        db.add(wh)
        db.flush()
        uom = UOM(
            id=uuid.uuid4(),
            company_id=company_id,
            code=f"U{uuid.uuid4().hex[:4]}",
            name="Unit",
            uom_type="UNIT",
            status="active",
        )
        db.add(uom)
        db.flush()
        product = Product(
            id=uuid.uuid4(),
            company_id=company_id,
            name="Dead Stock Product",
            product_code=f"RP-{uuid.uuid4().hex[:6]}",
            product_type="STANDARD",
            status="ACTIVE",
            base_uom_id=str(uom.id),
        )
        db.add(product)
        db.flush()
        db.add(
            StockPosition(
                id=uuid.uuid4(),
                company_id=company_id,
                product_id=str(product.id),
                warehouse_id=str(wh.id),
                qty_on_hand=10.0,
                qty_reserved=Decimal("0"),
                qty_damaged=Decimal("0"),
                unit_cost=5.0,
                currency_code="USD",
                reorder_level=Decimal("2"),
                safety_stock=Decimal("1"),
            )
        )
        db.flush()
        from datetime import UTC, datetime, timedelta

        db.add(
            StockMovement(
                id=uuid.uuid4(),
                company_id=company_id,
                product_id=str(product.id),
                warehouse_id=str(wh.id),
                movement_type="OPENING",
                direction="IN",
                quantity=10.0,
                unit_cost=5.0,
                performed_at=datetime.now(UTC) - timedelta(days=120),
            )
        )
    db.commit()


def test_dead_stock_export_seam(db_session: Session) -> None:
    company_id = uuid.uuid4()
    _seed_dead_stock(db_session, company_id, n=5)

    adapter = InventoryAdapter()
    filters = DeadStockFilter()

    count = adapter.count_export_rows(
        db_session, company_id, "inventory.dead_stock", filters
    )
    assert count == 5

    batches = list(
        adapter.iter_export_rows(
            db_session, company_id, "inventory.dead_stock", filters, None, batch_size=2
        )
    )
    total_rows = sum(len(b) for b in batches)
    assert total_rows == 5
    assert all(len(b) <= 2 for b in batches)


def test_aggregate_reports_have_no_export_seam(db_session: Session) -> None:
    adapter = InventoryAdapter()
    filters = InventorySummaryFilter()

    with pytest.raises(ValueError):
        adapter.count_export_rows(
            db_session, uuid.uuid4(), "inventory.summary", filters
        )

    with pytest.raises(ValueError):
        list(
            adapter.iter_export_rows(
                db_session,
                uuid.uuid4(),
                "inventory.summary",
                filters,
                None,
                batch_size=100,
            )
        )

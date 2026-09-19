"""T095 (corrected — adapter-level) — ``ReportQueryService``/``KPIService``
called directly vs. ``InventoryAdapter.run()`` — identical for
``inventory.summary``/``inventory.kpis``."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.inventory.models.product import Product
from modules.inventory.models.stock import StockPosition
from modules.inventory.models.uom import UOM
from modules.inventory.models.warehouse import Warehouse
from modules.inventory.services.kpi_service import KPIService
from modules.inventory.services.report_service import ReportQueryService
from modules.reports.schemas.inventory import InventoryKpiFilter, InventorySummaryFilter
from modules.reports.services.adapters.base import AggregateReportResult
from modules.reports.services.adapters.inventory_adapter import InventoryAdapter


def _seed(db: Session, company_id: uuid.UUID) -> None:
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
        name="Report Product",
        product_code=f"RP-{uuid.uuid4().hex[:6]}",
        product_type="STANDARD",
        status="ACTIVE",
        base_uom_id=str(uom.id),
    )
    db.add(product)
    db.flush()
    pos = StockPosition(
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
    db.add(pos)
    db.commit()


def test_inventory_summary_equivalence(db_session: Session) -> None:
    company_id = uuid.uuid4()
    _seed(db_session, company_id)

    reports = ReportQueryService(db_session)
    direct = reports.inventory_summary(company_id=company_id)

    adapter = InventoryAdapter()
    result = adapter.run(
        db_session,
        company_id,
        "inventory.summary",
        InventorySummaryFilter(),
        page=1,
        page_size=20,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, AggregateReportResult)
    assert result.data.grand_total_value == direct["grand_total_value"]
    assert len(result.data.rows) == len(direct["rows"])


def test_inventory_kpis_equivalence(db_session: Session) -> None:
    company_id = uuid.uuid4()
    _seed(db_session, company_id)

    kpis = KPIService(db_session)
    direct = kpis.compute(company_id=company_id)

    adapter = InventoryAdapter()
    result = adapter.run(
        db_session,
        company_id,
        "inventory.kpis",
        InventoryKpiFilter(),
        page=1,
        page_size=1,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, AggregateReportResult)
    dumped = result.data.model_dump()
    for key, value in direct.items():
        if key == "as_of":
            continue  # each call computes its own timestamp
        assert dumped[key] == value

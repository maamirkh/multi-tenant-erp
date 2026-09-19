"""T088 — Epic 11 Reports additive source-domain seam (T087) regression.

Proves ``dead_stock``/``movement_velocity``/``stock_aging``'s new optional
``limit``/``offset`` parameters (default ``None``/``0``) reproduce the exact
prior unbounded output for existing callers, and that the new
``count_*``/``count_for_company`` sibling methods return the correct
population size.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.inventory.models.alerts import LowStockAlert, ReorderRule
from modules.inventory.models.product import Product
from modules.inventory.models.stock import StockMovement, StockPosition
from modules.inventory.models.uom import UOM
from modules.inventory.models.warehouse import Warehouse
from modules.inventory.repositories.alerts_repository import (
    LowStockAlertRepository,
    ReorderRuleRepository,
)
from modules.inventory.services.report_service import ReportQueryService


def _make_warehouse(db: Session, company_id: uuid.UUID) -> Warehouse:
    wh = Warehouse(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"WH-{uuid.uuid4().hex[:4].upper()}",
        name=f"Test WH {uuid.uuid4().hex[:4]}",
        warehouse_type="MAIN",
        status="ACTIVE",
    )
    db.add(wh)
    db.flush()
    return wh


def _make_product(db: Session, company_id: uuid.UUID) -> Product:
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
        name=f"Report Product {uuid.uuid4().hex[:6]}",
        product_code=f"RP-{uuid.uuid4().hex[:6]}",
        product_type="STANDARD",
        status="ACTIVE",
        base_uom_id=str(uom.id),
    )
    db.add(product)
    db.flush()
    return product


def _make_position(
    db: Session, company_id: uuid.UUID, product_id: str, warehouse_id: str
) -> StockPosition:
    pos = StockPosition(
        id=uuid.uuid4(),
        company_id=company_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        qty_on_hand=10.0,
        qty_reserved=Decimal("0"),
        qty_damaged=Decimal("0"),
        unit_cost=5.0,
        currency_code="USD",
        reorder_level=Decimal("2"),
        safety_stock=Decimal("1"),
    )
    db.add(pos)
    db.flush()
    return pos


def _make_movement(
    db: Session,
    company_id: uuid.UUID,
    product_id: str,
    warehouse_id: str,
    performed_at: datetime,
) -> StockMovement:
    mov = StockMovement(
        id=uuid.uuid4(),
        company_id=company_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type="OPENING",
        direction="IN",
        quantity=10.0,
        unit_cost=5.0,
        performed_at=performed_at,
    )
    db.add(mov)
    db.flush()
    return mov


def _seed(db: Session, company_id: uuid.UUID, *, n: int = 3) -> None:
    for _ in range(n):
        wh = _make_warehouse(db, company_id)
        prod = _make_product(db, company_id)
        _make_position(db, company_id, str(prod.id), str(wh.id))
        _make_movement(
            db,
            company_id,
            str(prod.id),
            str(wh.id),
            performed_at=datetime.now(UTC) - timedelta(days=120),
        )
    db.commit()


def test_dead_stock_unbounded_call_unchanged(db_session: Session) -> None:
    company_id = uuid.uuid4()
    _seed(db_session, company_id, n=3)
    service = ReportQueryService(db_session)

    result = service.dead_stock(company_id=company_id)
    assert len(result["rows"]) == 3
    assert service.count_dead_stock(company_id=company_id) == 3


def test_dead_stock_bounded_page_is_subset_of_unbounded(db_session: Session) -> None:
    company_id = uuid.uuid4()
    _seed(db_session, company_id, n=3)
    service = ReportQueryService(db_session)

    full = service.dead_stock(company_id=company_id)["rows"]
    page = service.dead_stock(company_id=company_id, limit=2, offset=0)["rows"]
    assert len(page) == 2
    assert page == full[:2]


def test_movement_velocity_unbounded_call_unchanged(db_session: Session) -> None:
    company_id = uuid.uuid4()
    for _ in range(3):
        wh = _make_warehouse(db_session, company_id)
        prod = _make_product(db_session, company_id)
        _make_position(db_session, company_id, str(prod.id), str(wh.id))
        _make_movement(
            db_session,
            company_id,
            str(prod.id),
            str(wh.id),
            performed_at=datetime.now(UTC) - timedelta(days=10),
        )
    db_session.commit()
    service = ReportQueryService(db_session)

    result = service.movement_velocity(company_id=company_id)
    assert result["total_products_with_movement"] == 3
    assert service.count_movement_velocity(company_id=company_id) == 3


def test_stock_aging_unbounded_call_unchanged(db_session: Session) -> None:
    company_id = uuid.uuid4()
    _seed(db_session, company_id, n=3)
    service = ReportQueryService(db_session)

    full = service.stock_aging(company_id=company_id)["rows"]
    assert len(full) == 3
    assert service.count_stock_aging(company_id=company_id) == 3

    page = service.stock_aging(company_id=company_id, limit=2, offset=0)["rows"]
    assert len(page) == 2
    assert page == full[:2]


def test_low_stock_alert_count_matches_list(db_session: Session) -> None:
    company_id = uuid.uuid4()
    for _ in range(3):
        wh = _make_warehouse(db_session, company_id)
        prod = _make_product(db_session, company_id)
        db_session.add(
            LowStockAlert(
                company_id=company_id,
                product_id=str(prod.id),
                warehouse_id=str(wh.id),
                alert_type="LOW_STOCK",
                status="OPEN",
                current_quantity=Decimal("1"),
                threshold_quantity=Decimal("2"),
            )
        )
    db_session.commit()

    repo = LowStockAlertRepository(db_session)
    listed = repo.list_for_company(company_id=company_id)
    counted = repo.count_for_company(company_id=company_id)
    assert counted == len(listed) == 3


def test_reorder_rule_count_matches_list(db_session: Session) -> None:
    company_id = uuid.uuid4()
    prod = _make_product(db_session, company_id)
    for _ in range(2):
        db_session.add(
            ReorderRule(
                company_id=company_id,
                product_id=str(prod.id),
                reorder_level=Decimal("5"),
                reorder_quantity=Decimal("10"),
                is_active=True,
            )
        )
    db_session.commit()

    repo = ReorderRuleRepository(db_session)
    listed = repo.list_for_company(company_id=company_id)
    counted = repo.count_for_company(company_id=company_id)
    assert counted == len(listed) == 2

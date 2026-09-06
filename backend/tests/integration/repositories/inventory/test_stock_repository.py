"""Integration tests for StockPositionRepository, StockMovementRepository, SnapshotRepository.

Tests:
  - StockPositionRepository: get_or_create, get_by_product_warehouse, list_by_warehouse/product
  - StockMovementRepository: append (insert only), list, count
  - SnapshotRepository: create header + lines, list
  - Tenant isolation (company_id scoping)
  - has_stock returns True only when qty_on_hand > 0

Spec ref: specs/005-inventory-management/spec.md §15
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.inventory.models.stock import (
    InventorySnapshot,
    InventorySnapshotLine,
    StockMovement,
    StockPosition,
)
from modules.inventory.models.warehouse import Warehouse
from modules.inventory.repositories.stock_repository import (
    SnapshotRepository,
    StockMovementRepository,
    StockPositionRepository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_warehouse(db: Session, company_id: uuid.UUID) -> Warehouse:
    wh = Warehouse(
        company_id=company_id,
        code=f"WH-{uuid.uuid4().hex[:4].upper()}",
        name="Test Warehouse",
        warehouse_type="MAIN",
        status="ACTIVE",
    )
    db.add(wh)
    db.flush()
    return wh


def _make_position(
    db: Session,
    company_id: uuid.UUID,
    product_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    qty: Decimal = Decimal("0"),
) -> StockPosition:
    pos = StockPosition(
        company_id=company_id,
        product_id=str(product_id),
        warehouse_id=str(warehouse_id),
        qty_on_hand=qty,
        qty_reserved=Decimal("0"),
        qty_damaged=Decimal("0"),
    )
    db.add(pos)
    db.flush()
    return pos


def _make_movement(
    db: Session,
    company_id: uuid.UUID,
    product_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    movement_type: str = "OPENING",
    direction: str = "IN",
    quantity: Decimal = Decimal("10"),
) -> StockMovement:
    from core.utils.datetime import utcnow

    mov = StockMovement(
        company_id=company_id,
        product_id=str(product_id),
        warehouse_id=str(warehouse_id),
        movement_type=movement_type,
        direction=direction,
        quantity=quantity,
        performed_at=utcnow(),
    )
    db.add(mov)
    db.flush()
    return mov


# ---------------------------------------------------------------------------
# StockPositionRepository tests
# ---------------------------------------------------------------------------


class TestStockPositionRepository:
    def test_get_or_create_creates_when_missing(self, db_session: Session):
        cid = uuid.uuid4()
        pid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        repo = StockPositionRepository(db_session)

        pos, created = repo.get_or_create(
            company_id=cid,
            product_id=pid,
            warehouse_id=wh.id,
        )
        assert created is True
        assert pos is not None
        assert pos.qty_on_hand == Decimal("0")

    def test_get_or_create_returns_existing(self, db_session: Session):
        cid = uuid.uuid4()
        pid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        repo = StockPositionRepository(db_session)

        pos1, _ = repo.get_or_create(company_id=cid, product_id=pid, warehouse_id=wh.id)
        pos2, created = repo.get_or_create(
            company_id=cid, product_id=pid, warehouse_id=wh.id
        )

        assert created is False
        assert str(pos1.id) == str(pos2.id)

    def test_get_by_product_warehouse(self, db_session: Session):
        cid = uuid.uuid4()
        pid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        _make_position(db_session, cid, pid, wh.id, Decimal("50"))
        repo = StockPositionRepository(db_session)

        pos = repo.get_by_product_warehouse(
            company_id=cid, product_id=pid, warehouse_id=wh.id
        )
        assert pos is not None
        assert pos.qty_on_hand == Decimal("50")

    def test_get_by_product_warehouse_cross_company_isolation(
        self, db_session: Session
    ):
        cid1 = uuid.uuid4()
        cid2 = uuid.uuid4()
        pid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid1)
        _make_position(db_session, cid1, pid, wh.id)
        repo = StockPositionRepository(db_session)

        pos = repo.get_by_product_warehouse(
            company_id=cid2, product_id=pid, warehouse_id=wh.id
        )
        assert pos is None

    def test_list_by_warehouse(self, db_session: Session):
        cid = uuid.uuid4()
        pid1 = uuid.uuid4()
        pid2 = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        _make_position(db_session, cid, pid1, wh.id)
        _make_position(db_session, cid, pid2, wh.id)
        repo = StockPositionRepository(db_session)

        positions = repo.list_by_warehouse(company_id=cid, warehouse_id=wh.id)
        assert len(positions) == 2

    def test_list_by_product(self, db_session: Session):
        cid = uuid.uuid4()
        pid = uuid.uuid4()
        wh1 = _make_warehouse(db_session, cid)
        wh2 = _make_warehouse(db_session, cid)
        _make_position(db_session, cid, pid, wh1.id)
        _make_position(db_session, cid, pid, wh2.id)
        repo = StockPositionRepository(db_session)

        positions = repo.list_by_product(company_id=cid, product_id=pid)
        assert len(positions) == 2

    def test_list_for_company(self, db_session: Session):
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        pid1, pid2 = uuid.uuid4(), uuid.uuid4()
        _make_position(db_session, cid, pid1, wh.id)
        _make_position(db_session, cid, pid2, wh.id)
        repo = StockPositionRepository(db_session)

        positions = repo.list_for_company(company_id=cid)
        assert len(positions) >= 2

    def test_has_stock_false_when_zero_qty(self, db_session: Session):
        cid = uuid.uuid4()
        pid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        _make_position(db_session, cid, pid, wh.id, Decimal("0"))
        repo = StockPositionRepository(db_session)

        assert repo.has_stock(company_id=cid, warehouse_id=wh.id) is False

    def test_has_stock_true_when_positive_qty(self, db_session: Session):
        cid = uuid.uuid4()
        pid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        _make_position(db_session, cid, pid, wh.id, Decimal("5"))
        repo = StockPositionRepository(db_session)

        assert repo.has_stock(company_id=cid, warehouse_id=wh.id) is True

    def test_variant_id_none_filter(self, db_session: Session):
        """get_by_product_warehouse with variant_id=None doesn't match variant rows."""
        cid = uuid.uuid4()
        pid = uuid.uuid4()
        vid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)

        # Create position with a variant_id
        pos_with_variant = StockPosition(
            company_id=cid,
            product_id=str(pid),
            warehouse_id=str(wh.id),
            variant_id=str(vid),
            qty_on_hand=Decimal("10"),
            qty_reserved=Decimal("0"),
            qty_damaged=Decimal("0"),
        )
        db_session.add(pos_with_variant)
        db_session.flush()

        repo = StockPositionRepository(db_session)
        # Searching without variant should return None (no base position)
        pos = repo.get_by_product_warehouse(
            company_id=cid, product_id=pid, warehouse_id=wh.id
        )
        assert pos is None


# ---------------------------------------------------------------------------
# StockMovementRepository tests (INSERT ONLY)
# ---------------------------------------------------------------------------


class TestStockMovementRepository:
    def test_append_creates_movement(self, db_session: Session):
        cid = uuid.uuid4()
        pid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        repo = StockMovementRepository(db_session)

        mov = _make_movement(db_session, cid, pid, wh.id)
        assert mov.id is not None
        assert mov.movement_type == "OPENING"

    def test_list_by_product_warehouse(self, db_session: Session):
        cid = uuid.uuid4()
        pid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        _make_movement(db_session, cid, pid, wh.id)
        _make_movement(db_session, cid, pid, wh.id, movement_type="ADJUSTMENT_IN")
        repo = StockMovementRepository(db_session)

        movements = repo.list_by_product_warehouse(
            company_id=cid, product_id=pid, warehouse_id=wh.id
        )
        assert len(movements) == 2

    def test_list_filtered_by_movement_type(self, db_session: Session):
        cid = uuid.uuid4()
        pid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        _make_movement(db_session, cid, pid, wh.id, movement_type="OPENING")
        _make_movement(db_session, cid, pid, wh.id, movement_type="ADJUSTMENT_IN")
        repo = StockMovementRepository(db_session)

        openings = repo.list_by_product_warehouse(
            company_id=cid, movement_type="OPENING"
        )
        assert all(m.movement_type == "OPENING" for m in openings)

    def test_count_returns_correct_number(self, db_session: Session):
        cid = uuid.uuid4()
        pid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        _make_movement(db_session, cid, pid, wh.id)
        _make_movement(db_session, cid, pid, wh.id)
        repo = StockMovementRepository(db_session)

        count = repo.count(company_id=cid, product_id=pid)
        assert count == 2

    def test_cross_company_isolation(self, db_session: Session):
        cid1 = uuid.uuid4()
        cid2 = uuid.uuid4()
        pid = uuid.uuid4()
        wh1 = _make_warehouse(db_session, cid1)
        _make_movement(db_session, cid1, pid, wh1.id)
        repo = StockMovementRepository(db_session)

        movements = repo.list_by_product_warehouse(company_id=cid2, product_id=pid)
        assert len(movements) == 0


# ---------------------------------------------------------------------------
# SnapshotRepository tests
# ---------------------------------------------------------------------------


class TestSnapshotRepository:
    def _make_snapshot(self, db: Session, company_id: uuid.UUID) -> InventorySnapshot:
        snap = InventorySnapshot(
            company_id=company_id,
            snapshot_name="Test Snapshot",
            status="COMPLETED",
            total_products=0,
            total_warehouses=0,
        )
        db.add(snap)
        db.flush()
        return snap

    def test_list_for_company(self, db_session: Session):
        cid = uuid.uuid4()
        self._make_snapshot(db_session, cid)
        self._make_snapshot(db_session, cid)
        repo = SnapshotRepository(db_session)

        snaps = repo.list_for_company(company_id=cid)
        assert len(snaps) == 2

    def test_list_for_company_isolation(self, db_session: Session):
        cid1 = uuid.uuid4()
        cid2 = uuid.uuid4()
        self._make_snapshot(db_session, cid1)
        repo = SnapshotRepository(db_session)

        snaps = repo.list_for_company(company_id=cid2)
        assert len(snaps) == 0

    def test_list_lines(self, db_session: Session):
        cid = uuid.uuid4()
        pid = uuid.uuid4()
        wh_id = uuid.uuid4()
        snap = self._make_snapshot(db_session, cid)

        line = InventorySnapshotLine(
            company_id=cid,
            snapshot_id=str(snap.id),
            product_id=str(pid),
            warehouse_id=str(wh_id),
            qty_on_hand=Decimal("10"),
            qty_reserved=Decimal("0"),
            qty_damaged=Decimal("0"),
        )
        db_session.add(line)
        db_session.flush()

        repo = SnapshotRepository(db_session)
        lines = repo.list_lines(company_id=cid, snapshot_id=snap.id)
        assert len(lines) == 1
        assert lines[0].qty_on_hand == Decimal("10")

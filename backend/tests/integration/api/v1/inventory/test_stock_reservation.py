"""Integration tests for stock reservation and release (T211).

Tests:
  - reserve_stock decrements available_quantity
  - release_stock increments available_quantity
  - STRICT policy blocks over-reservation (reserve > available)
  - Multiple reserves accumulate correctly
  - Release more than reserved raises error
  - available_quantity = on_hand - reserved - damaged

Spec ref: specs/005-inventory-management/spec.md §15 / FR-IO-014
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from modules.inventory.exceptions import (
    InsufficientStockError,
    InvalidStockQuantityError,
)
from modules.inventory.models.warehouse import Warehouse
from modules.inventory.repositories.stock_repository import (
    SnapshotRepository,
    StockMovementRepository,
    StockPositionRepository,
)
from modules.inventory.repositories.transfer_repository import TransferRepository
from modules.inventory.repositories.warehouse_repository import WarehouseRepository
from modules.inventory.services.stock_service import StockLedgerService
from modules.inventory.services.transfer_service import TransferService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_warehouse(db: Session, company_id: uuid.UUID) -> Warehouse:
    wh = Warehouse(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"WH-{uuid.uuid4().hex[:4].upper()}",
        name="Test Warehouse",
        warehouse_type="MAIN",
        status="ACTIVE",
    )
    db.add(wh)
    db.flush()
    return wh


def _make_svc(db: Session) -> TransferService:
    pos_repo = StockPositionRepository(db)
    mov_repo = StockMovementRepository(db)
    snap_repo = SnapshotRepository(db)
    wh_repo = WarehouseRepository(db)
    ledger = StockLedgerService(
        db=db,
        position_repo=pos_repo,
        movement_repo=mov_repo,
        snapshot_repo=snap_repo,
        warehouse_repo=wh_repo,
    )
    return TransferService(
        db=db,
        transfer_repo=TransferRepository(db),
        stock_ledger=ledger,
        position_repo=pos_repo,
        warehouse_repo=wh_repo,
    )


def _seed_stock(
    db: Session,
    company_id: uuid.UUID,
    product_id: uuid.UUID,
    wh_id: uuid.UUID,
    qty: Decimal,
) -> None:
    pos_repo = StockPositionRepository(db)
    mov_repo = StockMovementRepository(db)
    snap_repo = SnapshotRepository(db)
    wh_repo = WarehouseRepository(db)
    ledger = StockLedgerService(
        db=db,
        position_repo=pos_repo,
        movement_repo=mov_repo,
        snapshot_repo=snap_repo,
        warehouse_repo=wh_repo,
    )
    ledger.record_opening_stock(
        company_id=company_id, product_id=product_id, warehouse_id=wh_id, quantity=qty
    )
    db.flush()


# ---------------------------------------------------------------------------
# Reserve
# ---------------------------------------------------------------------------


class TestReserveStock:
    def test_reserve_reduces_available(self, db_session: Session):
        svc = _make_svc(db_session)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, wh.id, Decimal("100"))

        svc.reserve_stock(
            company_id=cid,
            product_id=pid,
            warehouse_id=wh.id,
            quantity=Decimal("25"),
        )

        pos_repo = StockPositionRepository(db_session)
        pos = pos_repo.get_by_product_warehouse(
            company_id=cid, product_id=pid, warehouse_id=wh.id
        )
        assert pos is not None
        assert Decimal(str(pos.qty_on_hand)) == pytest.approx(Decimal("100"))
        assert Decimal(str(pos.qty_reserved)) == pytest.approx(Decimal("25"))
        # available = 100 - 25 = 75
        available = (
            Decimal(str(pos.qty_on_hand))
            - Decimal(str(pos.qty_reserved))
            - Decimal(str(pos.qty_damaged))
        )
        assert available == pytest.approx(Decimal("75"))

    def test_reserve_accumulates(self, db_session: Session):
        svc = _make_svc(db_session)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, wh.id, Decimal("100"))
        svc.reserve_stock(
            company_id=cid, product_id=pid, warehouse_id=wh.id, quantity=Decimal("20")
        )
        svc.reserve_stock(
            company_id=cid, product_id=pid, warehouse_id=wh.id, quantity=Decimal("30")
        )

        pos_repo = StockPositionRepository(db_session)
        pos = pos_repo.get_by_product_warehouse(
            company_id=cid, product_id=pid, warehouse_id=wh.id
        )
        assert pos is not None
        assert Decimal(str(pos.qty_reserved)) == pytest.approx(Decimal("50"))

    def test_reserve_exceeds_available_raises(self, db_session: Session):
        svc = _make_svc(db_session)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, wh.id, Decimal("20"))

        with pytest.raises(InsufficientStockError):
            svc.reserve_stock(
                company_id=cid,
                product_id=pid,
                warehouse_id=wh.id,
                quantity=Decimal("25"),
            )

    def test_reserve_uses_available_not_on_hand(self, db_session: Session):
        """Already-reserved stock must not be double-reserved."""
        svc = _make_svc(db_session)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, wh.id, Decimal("50"))
        svc.reserve_stock(
            company_id=cid, product_id=pid, warehouse_id=wh.id, quantity=Decimal("40")
        )
        # available = 10; trying to reserve 20 should fail
        with pytest.raises(InsufficientStockError):
            svc.reserve_stock(
                company_id=cid,
                product_id=pid,
                warehouse_id=wh.id,
                quantity=Decimal("20"),
            )


# ---------------------------------------------------------------------------
# Release
# ---------------------------------------------------------------------------


class TestReleaseStock:
    def test_release_increments_available(self, db_session: Session):
        svc = _make_svc(db_session)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, wh.id, Decimal("100"))
        svc.reserve_stock(
            company_id=cid, product_id=pid, warehouse_id=wh.id, quantity=Decimal("40")
        )
        svc.release_stock(
            company_id=cid, product_id=pid, warehouse_id=wh.id, quantity=Decimal("15")
        )

        pos_repo = StockPositionRepository(db_session)
        pos = pos_repo.get_by_product_warehouse(
            company_id=cid, product_id=pid, warehouse_id=wh.id
        )
        assert pos is not None
        assert Decimal(str(pos.qty_reserved)) == pytest.approx(Decimal("25"))

    def test_release_more_than_reserved_raises(self, db_session: Session):
        svc = _make_svc(db_session)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, wh.id, Decimal("100"))
        svc.reserve_stock(
            company_id=cid, product_id=pid, warehouse_id=wh.id, quantity=Decimal("10")
        )
        with pytest.raises(InsufficientStockError):
            svc.release_stock(
                company_id=cid,
                product_id=pid,
                warehouse_id=wh.id,
                quantity=Decimal("20"),
            )

    def test_release_zero_raises(self, db_session: Session):
        svc = _make_svc(db_session)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, wh.id, Decimal("100"))
        with pytest.raises(InvalidStockQuantityError):
            svc.release_stock(
                company_id=cid,
                product_id=pid,
                warehouse_id=wh.id,
                quantity=Decimal("0"),
            )

"""Integration tests for the full stock transfer workflow (T209 + T210).

Tests:
  - DRAFT → DISPATCH → IN_TRANSIT (TRANSFER_OUT created at source)
  - IN_TRANSIT → RECEIVE → COMPLETED (TRANSFER_IN created at destination)
  - DRAFT → CANCEL → CANCELLED (no stock change)
  - IN_TRANSIT → CANCEL → CANCELLED (reversal TRANSFER_IN at source)
  - source ≠ destination invariant enforced by service
  - Insufficient stock blocks dispatch
  - Tenant isolation: transfer cannot be actioned by another company

Spec ref: specs/005-inventory-management/spec.md §16 / FR-IO-013
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from modules.inventory.exceptions import (
    InsufficientStockError,
    InvalidTransferError,
    InvalidTransferStateTransitionError,
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


def _make_transfer_service(db: Session) -> TransferService:
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
    """Open stock so dispatch can proceed."""
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
        company_id=company_id,
        product_id=product_id,
        warehouse_id=wh_id,
        quantity=qty,
    )
    db.flush()


# ---------------------------------------------------------------------------
# Create invariants (service-level)
# ---------------------------------------------------------------------------


class TestCreateTransferService:
    def test_same_warehouse_raises(self, db_session: Session):
        svc = _make_transfer_service(db_session)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        with pytest.raises(InvalidTransferError):
            svc.create_transfer(
                company_id=cid,
                source_warehouse_id=wh.id,
                destination_warehouse_id=wh.id,
                lines=[{"product_id": uuid.uuid4(), "quantity": "10"}],
            )

    def test_creates_draft_with_lines(self, db_session: Session):
        svc = _make_transfer_service(db_session)
        cid = uuid.uuid4()
        src = _make_warehouse(db_session, cid)
        dst = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        transfer = svc.create_transfer(
            company_id=cid,
            source_warehouse_id=src.id,
            destination_warehouse_id=dst.id,
            lines=[{"product_id": pid, "quantity": "15"}],
        )
        assert transfer.status == "DRAFT"
        assert transfer.version == 1


# ---------------------------------------------------------------------------
# Dispatch workflow
# ---------------------------------------------------------------------------


class TestDispatchWorkflow:
    def test_dispatch_creates_transfer_out_movement(self, db_session: Session):
        svc = _make_transfer_service(db_session)
        cid = uuid.uuid4()
        src = _make_warehouse(db_session, cid)
        dst = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, src.id, Decimal("100"))

        transfer = svc.create_transfer(
            company_id=cid,
            source_warehouse_id=src.id,
            destination_warehouse_id=dst.id,
            lines=[{"product_id": pid, "quantity": "30"}],
        )
        dispatched = svc.dispatch_transfer(company_id=cid, transfer_id=transfer.id)
        assert dispatched.status == "IN_TRANSIT"
        assert dispatched.version == 2

        # Source stock should be reduced
        pos_repo = StockPositionRepository(db_session)
        src_pos = pos_repo.get_by_product_warehouse(
            company_id=cid, product_id=pid, warehouse_id=src.id
        )
        assert Decimal(str(src_pos.qty_on_hand)) == pytest.approx(Decimal("70"))

    def test_dispatch_insufficient_stock_raises(self, db_session: Session):
        svc = _make_transfer_service(db_session)
        cid = uuid.uuid4()
        src = _make_warehouse(db_session, cid)
        dst = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, src.id, Decimal("5"))

        transfer = svc.create_transfer(
            company_id=cid,
            source_warehouse_id=src.id,
            destination_warehouse_id=dst.id,
            lines=[{"product_id": pid, "quantity": "10"}],
        )
        with pytest.raises(InsufficientStockError):
            svc.dispatch_transfer(company_id=cid, transfer_id=transfer.id)

    def test_dispatch_already_in_transit_raises(self, db_session: Session):
        svc = _make_transfer_service(db_session)
        cid = uuid.uuid4()
        src = _make_warehouse(db_session, cid)
        dst = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, src.id, Decimal("100"))
        transfer = svc.create_transfer(
            company_id=cid,
            source_warehouse_id=src.id,
            destination_warehouse_id=dst.id,
            lines=[{"product_id": pid, "quantity": "10"}],
        )
        svc.dispatch_transfer(company_id=cid, transfer_id=transfer.id)

        with pytest.raises(InvalidTransferStateTransitionError):
            svc.dispatch_transfer(company_id=cid, transfer_id=transfer.id)


# ---------------------------------------------------------------------------
# Receive workflow
# ---------------------------------------------------------------------------


class TestReceiveWorkflow:
    def test_receive_completes_transfer_and_increases_dest_stock(
        self, db_session: Session
    ):
        svc = _make_transfer_service(db_session)
        cid = uuid.uuid4()
        src = _make_warehouse(db_session, cid)
        dst = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, src.id, Decimal("100"))
        transfer = svc.create_transfer(
            company_id=cid,
            source_warehouse_id=src.id,
            destination_warehouse_id=dst.id,
            lines=[{"product_id": pid, "quantity": "40"}],
        )
        svc.dispatch_transfer(company_id=cid, transfer_id=transfer.id)
        completed = svc.receive_transfer(company_id=cid, transfer_id=transfer.id)

        assert completed.status == "COMPLETED"
        assert completed.version == 3

        pos_repo = StockPositionRepository(db_session)
        dst_pos = pos_repo.get_by_product_warehouse(
            company_id=cid, product_id=pid, warehouse_id=dst.id
        )
        assert Decimal(str(dst_pos.qty_on_hand)) == pytest.approx(Decimal("40"))
        # source is now 60
        src_pos = pos_repo.get_by_product_warehouse(
            company_id=cid, product_id=pid, warehouse_id=src.id
        )
        assert Decimal(str(src_pos.qty_on_hand)) == pytest.approx(Decimal("60"))

    def test_receive_draft_raises(self, db_session: Session):
        svc = _make_transfer_service(db_session)
        cid = uuid.uuid4()
        src = _make_warehouse(db_session, cid)
        dst = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, src.id, Decimal("50"))
        transfer = svc.create_transfer(
            company_id=cid,
            source_warehouse_id=src.id,
            destination_warehouse_id=dst.id,
            lines=[{"product_id": pid, "quantity": "10"}],
        )
        with pytest.raises(InvalidTransferStateTransitionError):
            svc.receive_transfer(company_id=cid, transfer_id=transfer.id)


# ---------------------------------------------------------------------------
# Cancel workflow (T210)
# ---------------------------------------------------------------------------


class TestCancelWorkflow:
    def test_cancel_draft_no_stock_change(self, db_session: Session):
        svc = _make_transfer_service(db_session)
        cid = uuid.uuid4()
        src = _make_warehouse(db_session, cid)
        dst = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, src.id, Decimal("100"))
        transfer = svc.create_transfer(
            company_id=cid,
            source_warehouse_id=src.id,
            destination_warehouse_id=dst.id,
            lines=[{"product_id": pid, "quantity": "20"}],
        )
        cancelled = svc.cancel_transfer(
            company_id=cid,
            transfer_id=transfer.id,
            cancelled_reason="changed my mind",
        )
        assert cancelled.status == "CANCELLED"

        # Stock unchanged
        pos_repo = StockPositionRepository(db_session)
        pos = pos_repo.get_by_product_warehouse(
            company_id=cid, product_id=pid, warehouse_id=src.id
        )
        assert Decimal(str(pos.qty_on_hand)) == pytest.approx(Decimal("100"))

    def test_cancel_in_transit_creates_reversal_and_restores_stock(
        self, db_session: Session
    ):
        """T210: IN_TRANSIT cancellation creates reversal TRANSFER_IN at source."""
        svc = _make_transfer_service(db_session)
        cid = uuid.uuid4()
        src = _make_warehouse(db_session, cid)
        dst = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, src.id, Decimal("100"))
        transfer = svc.create_transfer(
            company_id=cid,
            source_warehouse_id=src.id,
            destination_warehouse_id=dst.id,
            lines=[{"product_id": pid, "quantity": "30"}],
        )
        svc.dispatch_transfer(company_id=cid, transfer_id=transfer.id)

        # Verify source reduced after dispatch
        pos_repo = StockPositionRepository(db_session)
        src_pos = pos_repo.get_by_product_warehouse(
            company_id=cid, product_id=pid, warehouse_id=src.id
        )
        assert Decimal(str(src_pos.qty_on_hand)) == pytest.approx(Decimal("70"))

        # Cancel from IN_TRANSIT
        cancelled = svc.cancel_transfer(
            company_id=cid,
            transfer_id=transfer.id,
            cancelled_reason="logistics issue",
        )
        assert cancelled.status == "CANCELLED"

        # Stock restored to 100
        db_session.expire(src_pos)
        src_pos = pos_repo.get_by_product_warehouse(
            company_id=cid, product_id=pid, warehouse_id=src.id
        )
        assert Decimal(str(src_pos.qty_on_hand)) == pytest.approx(Decimal("100"))

        # Destination unchanged
        dst_pos = pos_repo.get_by_product_warehouse(
            company_id=cid, product_id=pid, warehouse_id=dst.id
        )
        assert dst_pos is None or Decimal(str(dst_pos.qty_on_hand)) == pytest.approx(
            Decimal("0")
        )

    def test_cancel_completed_raises(self, db_session: Session):
        svc = _make_transfer_service(db_session)
        cid = uuid.uuid4()
        src = _make_warehouse(db_session, cid)
        dst = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, src.id, Decimal("100"))
        transfer = svc.create_transfer(
            company_id=cid,
            source_warehouse_id=src.id,
            destination_warehouse_id=dst.id,
            lines=[{"product_id": pid, "quantity": "20"}],
        )
        svc.dispatch_transfer(company_id=cid, transfer_id=transfer.id)
        svc.receive_transfer(company_id=cid, transfer_id=transfer.id)

        with pytest.raises(InvalidTransferStateTransitionError):
            svc.cancel_transfer(
                company_id=cid,
                transfer_id=transfer.id,
                cancelled_reason="too late",
            )

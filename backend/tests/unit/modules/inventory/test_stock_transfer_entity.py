"""Unit tests for TransferService business logic (T208).

Tests:
  - State machine transitions (valid and invalid)
  - source ≠ destination invariant
  - Lines required invariant
  - Cancellation reversal path (IN_TRANSIT → CANCELLED)
  - Reservation / release business rules
  - Insufficient stock guard on dispatch

Spec ref: specs/005-inventory-management/spec.md §16 / FR-IO-013
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from modules.inventory.exceptions import (
    InsufficientStockError,
    InvalidStockQuantityError,
    InvalidTransferError,
    InvalidTransferStateTransitionError,
    TransferNotFoundError,
    WarehouseNotFoundError,
)
from modules.inventory.services.transfer_service import TransferService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_line(**kwargs) -> MagicMock:
    defaults = {
        "id": uuid.uuid4(),
        "transfer_id": str(uuid.uuid4()),
        "product_id": str(uuid.uuid4()),
        "variant_id": None,
        "quantity": Decimal("10"),
        "unit_cost": None,
        "currency_code": None,
        "source_movement_id": None,
        "destination_movement_id": None,
        "reversal_movement_id": None,
    }
    all_attrs = {**defaults, **kwargs}
    mock = MagicMock()
    for k, v in all_attrs.items():
        setattr(mock, k, v)
    return mock


def _make_transfer(**kwargs) -> MagicMock:
    line = _make_line()
    defaults = {
        "id": uuid.uuid4(),
        "company_id": uuid.uuid4(),
        "source_warehouse_id": str(uuid.uuid4()),
        "destination_warehouse_id": str(uuid.uuid4()),
        "status": "DRAFT",
        "version": 1,
        "notes": None,
        "lines": [line],
    }
    all_attrs = {**defaults, **kwargs}
    mock = MagicMock()
    for k, v in all_attrs.items():
        setattr(mock, k, v)
    return mock


@dataclass
class _ServiceUnderTest:
    """Bundles the real ``TransferService`` with its own constructor
    mocks, so tests assert against the mocks directly (``m.wh_repo...``)
    rather than through ``svc._wh_repo...`` — the latter is statically
    typed as the real repository class regardless of what was actually
    passed at construction, so MagicMock-only members like
    ``.return_value``/``.assert_called_once()`` don't type-check on it."""

    service: TransferService
    db: MagicMock
    transfer_repo: MagicMock
    ledger: MagicMock
    pos_repo: MagicMock
    wh_repo: MagicMock


def _make_service() -> _ServiceUnderTest:
    db = MagicMock()
    transfer_repo = MagicMock()
    stock_ledger = MagicMock()
    pos_repo = MagicMock()
    wh_repo = MagicMock()

    svc = TransferService(
        db=db,
        transfer_repo=transfer_repo,
        stock_ledger=stock_ledger,
        position_repo=pos_repo,
        warehouse_repo=wh_repo,
    )
    return _ServiceUnderTest(
        service=svc,
        db=db,
        transfer_repo=transfer_repo,
        ledger=stock_ledger,
        pos_repo=pos_repo,
        wh_repo=wh_repo,
    )


# ---------------------------------------------------------------------------
# Create transfer invariants
# ---------------------------------------------------------------------------


class TestCreateTransferInvariants:
    def test_same_warehouse_raises(self):
        m = _make_service()
        wh = uuid.uuid4()
        with pytest.raises(InvalidTransferError):
            m.service.create_transfer(
                company_id=uuid.uuid4(),
                source_warehouse_id=wh,
                destination_warehouse_id=wh,
                lines=[{"product_id": uuid.uuid4(), "quantity": "10"}],
            )

    def test_empty_lines_raises(self):
        m = _make_service()
        m.wh_repo.get_by_id_or_none.return_value = MagicMock(
            is_deleted=False, status="ACTIVE"
        )
        with pytest.raises(ValueError, match="least one"):
            m.service.create_transfer(
                company_id=uuid.uuid4(),
                source_warehouse_id=uuid.uuid4(),
                destination_warehouse_id=uuid.uuid4(),
                lines=[],
            )

    def test_inactive_source_warehouse_raises(self):
        m = _make_service()
        m.wh_repo.get_by_id_or_none.side_effect = [
            MagicMock(is_deleted=False, status="INACTIVE"),
        ]
        with pytest.raises(WarehouseNotFoundError):
            m.service.create_transfer(
                company_id=uuid.uuid4(),
                source_warehouse_id=uuid.uuid4(),
                destination_warehouse_id=uuid.uuid4(),
                lines=[{"product_id": uuid.uuid4(), "quantity": "5"}],
            )

    def test_zero_quantity_line_raises(self):
        m = _make_service()
        m.wh_repo.get_by_id_or_none.return_value = MagicMock(
            is_deleted=False, status="ACTIVE"
        )
        with pytest.raises(InvalidStockQuantityError):
            m.service.create_transfer(
                company_id=uuid.uuid4(),
                source_warehouse_id=uuid.uuid4(),
                destination_warehouse_id=uuid.uuid4(),
                lines=[{"product_id": uuid.uuid4(), "quantity": "0"}],
            )

    def test_negative_quantity_line_raises(self):
        m = _make_service()
        m.wh_repo.get_by_id_or_none.return_value = MagicMock(
            is_deleted=False, status="ACTIVE"
        )
        with pytest.raises(InvalidStockQuantityError):
            m.service.create_transfer(
                company_id=uuid.uuid4(),
                source_warehouse_id=uuid.uuid4(),
                destination_warehouse_id=uuid.uuid4(),
                lines=[{"product_id": uuid.uuid4(), "quantity": "-5"}],
            )

    def test_create_returns_draft(self):
        m = _make_service()
        m.wh_repo.get_by_id_or_none.return_value = MagicMock(
            is_deleted=False, status="ACTIVE"
        )
        m.db.add = MagicMock()
        m.db.flush = MagicMock()

        result = m.service.create_transfer(
            company_id=uuid.uuid4(),
            source_warehouse_id=uuid.uuid4(),
            destination_warehouse_id=uuid.uuid4(),
            lines=[{"product_id": uuid.uuid4(), "quantity": "20"}],
        )
        assert result.status == "DRAFT"
        assert result.version == 1


# ---------------------------------------------------------------------------
# Dispatch transitions
# ---------------------------------------------------------------------------


class TestDispatchTransfer:
    def test_dispatch_non_draft_raises(self):
        m = _make_service()
        transfer = _make_transfer(status="IN_TRANSIT")
        m.transfer_repo.get_by_id_with_lines.return_value = transfer
        with pytest.raises(InvalidTransferStateTransitionError):
            m.service.dispatch_transfer(
                company_id=transfer.company_id,
                transfer_id=transfer.id,
            )

    def test_dispatch_not_found_raises(self):
        m = _make_service()
        m.transfer_repo.get_by_id_with_lines.return_value = None
        with pytest.raises(TransferNotFoundError):
            m.service.dispatch_transfer(
                company_id=uuid.uuid4(),
                transfer_id=uuid.uuid4(),
            )

    def test_dispatch_insufficient_stock_raises(self):
        m = _make_service()
        transfer = _make_transfer(status="DRAFT")
        m.transfer_repo.get_by_id_with_lines.return_value = transfer
        mock_pos = MagicMock()
        mock_pos.qty_on_hand = Decimal("5")
        mock_pos.qty_reserved = Decimal("0")
        mock_pos.qty_damaged = Decimal("0")
        m.pos_repo.get_by_product_warehouse.return_value = mock_pos
        with pytest.raises(InsufficientStockError):
            m.service.dispatch_transfer(
                company_id=transfer.company_id,
                transfer_id=transfer.id,
            )

    def test_dispatch_success_calls_ledger_and_transitions(self):
        m = _make_service()
        transfer = _make_transfer(status="DRAFT", version=1)
        m.transfer_repo.get_by_id_with_lines.return_value = transfer
        mock_pos = MagicMock()
        mock_pos.qty_on_hand = Decimal("100")
        mock_pos.qty_reserved = Decimal("0")
        mock_pos.qty_damaged = Decimal("0")
        m.pos_repo.get_by_product_warehouse.return_value = mock_pos
        mock_movement = MagicMock()
        mock_movement.id = uuid.uuid4()
        m.ledger.record_transfer_movement.return_value = (mock_movement, mock_pos)
        dispatched = _make_transfer(status="IN_TRANSIT", version=2)
        m.transfer_repo.update_status.return_value = dispatched

        result = m.service.dispatch_transfer(
            company_id=transfer.company_id,
            transfer_id=transfer.id,
        )
        assert result.status == "IN_TRANSIT"
        m.ledger.record_transfer_movement.assert_called_once()


# ---------------------------------------------------------------------------
# Receive transitions
# ---------------------------------------------------------------------------


class TestReceiveTransfer:
    def test_receive_non_in_transit_raises(self):
        m = _make_service()
        transfer = _make_transfer(status="DRAFT")
        m.transfer_repo.get_by_id_with_lines.return_value = transfer
        with pytest.raises(InvalidTransferStateTransitionError):
            m.service.receive_transfer(
                company_id=transfer.company_id,
                transfer_id=transfer.id,
            )

    def test_receive_completed_raises(self):
        m = _make_service()
        transfer = _make_transfer(status="COMPLETED")
        m.transfer_repo.get_by_id_with_lines.return_value = transfer
        with pytest.raises(InvalidTransferStateTransitionError):
            m.service.receive_transfer(
                company_id=transfer.company_id,
                transfer_id=transfer.id,
            )

    def test_receive_success(self):
        m = _make_service()
        transfer = _make_transfer(status="IN_TRANSIT", version=2)
        m.transfer_repo.get_by_id_with_lines.return_value = transfer
        mock_pos = MagicMock()
        mock_movement = MagicMock()
        mock_movement.id = uuid.uuid4()
        m.ledger.record_transfer_movement.return_value = (mock_movement, mock_pos)
        completed = _make_transfer(status="COMPLETED", version=3)
        m.transfer_repo.update_status.return_value = completed

        result = m.service.receive_transfer(
            company_id=transfer.company_id,
            transfer_id=transfer.id,
        )
        assert result.status == "COMPLETED"
        m.ledger.record_transfer_movement.assert_called_once()


# ---------------------------------------------------------------------------
# Cancel transitions
# ---------------------------------------------------------------------------


class TestCancelTransfer:
    def test_cancel_completed_raises(self):
        m = _make_service()
        transfer = _make_transfer(status="COMPLETED")
        m.transfer_repo.get_by_id_with_lines.return_value = transfer
        with pytest.raises(InvalidTransferStateTransitionError):
            m.service.cancel_transfer(
                company_id=transfer.company_id,
                transfer_id=transfer.id,
                cancelled_reason="mistake",
            )

    def test_cancel_draft_no_stock_change(self):
        m = _make_service()
        transfer = _make_transfer(status="DRAFT", version=1)
        m.transfer_repo.get_by_id_with_lines.return_value = transfer
        cancelled = _make_transfer(status="CANCELLED", version=2)
        m.transfer_repo.update_status.return_value = cancelled

        result = m.service.cancel_transfer(
            company_id=transfer.company_id,
            transfer_id=transfer.id,
            cancelled_reason="no longer needed",
        )
        assert result.status == "CANCELLED"
        m.ledger.record_transfer_movement.assert_not_called()

    def test_cancel_in_transit_creates_reversal(self):
        m = _make_service()
        transfer = _make_transfer(status="IN_TRANSIT", version=2)
        m.transfer_repo.get_by_id_with_lines.return_value = transfer
        mock_pos = MagicMock()
        mock_movement = MagicMock()
        mock_movement.id = uuid.uuid4()
        m.ledger.record_transfer_movement.return_value = (mock_movement, mock_pos)
        cancelled = _make_transfer(status="CANCELLED", version=3)
        m.transfer_repo.update_status.return_value = cancelled

        result = m.service.cancel_transfer(
            company_id=transfer.company_id,
            transfer_id=transfer.id,
            cancelled_reason="logistics issue",
        )
        assert result.status == "CANCELLED"
        # Must have called ledger to create reversal TRANSFER_IN
        m.ledger.record_transfer_movement.assert_called_once()
        call_kwargs = m.ledger.record_transfer_movement.call_args.kwargs
        assert call_kwargs["movement_type"] == "TRANSFER_IN"
        assert call_kwargs["reference_type"] == "TRANSFER_REVERSAL"


# ---------------------------------------------------------------------------
# Reservation
# ---------------------------------------------------------------------------


class TestReservation:
    def test_reserve_zero_raises(self):
        m = _make_service()
        with pytest.raises(InvalidStockQuantityError):
            m.service.reserve_stock(
                company_id=uuid.uuid4(),
                product_id=uuid.uuid4(),
                warehouse_id=uuid.uuid4(),
                quantity=Decimal("0"),
            )

    def test_reserve_negative_raises(self):
        m = _make_service()
        with pytest.raises(InvalidStockQuantityError):
            m.service.reserve_stock(
                company_id=uuid.uuid4(),
                product_id=uuid.uuid4(),
                warehouse_id=uuid.uuid4(),
                quantity=Decimal("-1"),
            )

    def test_reserve_exceeds_available_raises(self):
        m = _make_service()
        mock_pos = MagicMock()
        mock_pos.qty_on_hand = Decimal("10")
        mock_pos.qty_reserved = Decimal("8")
        mock_pos.qty_damaged = Decimal("0")
        m.pos_repo.get_or_create.return_value = (mock_pos, True)
        with pytest.raises(InsufficientStockError):
            m.service.reserve_stock(
                company_id=uuid.uuid4(),
                product_id=uuid.uuid4(),
                warehouse_id=uuid.uuid4(),
                quantity=Decimal("5"),
            )

    def test_reserve_within_available_succeeds(self):
        m = _make_service()
        mock_pos = MagicMock()
        mock_pos.qty_on_hand = Decimal("100")
        mock_pos.qty_reserved = Decimal("10")
        mock_pos.qty_damaged = Decimal("0")
        m.pos_repo.get_or_create.return_value = (mock_pos, False)
        m.db.flush = MagicMock()

        m.service.reserve_stock(
            company_id=uuid.uuid4(),
            product_id=uuid.uuid4(),
            warehouse_id=uuid.uuid4(),
            quantity=Decimal("20"),
        )
        assert Decimal(str(mock_pos.qty_reserved)) == Decimal("30")

    def test_release_zero_raises(self):
        m = _make_service()
        with pytest.raises(InvalidStockQuantityError):
            m.service.release_stock(
                company_id=uuid.uuid4(),
                product_id=uuid.uuid4(),
                warehouse_id=uuid.uuid4(),
                quantity=Decimal("0"),
            )

    def test_release_exceeds_reserved_raises(self):
        m = _make_service()
        mock_pos = MagicMock()
        mock_pos.qty_on_hand = Decimal("100")
        mock_pos.qty_reserved = Decimal("5")
        mock_pos.qty_damaged = Decimal("0")
        m.pos_repo.get_or_create.return_value = (mock_pos, False)
        with pytest.raises(InsufficientStockError):
            m.service.release_stock(
                company_id=uuid.uuid4(),
                product_id=uuid.uuid4(),
                warehouse_id=uuid.uuid4(),
                quantity=Decimal("10"),
            )

    def test_release_decrements_reserved(self):
        m = _make_service()
        mock_pos = MagicMock()
        mock_pos.qty_on_hand = Decimal("100")
        mock_pos.qty_reserved = Decimal("30")
        mock_pos.qty_damaged = Decimal("0")
        m.pos_repo.get_or_create.return_value = (mock_pos, False)
        m.db.flush = MagicMock()

        m.service.release_stock(
            company_id=uuid.uuid4(),
            product_id=uuid.uuid4(),
            warehouse_id=uuid.uuid4(),
            quantity=Decimal("10"),
        )
        assert Decimal(str(mock_pos.qty_reserved)) == Decimal("20")

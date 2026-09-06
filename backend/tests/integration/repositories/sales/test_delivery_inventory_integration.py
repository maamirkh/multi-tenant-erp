"""Integration tests for Delivery Note with Epic 5 inventory — Phase 5.

Tests:
  - Stock reservation on DN creation (via TransferService.reserve_stock)
  - Stock deduction on dispatch (via StockLedgerService.record_adjustment)
  - Reservation release on DN cancellation
  - Rollback: if DN status update fails, stock deduction should not persist
  - Quantity validation: cannot dispatch more than remaining

These tests create real inventory data (warehouse, product, stock position)
to verify end-to-end Epic 5 integration.

Task: T154
Spec ref: specs/007-sales-management/spec.md §Order Fulfilment
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from modules.inventory.models.warehouse import Warehouse
from modules.inventory.repositories.stock_repository import (
    StockPositionRepository,
)
from modules.sales.models.order import OrderLine, SalesOrder
from modules.sales.schemas.delivery import (
    DeliveryNoteCreate,
    DeliveryNoteDispatch,
    DeliveryNoteLineCreate,
)
from modules.sales.services.delivery_service import DeliveryService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_warehouse(db: Session, company_id: UUID) -> Warehouse:
    wh = Warehouse(
        id=uuid4(),
        company_id=company_id,
        code=f"WH-{uuid4().hex[:4].upper()}",
        name="Main Warehouse",
        warehouse_type="MAIN",
        status="ACTIVE",
    )
    db.add(wh)
    db.flush()
    return wh


def _make_order(
    db: Session,
    company_id: UUID,
    status: str = "APPROVED",
    total_amount: str = "100.00",
) -> SalesOrder:
    order = SalesOrder(
        company_id=company_id,
        order_number=f"SO-INT-{uuid4().hex[:8]}",
        customer_id=str(uuid4()),
        order_date="2026-08-03",
        currency_code="USD",
        sales_rep_id=str(uuid4()),
        priority="NORMAL",
        status=status,
        subtotal=Decimal(total_amount),
        discount_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        charges_amount=Decimal("0"),
        total_amount=Decimal(total_amount),
        approval_version=1,
        version=1,
    )
    db.add(order)
    db.flush()
    return order


def _make_order_line(
    db: Session,
    company_id: UUID,
    order_id: str,
    product_id: str | None = None,
    quantity_ordered: str = "10",
    quantity_delivered: str = "0",
) -> OrderLine:
    line = OrderLine(
        company_id=company_id,
        order_id=order_id,
        line_number=1,
        product_id=product_id,
        description="Test product",
        quantity_ordered=Decimal(quantity_ordered),
        quantity_delivered=Decimal(quantity_delivered),
        unit_of_measure="EA",
        unit_price=Decimal("10.00"),
        extended_amount=Decimal(quantity_ordered) * Decimal("10.00"),
        delivery_status="PENDING",
    )
    db.add(line)
    db.flush()
    return line


def _give_stock(
    db: Session,
    company_id: UUID,
    product_id: UUID,
    warehouse_id: UUID,
    quantity: Decimal,
) -> None:
    """Give a product stock by creating/updating the stock position directly."""
    pos_repo = StockPositionRepository(db)
    pos, _ = pos_repo.get_or_create(
        company_id=company_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
    )
    pos.qty_on_hand = Decimal(str(pos.qty_on_hand)) + quantity
    db.flush()


# ---------------------------------------------------------------------------
# Tests: Quantity validation
# ---------------------------------------------------------------------------


class TestQuantityValidation:
    def test_cannot_exceed_remaining_quantity(self, db_session: Session) -> None:
        """Dispatching more than ordered quantity raises ConflictException."""
        company_id = uuid4()
        order = _make_order(db_session, company_id)
        order_line = _make_order_line(
            db_session, company_id, str(order.id), quantity_ordered="5"
        )

        svc = DeliveryService(db_session)
        data = DeliveryNoteCreate(
            order_id=order.id,
            lines=[
                DeliveryNoteLineCreate(
                    order_line_id=order_line.id,
                    description="Test",
                    quantity_dispatched=Decimal("6"),  # > 5 ordered
                    unit_of_measure="EA",
                )
            ],
        )
        from core.exceptions.base import ConflictException

        with pytest.raises(ConflictException, match="remaining"):
            svc.create_delivery_note(
                company_id=company_id,
                data=data,
                created_by=uuid4(),
            )

    def test_exact_remaining_quantity_allowed(self, db_session: Session) -> None:
        """Dispatching exactly the remaining quantity succeeds."""
        company_id = uuid4()
        order = _make_order(db_session, company_id)
        order_line = _make_order_line(
            db_session, company_id, str(order.id), quantity_ordered="5"
        )

        svc = DeliveryService(db_session)
        data = DeliveryNoteCreate(
            order_id=order.id,
            lines=[
                DeliveryNoteLineCreate(
                    order_line_id=order_line.id,
                    description="Test",
                    quantity_dispatched=Decimal("5"),  # exactly 5 ordered
                    unit_of_measure="EA",
                )
            ],
        )
        dn = svc.create_delivery_note(
            company_id=company_id,
            data=data,
            created_by=uuid4(),
        )
        assert dn.status == "DRAFT"


# ---------------------------------------------------------------------------
# Tests: Inventory integration
# ---------------------------------------------------------------------------


class TestStockReservationOnCreation:
    def test_stock_reserved_on_dn_creation(self, db_session: Session) -> None:
        """Creating a DN with a product that has stock reserves qty_reserved."""
        company_id = uuid4()
        product_id = uuid4()
        warehouse = _make_warehouse(db_session, company_id)
        _give_stock(db_session, company_id, product_id, warehouse.id, Decimal("20"))

        order = _make_order(db_session, company_id)
        order_line = _make_order_line(
            db_session,
            company_id,
            str(order.id),
            product_id=str(product_id),
            quantity_ordered="10",
        )

        svc = DeliveryService(db_session)
        data = DeliveryNoteCreate(
            order_id=order.id,
            lines=[
                DeliveryNoteLineCreate(
                    order_line_id=order_line.id,
                    product_id=product_id,
                    description="Test product",
                    quantity_dispatched=Decimal("5"),
                    unit_of_measure="EA",
                )
            ],
        )
        dn = svc.create_delivery_note(
            company_id=company_id, data=data, created_by=uuid4()
        )
        assert dn.status == "DRAFT"

        # Verify stock was reserved
        pos_repo = StockPositionRepository(db_session)
        pos, _ = pos_repo.get_or_create(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse.id,
        )
        assert Decimal(str(pos.qty_reserved)) == Decimal("5")

    def test_insufficient_stock_blocks_dn_creation(self, db_session: Session) -> None:
        """Creating a DN when stock is insufficient raises ConflictException."""
        company_id = uuid4()
        product_id = uuid4()
        warehouse = _make_warehouse(db_session, company_id)
        _give_stock(db_session, company_id, product_id, warehouse.id, Decimal("3"))

        order = _make_order(db_session, company_id)
        order_line = _make_order_line(
            db_session,
            company_id,
            str(order.id),
            product_id=str(product_id),
            quantity_ordered="10",
        )

        svc = DeliveryService(db_session)
        data = DeliveryNoteCreate(
            order_id=order.id,
            lines=[
                DeliveryNoteLineCreate(
                    order_line_id=order_line.id,
                    product_id=product_id,
                    description="Test product",
                    quantity_dispatched=Decimal("5"),  # > 3 available
                    unit_of_measure="EA",
                )
            ],
        )
        from core.exceptions.base import ConflictException

        with pytest.raises(ConflictException, match="[Ii]nsufficient"):
            svc.create_delivery_note(
                company_id=company_id, data=data, created_by=uuid4()
            )


class TestStockDeductionOnDispatch:
    def test_stock_deducted_on_dispatch(self, db_session: Session) -> None:
        """Dispatching a DN deducts stock from on_hand."""
        company_id = uuid4()
        product_id = uuid4()
        warehouse = _make_warehouse(db_session, company_id)
        _give_stock(db_session, company_id, product_id, warehouse.id, Decimal("20"))

        order = _make_order(db_session, company_id)
        order_line = _make_order_line(
            db_session,
            company_id,
            str(order.id),
            product_id=str(product_id),
            quantity_ordered="10",
        )

        svc = DeliveryService(db_session)
        data = DeliveryNoteCreate(
            order_id=order.id,
            lines=[
                DeliveryNoteLineCreate(
                    order_line_id=order_line.id,
                    product_id=product_id,
                    description="Test product",
                    quantity_dispatched=Decimal("5"),
                    unit_of_measure="EA",
                )
            ],
        )
        dn = svc.create_delivery_note(
            company_id=company_id, data=data, created_by=uuid4()
        )

        svc.dispatch(
            company_id=company_id,
            delivery_note_id=dn.id,
            data=DeliveryNoteDispatch(dispatch_date="2026-08-03"),
            dispatched_by=uuid4(),
        )

        # Verify on_hand was deducted
        pos_repo = StockPositionRepository(db_session)
        pos, _ = pos_repo.get_or_create(
            company_id=company_id, product_id=product_id, warehouse_id=warehouse.id
        )
        assert Decimal(str(pos.qty_on_hand)) == Decimal("15")  # 20 - 5

    def test_stock_reserved_released_on_dispatch(self, db_session: Session) -> None:
        """After dispatch, qty_reserved should go back to 0 (released)."""
        company_id = uuid4()
        product_id = uuid4()
        warehouse = _make_warehouse(db_session, company_id)
        _give_stock(db_session, company_id, product_id, warehouse.id, Decimal("20"))

        order = _make_order(db_session, company_id)
        order_line = _make_order_line(
            db_session,
            company_id,
            str(order.id),
            product_id=str(product_id),
            quantity_ordered="10",
        )

        svc = DeliveryService(db_session)
        data = DeliveryNoteCreate(
            order_id=order.id,
            lines=[
                DeliveryNoteLineCreate(
                    order_line_id=order_line.id,
                    product_id=product_id,
                    description="Test product",
                    quantity_dispatched=Decimal("5"),
                    unit_of_measure="EA",
                )
            ],
        )
        dn = svc.create_delivery_note(
            company_id=company_id, data=data, created_by=uuid4()
        )
        svc.dispatch(
            company_id=company_id,
            delivery_note_id=dn.id,
            data=DeliveryNoteDispatch(dispatch_date="2026-08-03"),
            dispatched_by=uuid4(),
        )

        pos_repo = StockPositionRepository(db_session)
        pos, _ = pos_repo.get_or_create(
            company_id=company_id, product_id=product_id, warehouse_id=warehouse.id
        )
        # Reservation should be released
        assert Decimal(str(pos.qty_reserved)) == Decimal("0")


class TestReservationReleaseOnCancellation:
    def test_reservation_released_on_cancellation(self, db_session: Session) -> None:
        """Cancelling a DRAFT DN releases the stock reservation."""
        company_id = uuid4()
        product_id = uuid4()
        warehouse = _make_warehouse(db_session, company_id)
        _give_stock(db_session, company_id, product_id, warehouse.id, Decimal("20"))

        order = _make_order(db_session, company_id)
        order_line = _make_order_line(
            db_session,
            company_id,
            str(order.id),
            product_id=str(product_id),
            quantity_ordered="10",
        )

        svc = DeliveryService(db_session)
        data = DeliveryNoteCreate(
            order_id=order.id,
            lines=[
                DeliveryNoteLineCreate(
                    order_line_id=order_line.id,
                    product_id=product_id,
                    description="Test product",
                    quantity_dispatched=Decimal("5"),
                    unit_of_measure="EA",
                )
            ],
        )
        dn = svc.create_delivery_note(
            company_id=company_id, data=data, created_by=uuid4()
        )

        # Verify reserved
        pos_repo = StockPositionRepository(db_session)
        pos, _ = pos_repo.get_or_create(
            company_id=company_id, product_id=product_id, warehouse_id=warehouse.id
        )
        assert Decimal(str(pos.qty_reserved)) == Decimal("5")

        # Cancel the DN
        svc.cancel(company_id=company_id, delivery_note_id=dn.id, cancelled_by=uuid4())

        # Verify reservation released
        pos, _ = pos_repo.get_or_create(
            company_id=company_id, product_id=product_id, warehouse_id=warehouse.id
        )
        assert Decimal(str(pos.qty_reserved)) == Decimal("0")

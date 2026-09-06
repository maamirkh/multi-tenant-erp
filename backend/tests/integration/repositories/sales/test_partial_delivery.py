"""Integration tests for partial delivery workflow — Phase 5.

Tests:
  - Multiple DNs against one SO
  - Cumulative quantity tracking (cannot exceed ordered)
  - SO status auto-update: APPROVED → PARTIALLY_DELIVERED
  - SO status auto-update: PARTIALLY_DELIVERED → DELIVERED (all lines done)
  - Order line delivery_status updates correctly

Task: T155
Spec ref: specs/007-sales-management/spec.md §Order Fulfilment
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

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


def _make_order(db: Session, company_id: UUID, status: str = "APPROVED") -> SalesOrder:
    order = SalesOrder(
        company_id=company_id,
        order_number=f"SO-PART-{uuid4().hex[:8]}",
        customer_id=str(uuid4()),
        order_date="2026-08-03",
        currency_code="USD",
        sales_rep_id=str(uuid4()),
        priority="NORMAL",
        status=status,
        subtotal=Decimal("200.00"),
        discount_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        charges_amount=Decimal("0"),
        total_amount=Decimal("200.00"),
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
    line_number: int = 1,
    quantity_ordered: str = "10",
    product_id: str | None = None,
) -> OrderLine:
    line = OrderLine(
        company_id=company_id,
        order_id=order_id,
        line_number=line_number,
        product_id=product_id,
        description=f"Product line {line_number}",
        quantity_ordered=Decimal(quantity_ordered),
        quantity_delivered=Decimal("0"),
        unit_of_measure="EA",
        unit_price=Decimal("10.00"),
        extended_amount=Decimal(quantity_ordered) * Decimal("10.00"),
        delivery_status="PENDING",
    )
    db.add(line)
    db.flush()
    return line


def _create_and_dispatch_dn(
    svc: DeliveryService,
    db: Session,
    company_id: UUID,
    order: SalesOrder,
    line: OrderLine,
    qty: Decimal,
    user_id: UUID | None = None,
) -> None:
    """Helper to create and dispatch a DN for the given order line."""
    if user_id is None:
        user_id = uuid4()
    data = DeliveryNoteCreate(
        order_id=order.id,
        lines=[
            DeliveryNoteLineCreate(
                order_line_id=line.id,
                description=line.description,
                quantity_dispatched=qty,
                unit_of_measure=line.unit_of_measure,
            )
        ],
    )
    dn = svc.create_delivery_note(company_id=company_id, data=data, created_by=user_id)
    svc.dispatch(
        company_id=company_id,
        delivery_note_id=dn.id,
        data=DeliveryNoteDispatch(dispatch_date="2026-08-03"),
        dispatched_by=user_id,
    )


# ---------------------------------------------------------------------------
# Tests: Single SO, single line, partial delivery
# ---------------------------------------------------------------------------


class TestPartialDelivery:
    def test_partial_dispatch_sets_partially_delivered(
        self, db_session: Session
    ) -> None:
        """Dispatching 5 of 10 → SO status = PARTIALLY_DELIVERED."""
        company_id = uuid4()
        order = _make_order(db_session, company_id)
        line = _make_order_line(
            db_session, company_id, str(order.id), quantity_ordered="10"
        )

        svc = DeliveryService(db_session)
        _create_and_dispatch_dn(svc, db_session, company_id, order, line, Decimal("5"))

        db_session.refresh(order)
        assert order.status == "PARTIALLY_DELIVERED"

    def test_partial_dispatch_updates_order_line_status(
        self, db_session: Session
    ) -> None:
        """Dispatching partial quantity → OrderLine.delivery_status = PARTIALLY_DELIVERED."""
        company_id = uuid4()
        order = _make_order(db_session, company_id)
        line = _make_order_line(
            db_session, company_id, str(order.id), quantity_ordered="10"
        )

        svc = DeliveryService(db_session)
        _create_and_dispatch_dn(svc, db_session, company_id, order, line, Decimal("5"))

        db_session.refresh(line)
        assert line.delivery_status == "PARTIALLY_DELIVERED"
        assert Decimal(str(line.quantity_delivered)) == Decimal("5")

    def test_full_dispatch_sets_delivered(self, db_session: Session) -> None:
        """Dispatching 10 of 10 → SO status = DELIVERED."""
        company_id = uuid4()
        order = _make_order(db_session, company_id)
        line = _make_order_line(
            db_session, company_id, str(order.id), quantity_ordered="10"
        )

        svc = DeliveryService(db_session)
        _create_and_dispatch_dn(svc, db_session, company_id, order, line, Decimal("10"))

        db_session.refresh(order)
        assert order.status == "DELIVERED"

    def test_full_dispatch_updates_order_line_status(self, db_session: Session) -> None:
        """Dispatching full quantity → OrderLine.delivery_status = DELIVERED."""
        company_id = uuid4()
        order = _make_order(db_session, company_id)
        line = _make_order_line(
            db_session, company_id, str(order.id), quantity_ordered="10"
        )

        svc = DeliveryService(db_session)
        _create_and_dispatch_dn(svc, db_session, company_id, order, line, Decimal("10"))

        db_session.refresh(line)
        assert line.delivery_status == "DELIVERED"
        assert Decimal(str(line.quantity_delivered)) == Decimal("10")


# ---------------------------------------------------------------------------
# Tests: Multiple DNs against same SO line
# ---------------------------------------------------------------------------


class TestMultiDnPartialDelivery:
    def test_two_partial_dns_then_full_delivery(self, db_session: Session) -> None:
        """Two DNs (5 + 5) against a 10-qty line → PARTIALLY_DELIVERED then DELIVERED."""
        company_id = uuid4()
        order = _make_order(db_session, company_id)
        line = _make_order_line(
            db_session, company_id, str(order.id), quantity_ordered="10"
        )
        svc = DeliveryService(db_session)

        # First DN: 5 units
        _create_and_dispatch_dn(svc, db_session, company_id, order, line, Decimal("5"))
        db_session.refresh(order)
        assert order.status == "PARTIALLY_DELIVERED"
        db_session.refresh(line)
        assert Decimal(str(line.quantity_delivered)) == Decimal("5")

        # Second DN: remaining 5 units
        _create_and_dispatch_dn(svc, db_session, company_id, order, line, Decimal("5"))
        db_session.refresh(order)
        assert order.status == "DELIVERED"
        db_session.refresh(line)
        assert Decimal(str(line.quantity_delivered)) == Decimal("10")

    def test_cumulative_quantity_exceeds_ordered_raises(
        self, db_session: Session
    ) -> None:
        """Creating a second DN that would exceed the ordered quantity raises ConflictException."""
        company_id = uuid4()
        order = _make_order(db_session, company_id)
        line = _make_order_line(
            db_session, company_id, str(order.id), quantity_ordered="10"
        )
        svc = DeliveryService(db_session)

        # First DN: 8 units
        _create_and_dispatch_dn(svc, db_session, company_id, order, line, Decimal("8"))

        # Second DN: 5 units (8+5=13 > 10)
        data = DeliveryNoteCreate(
            order_id=order.id,
            lines=[
                DeliveryNoteLineCreate(
                    order_line_id=line.id,
                    description="Product",
                    quantity_dispatched=Decimal("5"),
                    unit_of_measure="EA",
                )
            ],
        )
        from core.exceptions.base import ConflictException

        with pytest.raises(ConflictException, match="remaining"):
            svc.create_delivery_note(
                company_id=company_id, data=data, created_by=uuid4()
            )

    def test_cancelled_dn_does_not_count_toward_cumulative(
        self, db_session: Session
    ) -> None:
        """Cancelled DN quantities do not block subsequent DN creation."""
        company_id = uuid4()
        order = _make_order(db_session, company_id)
        line = _make_order_line(
            db_session, company_id, str(order.id), quantity_ordered="10"
        )
        svc = DeliveryService(db_session)

        # Create a DRAFT DN for 8 units and cancel it
        data_8 = DeliveryNoteCreate(
            order_id=order.id,
            lines=[
                DeliveryNoteLineCreate(
                    order_line_id=line.id,
                    description="Product",
                    quantity_dispatched=Decimal("8"),
                    unit_of_measure="EA",
                )
            ],
        )
        dn_cancelled = svc.create_delivery_note(
            company_id=company_id, data=data_8, created_by=uuid4()
        )
        svc.cancel(
            company_id=company_id,
            delivery_note_id=dn_cancelled.id,
            cancelled_by=uuid4(),
        )

        # Now create a new DN for 10 units — should succeed since cancelled DN doesn't count
        data_10 = DeliveryNoteCreate(
            order_id=order.id,
            lines=[
                DeliveryNoteLineCreate(
                    order_line_id=line.id,
                    description="Product",
                    quantity_dispatched=Decimal("10"),
                    unit_of_measure="EA",
                )
            ],
        )
        dn_new = svc.create_delivery_note(
            company_id=company_id, data=data_10, created_by=uuid4()
        )
        assert dn_new.status == "DRAFT"


# ---------------------------------------------------------------------------
# Tests: Multi-line SO
# ---------------------------------------------------------------------------


class TestMultiLineOrder:
    def test_partial_delivery_with_multiline_so(self, db_session: Session) -> None:
        """SO with 2 lines: dispatch line1 fully → PARTIALLY_DELIVERED (line2 still pending)."""
        company_id = uuid4()
        order = _make_order(db_session, company_id)
        line1 = _make_order_line(
            db_session, company_id, str(order.id), line_number=1, quantity_ordered="5"
        )
        line2 = _make_order_line(
            db_session, company_id, str(order.id), line_number=2, quantity_ordered="8"
        )
        svc = DeliveryService(db_session)

        # Deliver line1 fully
        data = DeliveryNoteCreate(
            order_id=order.id,
            lines=[
                DeliveryNoteLineCreate(
                    order_line_id=line1.id,
                    description="Line 1",
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

        db_session.refresh(order)
        assert order.status == "PARTIALLY_DELIVERED"

    def test_full_delivery_with_multiline_so(self, db_session: Session) -> None:
        """SO with 2 lines: dispatch both fully → DELIVERED."""
        company_id = uuid4()
        order = _make_order(db_session, company_id)
        line1 = _make_order_line(
            db_session, company_id, str(order.id), line_number=1, quantity_ordered="5"
        )
        line2 = _make_order_line(
            db_session, company_id, str(order.id), line_number=2, quantity_ordered="8"
        )
        svc = DeliveryService(db_session)

        # Deliver both lines in a single DN
        data = DeliveryNoteCreate(
            order_id=order.id,
            lines=[
                DeliveryNoteLineCreate(
                    order_line_id=line1.id,
                    description="Line 1",
                    quantity_dispatched=Decimal("5"),
                    unit_of_measure="EA",
                ),
                DeliveryNoteLineCreate(
                    order_line_id=line2.id,
                    description="Line 2",
                    quantity_dispatched=Decimal("8"),
                    unit_of_measure="EA",
                ),
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

        db_session.refresh(order)
        assert order.status == "DELIVERED"


# ---------------------------------------------------------------------------
# Tests: Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    def test_dn_not_visible_across_companies(self, db_session: Session) -> None:
        """Company B cannot see Company A's delivery notes."""
        company_a = uuid4()
        company_b = uuid4()

        order = _make_order(db_session, company_a)
        line = _make_order_line(db_session, company_a, str(order.id))
        svc = DeliveryService(db_session)

        data = DeliveryNoteCreate(
            order_id=order.id,
            lines=[
                DeliveryNoteLineCreate(
                    order_line_id=line.id,
                    description="Product",
                    quantity_dispatched=Decimal("5"),
                    unit_of_measure="EA",
                )
            ],
        )
        dn = svc.create_delivery_note(
            company_id=company_a, data=data, created_by=uuid4()
        )

        from core.exceptions.base import NotFoundException

        with pytest.raises(NotFoundException):
            svc.get_delivery_note(company_b, dn.id)

        items, total = svc.list_delivery_notes(company_b)
        assert total == 0

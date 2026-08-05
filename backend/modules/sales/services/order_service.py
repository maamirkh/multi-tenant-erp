"""Sales Order application service — Phase 4.

Services:
  OrderService     — lifecycle management, state machine, approval routing,
                     cancellation, quotation conversion
  OrderLineService — line CRUD within a Sales Order

State machine (enforced at service layer):
  DRAFT → PENDING_APPROVAL | CANCELLED
  PENDING_APPROVAL → APPROVED | REJECTED
  APPROVED → PARTIALLY_DELIVERED | DELIVERED | CANCELLED
  REJECTED → DRAFT (revision — approval_version increments)
  PARTIALLY_DELIVERED → DELIVERED
  DELIVERED → INVOICED
  INVOICED → CLOSED
  CLOSED → (terminal)
  CANCELLED → (terminal)

Spec ref: specs/007-sales-management/spec.md §Sales Orders
Task: T110, T111 (via ApprovalService), T114, T115
"""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException, NotFoundException
from modules.sales.events import get_event_bus
from modules.sales.events.order_events import (
    OrderApproved,
    OrderCancelled,
    OrderClosed,
    OrderCreated,
    OrderDelivered,
    OrderInvoiced,
    OrderPartiallyDelivered,
    OrderRejected,
    OrderSubmitted,
)
from modules.sales.models.order import OrderLine, SalesOrder
from modules.sales.repositories.order import OrderLineRepository, SalesOrderRepository
from modules.sales.repositories.pricing import (
    CustomerSpecificPriceRepository,
    PriceEntryRepository,
    PriceListRepository,
)
from modules.sales.schemas.order import (
    OrderCancelRequest,
    OrderLineCreate,
    OrderLineUpdate,
    SalesOrderCreate,
    SalesOrderUpdate,
)
from modules.sales.services.approval_service import ApprovalService
from modules.sales.services.pricing_service import PricingService
from modules.sales.services.sequence_service import SalesSequenceService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[str, list[str]] = {
    "DRAFT": ["PENDING_APPROVAL", "CANCELLED"],
    "PENDING_APPROVAL": ["APPROVED", "REJECTED"],
    "APPROVED": ["PARTIALLY_DELIVERED", "DELIVERED", "CANCELLED"],
    "REJECTED": ["DRAFT"],  # revision path
    "PARTIALLY_DELIVERED": ["DELIVERED"],
    "DELIVERED": ["INVOICED"],
    "INVOICED": ["CLOSED"],
    "CLOSED": [],
    "CANCELLED": [],
}

_TERMINAL_STATUSES = {"CLOSED", "CANCELLED"}
_IMMUTABLE_STATUSES = {
    "PENDING_APPROVAL",
    "APPROVED",
    "PARTIALLY_DELIVERED",
    "DELIVERED",
    "INVOICED",
    "CLOSED",
    "CANCELLED",
}


def _assert_transition(current: str, target: str) -> None:
    """Raise ConflictException if the status transition is invalid."""
    allowed = _VALID_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise ConflictException(
            f"Invalid order status transition: {current!r} → {target!r}. "
            f"Allowed: {allowed}"
        )


# ---------------------------------------------------------------------------
# OrderLineService
# ---------------------------------------------------------------------------


class OrderLineService:
    """Service for managing lines within a Sales Order.

    Lines can only be added/updated/deleted on DRAFT orders.
    """

    def __init__(
        self,
        db: Session,
        pricing_service: PricingService | None = None,
    ) -> None:
        self._db = db
        self._line_repo = OrderLineRepository(db)
        self._order_repo = SalesOrderRepository(db)
        self._pricing = pricing_service or PricingService(
            db=db,
            price_list_repo=PriceListRepository(db),
            entry_repo=PriceEntryRepository(db),
            specific_repo=CustomerSpecificPriceRepository(db),
        )

    def add_line(
        self,
        company_id: UUID,
        order_id: UUID,
        data: OrderLineCreate,
    ) -> OrderLine:
        """Add a line to a DRAFT order."""
        order = self._order_repo.get_by_id_or_none(order_id, company_id)
        if order is None:
            raise NotFoundException(f"Sales order {order_id} not found.")
        if order.status != "DRAFT":
            raise ConflictException(
                f"Lines can only be added to DRAFT orders. Current status: {order.status}"
            )

        line_number = self._line_repo.next_line_number(company_id, order_id)
        unit_price = data.unit_price

        # Compute line amounts
        discount_amount: Decimal | None = None
        if data.discount_percentage is not None and data.discount_percentage > 0:
            discount_amount = (
                (data.quantity_ordered * unit_price * data.discount_percentage) / 100
            ).quantize(Decimal("0.01"))

        effective_price = unit_price
        if discount_amount:
            effective_price = unit_price - (discount_amount / data.quantity_ordered)

        tax_rate = data.tax_rate or Decimal("0")
        extended = (data.quantity_ordered * effective_price).quantize(Decimal("0.01"))
        tax_amount = (extended * tax_rate).quantize(Decimal("0.01"))

        line = OrderLine(
            company_id=company_id,
            order_id=str(order_id),
            line_number=line_number,
            product_id=str(data.product_id) if data.product_id else None,
            description=data.description,
            quantity_ordered=data.quantity_ordered,
            quantity_delivered=Decimal("0"),
            unit_of_measure=data.unit_of_measure,
            unit_price=unit_price,
            cost_price=data.cost_price,
            discount_percentage=data.discount_percentage,
            discount_amount=discount_amount,
            tax_category=data.tax_category,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            extended_amount=extended,
            delivery_status="PENDING",
            price_source=data.price_source,
            notes=data.notes,
        )
        self._db.add(line)
        self._db.flush()
        self._recalculate_totals(order, company_id)
        return line

    def update_line(
        self,
        company_id: UUID,
        order_id: UUID,
        line_id: UUID,
        data: OrderLineUpdate,
    ) -> OrderLine:
        """Update a line on a DRAFT order."""
        order = self._order_repo.get_by_id_or_none(order_id, company_id)
        if order is None:
            raise NotFoundException(f"Sales order {order_id} not found.")
        if order.status != "DRAFT":
            raise ConflictException(
                f"Lines can only be updated on DRAFT orders. Current status: {order.status}"
            )

        line = self._line_repo.get_by_id_or_none(line_id, company_id)
        if line is None or line.order_id != str(order_id):
            raise NotFoundException(f"Order line {line_id} not found.")

        if data.description is not None:
            line.description = data.description
        if data.quantity_ordered is not None:
            line.quantity_ordered = data.quantity_ordered
        if data.unit_of_measure is not None:
            line.unit_of_measure = data.unit_of_measure
        if data.unit_price is not None:
            line.unit_price = data.unit_price
        if data.cost_price is not None:
            line.cost_price = data.cost_price
        if data.discount_percentage is not None:
            line.discount_percentage = data.discount_percentage
        if data.tax_category is not None:
            line.tax_category = data.tax_category
        if data.tax_rate is not None:
            line.tax_rate = data.tax_rate
        if data.notes is not None:
            line.notes = data.notes

        # Recompute amounts
        qty = line.quantity_ordered
        price = line.unit_price
        disc_pct = line.discount_percentage or Decimal("0")
        disc_amt = (
            ((qty * price * disc_pct) / 100).quantize(Decimal("0.01"))
            if disc_pct
            else None
        )
        effective = price - (disc_amt / qty if disc_amt else Decimal("0"))
        extended = (qty * effective).quantize(Decimal("0.01"))
        tax_r = line.tax_rate or Decimal("0")
        tax_amt = (extended * tax_r).quantize(Decimal("0.01"))

        line.discount_amount = disc_amt
        line.extended_amount = extended
        line.tax_amount = tax_amt

        self._db.flush()
        self._recalculate_totals(order, company_id)
        return line

    def delete_line(self, company_id: UUID, order_id: UUID, line_id: UUID) -> None:
        """Delete a line from a DRAFT order."""
        order = self._order_repo.get_by_id_or_none(order_id, company_id)
        if order is None:
            raise NotFoundException(f"Sales order {order_id} not found.")
        if order.status != "DRAFT":
            raise ConflictException(
                f"Lines can only be deleted from DRAFT orders. Current status: {order.status}"
            )

        line = self._line_repo.get_by_id_or_none(line_id, company_id)
        if line is None or line.order_id != str(order_id):
            raise NotFoundException(f"Order line {line_id} not found.")

        line.is_deleted = True
        self._db.flush()
        self._recalculate_totals(order, company_id)

    def _recalculate_totals(self, order: SalesOrder, company_id: UUID) -> None:
        """Recompute order subtotal and total from active lines."""
        lines = self._line_repo.list_for_order(order.company_id, order.id)
        subtotal = sum(
            (Decimal(str(ln.extended_amount)) for ln in lines),
            Decimal("0"),
        )
        tax_total = sum(
            (Decimal(str(ln.tax_amount)) for ln in lines),
            Decimal("0"),
        )

        disc_type = order.discount_type
        disc_value = (
            Decimal(str(order.discount_value)) if order.discount_value else Decimal("0")
        )
        disc_amount = Decimal("0")
        if disc_type == "PERCENTAGE" and disc_value > 0:
            disc_amount = (subtotal * disc_value / 100).quantize(Decimal("0.01"))
        elif disc_type == "AMOUNT":
            disc_amount = min(disc_value, subtotal)

        charges = (
            Decimal(str(order.charges_amount)) if order.charges_amount else Decimal("0")
        )
        total = subtotal - disc_amount + tax_total + charges

        order.subtotal = subtotal
        order.discount_amount = disc_amount
        order.tax_amount = tax_total
        order.total_amount = total


# ---------------------------------------------------------------------------
# OrderService
# ---------------------------------------------------------------------------


class OrderService:
    """Service for Sales Order lifecycle management.

    Handles:
      - Order creation (direct and from quotation conversion)
      - DRAFT editing gating (immutable after PENDING_APPROVAL)
      - Submission for approval (with credit check + auto-approval)
      - Approval/rejection processing
      - Cancellation with mandatory reason
      - Delivery and invoice status updates (triggered by Phase 5/6)
      - Order closure

    Spec ref: specs/007-sales-management/spec.md §Sales Orders
    Task: T110, T114, T115
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._order_repo = SalesOrderRepository(db)
        self._line_repo = OrderLineRepository(db)
        self._approval_service = ApprovalService(db)
        self._line_service = OrderLineService(db)
        self._seq_service = SalesSequenceService(db)

    def _get_order_or_raise(self, company_id: UUID, order_id: UUID) -> SalesOrder:
        order = self._order_repo.get_by_id_or_none(order_id, company_id)
        if order is None:
            raise NotFoundException(f"Sales order {order_id} not found.")
        return order

    def _check_require_quotation(self, company_id: UUID) -> bool:
        """Return True if direct order creation is blocked by feature flag."""
        from modules.sales.repositories.feature_flag_repository import (
            SalesFeatureFlagRepository,  # noqa: PLC0415
        )
        from modules.sales.services.feature_flag_service import (
            SalesFeatureFlagService,  # noqa: PLC0415
        )

        flag_service = SalesFeatureFlagService(
            self._db, SalesFeatureFlagRepository(self._db)
        )
        return flag_service.is_enabled(
            company_id=company_id,
            flag_key="sales.quotation_required",
        )

    def create_order(
        self,
        company_id: UUID,
        data: SalesOrderCreate,
        created_by: UUID,
    ) -> SalesOrder:
        """Create a new Sales Order in DRAFT status.

        If data.quotation_id is set, the order is created from quotation
        conversion (Phase 3 integration). Otherwise it's a direct order.

        Raises:
            ConflictException: If sales.quotation_required flag is on and
                               no quotation_id is provided.
        """
        if data.quotation_id is None and self._check_require_quotation(company_id):
            raise ConflictException(
                "Direct order creation is disabled. "
                "A quotation must be accepted and converted first "
                "(feature flag: sales.quotation_required)."
            )

        order_number = self._seq_service.generate_next_number(company_id, "SO")

        order = SalesOrder(
            company_id=company_id,
            order_number=order_number,
            customer_id=str(data.customer_id),
            quotation_id=str(data.quotation_id) if data.quotation_id else None,
            order_date=data.order_date,
            required_delivery_date=data.required_delivery_date,
            currency_code=data.currency_code,
            payment_term_id=str(data.payment_term_id) if data.payment_term_id else None,
            shipping_address_id=(
                str(data.shipping_address_id) if data.shipping_address_id else None
            ),
            billing_address_id=(
                str(data.billing_address_id) if data.billing_address_id else None
            ),
            sales_rep_id=str(data.sales_rep_id),
            priority=data.priority,
            status="DRAFT",
            subtotal=Decimal("0"),
            discount_amount=Decimal("0"),
            tax_amount=Decimal("0"),
            charges_amount=Decimal("0"),
            total_amount=Decimal("0"),
            internal_notes=data.internal_notes,
            customer_notes=data.customer_notes,
            approval_version=1,
            version=1,
            created_by=created_by,
        )
        self._db.add(order)
        self._db.flush()

        # Add lines
        line_service = OrderLineService(self._db)
        for line_data in data.lines:
            line_service.add_line(company_id, order.id, line_data)

        self._db.flush()

        get_event_bus().publish(
            OrderCreated(
                company_id=company_id,
                aggregate_id=order.id,
                order_id=order.id,
                order_number=order.order_number,
                customer_id=str(data.customer_id),
                total_amount=str(order.total_amount),
                currency_code=order.currency_code,
                sales_rep_id=str(data.sales_rep_id),
                from_quotation=data.quotation_id is not None,
                quotation_id=str(data.quotation_id) if data.quotation_id else None,
            )
        )

        logger.info(
            "OrderService: created order %s for company %s",
            order.order_number,
            company_id,
        )
        return order

    def update_order(
        self,
        company_id: UUID,
        order_id: UUID,
        data: SalesOrderUpdate,
    ) -> SalesOrder:
        """Update a DRAFT Sales Order header fields."""
        order = self._get_order_or_raise(company_id, order_id)
        if order.status not in ("DRAFT", "REJECTED"):
            raise ConflictException(
                f"Only DRAFT or REJECTED orders can be updated. Current status: {order.status}"
            )

        if data.required_delivery_date is not None:
            order.required_delivery_date = data.required_delivery_date
        if data.currency_code is not None:
            order.currency_code = data.currency_code
        if data.payment_term_id is not None:
            order.payment_term_id = str(data.payment_term_id)
        if data.shipping_address_id is not None:
            order.shipping_address_id = str(data.shipping_address_id)
        if data.billing_address_id is not None:
            order.billing_address_id = str(data.billing_address_id)
        if data.priority is not None:
            order.priority = data.priority
        if data.internal_notes is not None:
            order.internal_notes = data.internal_notes
        if data.customer_notes is not None:
            order.customer_notes = data.customer_notes

        self._db.flush()
        return order

    def submit_for_approval(
        self,
        company_id: UUID,
        order_id: UUID,
        submitted_by: UUID,
    ) -> tuple[SalesOrder, bool]:
        """Submit a DRAFT order for approval.

        Performs credit check and applies approval routing (auto or human).

        Returns:
            (order, auto_approved): Whether the order was auto-approved.

        Raises:
            ConflictException: If credit check fails or transition invalid.
        """
        order = self._get_order_or_raise(company_id, order_id)
        _assert_transition(order.status, "PENDING_APPROVAL")

        order.status = "PENDING_APPROVAL"
        self._db.flush()

        # Evaluate — may auto-approve immediately
        auto_approved, message = self._approval_service.evaluate_for_order(
            company_id=company_id,
            order_id=order.id,
            submitted_by=submitted_by,
        )

        if auto_approved:
            order.status = "APPROVED"
        else:
            get_event_bus().publish(
                OrderSubmitted(
                    company_id=company_id,
                    aggregate_id=order.id,
                    order_id=order.id,
                    order_number=order.order_number,
                    customer_id=order.customer_id,
                    total_amount=str(order.total_amount),
                    submitted_by=str(submitted_by),
                    approval_version=order.approval_version,
                )
            )

        self._db.flush()
        logger.info(
            "OrderService: order %s submitted (auto_approved=%s)",
            order.order_number,
            auto_approved,
        )
        return order, auto_approved

    def approve_order(
        self,
        company_id: UUID,
        order_id: UUID,
        approver_id: UUID,
        comments: str | None = None,
        requestor_id: UUID | None = None,
    ) -> SalesOrder:
        """Record an approval decision for a PENDING_APPROVAL order.

        If all approval levels are satisfied, transitions order to APPROVED.

        Raises:
            ConflictException: Self-approval, already decided, or invalid transition.
        """
        order = self._get_order_or_raise(company_id, order_id)
        if order.status != "PENDING_APPROVAL":
            raise ConflictException(
                f"Order must be in PENDING_APPROVAL to approve. "
                f"Current status: {order.status}"
            )

        all_approved, _ = self._approval_service.process_approval_decision(
            company_id=company_id,
            document_type="SALES_ORDER",
            document_id=order.id,
            approver_id=approver_id,
            decision="APPROVED",
            comments=comments,
            requestor_id=requestor_id,
        )

        if all_approved:
            order.status = "APPROVED"
            self._db.flush()
            get_event_bus().publish(
                OrderApproved(
                    company_id=company_id,
                    aggregate_id=order.id,
                    order_id=order.id,
                    order_number=order.order_number,
                    customer_id=order.customer_id,
                    total_amount=str(order.total_amount),
                    approved_by=str(approver_id),
                    auto_approved=False,
                )
            )
            logger.info("OrderService: order %s APPROVED", order.order_number)

        return order

    def reject_order(
        self,
        company_id: UUID,
        order_id: UUID,
        approver_id: UUID,
        rejection_reason: str,
        comments: str | None = None,
        requestor_id: UUID | None = None,
    ) -> SalesOrder:
        """Record a rejection decision; returns order to DRAFT for revision.

        Increments approval_version for the next submission cycle.

        Raises:
            ConflictException: Self-approval prevention, or invalid transition.
        """
        order = self._get_order_or_raise(company_id, order_id)
        if order.status != "PENDING_APPROVAL":
            raise ConflictException(
                f"Order must be in PENDING_APPROVAL to reject. "
                f"Current status: {order.status}"
            )

        _, any_rejected = self._approval_service.process_approval_decision(
            company_id=company_id,
            document_type="SALES_ORDER",
            document_id=order.id,
            approver_id=approver_id,
            decision="REJECTED",
            comments=comments or rejection_reason,
            requestor_id=requestor_id,
        )

        # Invalidate remaining pending records for current version
        self._approval_service.invalidate_pending_approvals(
            company_id=company_id,
            document_type="SALES_ORDER",
            document_id=order.id,
            approval_version=order.approval_version,
        )

        # Return to DRAFT for revision; increment approval_version
        order.status = "DRAFT"
        order.approval_version = order.approval_version + 1
        self._db.flush()

        get_event_bus().publish(
            OrderRejected(
                company_id=company_id,
                aggregate_id=order.id,
                order_id=order.id,
                order_number=order.order_number,
                customer_id=order.customer_id,
                rejected_by=str(approver_id),
                rejection_reason=rejection_reason,
            )
        )
        logger.info(
            "OrderService: order %s REJECTED by %s", order.order_number, approver_id
        )
        return order

    def cancel_order(
        self,
        company_id: UUID,
        order_id: UUID,
        data: OrderCancelRequest,
    ) -> SalesOrder:
        """Cancel an order with mandatory reason.

        Cancellation is allowed from: DRAFT, PENDING_APPROVAL, APPROVED.
        Terminal states (CLOSED, CANCELLED) cannot be cancelled.

        Raises:
            ConflictException: If transition invalid or reason missing.
        """
        order = self._get_order_or_raise(company_id, order_id)
        _assert_transition(order.status, "CANCELLED")

        if not data.cancellation_reason or not data.cancellation_reason.strip():
            raise ConflictException("Cancellation reason is required.")

        previous_status = order.status
        order.status = "CANCELLED"
        order.cancellation_reason = data.cancellation_reason
        self._db.flush()

        get_event_bus().publish(
            OrderCancelled(
                company_id=company_id,
                aggregate_id=order.id,
                order_id=order.id,
                order_number=order.order_number,
                customer_id=order.customer_id,
                previous_status=previous_status,
                cancellation_reason=data.cancellation_reason,
                cancelled_by=str(data.cancelled_by),
            )
        )
        logger.info(
            "OrderService: order %s CANCELLED (was %s)",
            order.order_number,
            previous_status,
        )
        return order

    def mark_partially_delivered(
        self,
        company_id: UUID,
        order_id: UUID,
        delivery_note_id: str,
    ) -> SalesOrder:
        """Transition APPROVED order to PARTIALLY_DELIVERED. Called by Phase 5."""
        order = self._get_order_or_raise(company_id, order_id)
        if order.status not in ("APPROVED", "PARTIALLY_DELIVERED"):
            raise ConflictException(
                f"Order must be APPROVED or PARTIALLY_DELIVERED for partial delivery. "
                f"Current: {order.status}"
            )
        if order.status == "APPROVED":
            order.status = "PARTIALLY_DELIVERED"
            self._db.flush()
            get_event_bus().publish(
                OrderPartiallyDelivered(
                    company_id=company_id,
                    aggregate_id=order.id,
                    order_id=order.id,
                    order_number=order.order_number,
                    customer_id=order.customer_id,
                    delivery_note_id=delivery_note_id,
                )
            )
        return order

    def mark_delivered(self, company_id: UUID, order_id: UUID) -> SalesOrder:
        """Transition to DELIVERED. Called by Phase 5 when all lines delivered."""
        order = self._get_order_or_raise(company_id, order_id)
        _assert_transition(order.status, "DELIVERED")
        order.status = "DELIVERED"
        self._db.flush()
        get_event_bus().publish(
            OrderDelivered(
                company_id=company_id,
                aggregate_id=order.id,
                order_id=order.id,
                order_number=order.order_number,
                customer_id=order.customer_id,
            )
        )
        return order

    def mark_invoiced(
        self, company_id: UUID, order_id: UUID, invoice_id: str
    ) -> SalesOrder:
        """Transition to INVOICED. Called by Phase 6."""
        order = self._get_order_or_raise(company_id, order_id)
        _assert_transition(order.status, "INVOICED")
        order.status = "INVOICED"
        self._db.flush()
        get_event_bus().publish(
            OrderInvoiced(
                company_id=company_id,
                aggregate_id=order.id,
                order_id=order.id,
                order_number=order.order_number,
                customer_id=order.customer_id,
                invoice_id=invoice_id,
            )
        )
        return order

    def close_order(
        self, company_id: UUID, order_id: UUID, closed_by: UUID
    ) -> SalesOrder:
        """Transition INVOICED order to CLOSED (terminal)."""
        order = self._get_order_or_raise(company_id, order_id)
        _assert_transition(order.status, "CLOSED")
        order.status = "CLOSED"
        self._db.flush()
        get_event_bus().publish(
            OrderClosed(
                company_id=company_id,
                aggregate_id=order.id,
                order_id=order.id,
                order_number=order.order_number,
                customer_id=order.customer_id,
            )
        )
        logger.info("OrderService: order %s CLOSED", order.order_number)
        return order

    def get_order_with_lines(
        self, company_id: UUID, order_id: UUID
    ) -> tuple[SalesOrder, list[OrderLine]]:
        """Fetch an order and its lines."""
        order = self._get_order_or_raise(company_id, order_id)
        lines = self._line_repo.list_for_order(order.company_id, order.id)
        return order, lines

    def list_orders(
        self,
        company_id: UUID,
        status: str | None = None,
        customer_id: UUID | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[SalesOrder]:
        """List orders with optional filters."""
        return self._order_repo.list_for_company(
            company_id, status, customer_id, search, skip, limit
        )

    def count_orders(
        self,
        company_id: UUID,
        status: str | None = None,
        customer_id: UUID | None = None,
    ) -> int:
        """Count orders with optional filters."""
        return self._order_repo.count_for_company(company_id, status, customer_id)

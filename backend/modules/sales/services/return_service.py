"""Sales Return application service — Phase 7.

Services:
  ReturnService — full return lifecycle:
    create (DRAFT), submit, approve, reject, receive (with inventory restock),
    complete (with resolution: credit note / replacement / refund-readiness), cancel.

State machine (SalesReturn.status):
  DRAFT → PENDING_APPROVAL | CANCELLED
  PENDING_APPROVAL → APPROVED | REJECTED | CANCELLED
  APPROVED → RECEIVED
  RECEIVED → COMPLETED
  COMPLETED → (terminal)
  REJECTED  → (terminal)
  CANCELLED → (terminal)

Resolution types (T190):
  CREDIT_NOTE       — sets credit_note_amount on the return
  REPLACEMENT       — creates a zero-value replacement SalesOrder (stub)
  REFUND_READINESS  — publishes ReturnRefundReady event for external processing

Inventory restock (T189):
  On RECEIVED transition, StockLedgerService.record_adjustment(ADJUSTMENT_IN)
  is called for each line where quantity_accepted > 0.  Rejected quantities
  are NOT restocked.  Best-effort: failures are logged but do not abort the
  transaction.

Gap-free numbering (T186):
  Uses SalesSequenceService with document_type="SR".

Spec ref: specs/007-sales-management/spec.md §19 Sales Returns
Task: T186–T190
"""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException, NotFoundException
from core.utils.datetime import utcnow
from modules.sales.events import get_event_bus
from modules.sales.events.return_events import (
    ReturnApproved,
    ReturnCompleted,
    ReturnCreated,
    ReturnReceived,
    ReturnRefundReady,
    ReturnRejected,
    ReturnSubmitted,
)
from modules.sales.models.sales_return import ReturnLine, SalesReturn
from modules.sales.repositories.sales_return import (
    ReturnLineRepository,
    SalesReturnRepository,
)
from modules.sales.schemas.sales_return import (
    ReturnApproveRequest,
    ReturnCompleteRequest,
    ReturnReceiveRequest,
    ReturnRejectRequest,
    SalesReturnCreate,
)
from modules.sales.services.sequence_service import SalesSequenceService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[str, list[str]] = {
    "DRAFT": ["PENDING_APPROVAL", "CANCELLED"],
    "PENDING_APPROVAL": ["APPROVED", "REJECTED", "CANCELLED"],
    "APPROVED": ["RECEIVED"],
    "RECEIVED": ["COMPLETED"],
    "COMPLETED": [],
    "REJECTED": [],
    "CANCELLED": [],
}

_TERMINAL_STATUSES = {"COMPLETED", "REJECTED", "CANCELLED"}


def _assert_return_transition(current: str, target: str) -> None:
    """Raise ConflictException if the return status transition is invalid."""
    allowed = _VALID_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise ConflictException(
            f"Invalid return status transition: {current!r} → {target!r}. "
            f"Allowed: {allowed}"
        )


# ---------------------------------------------------------------------------
# ReturnService
# ---------------------------------------------------------------------------


class ReturnService:
    """Orchestrates the full Sales Return (RMA) lifecycle.

    All public methods flush to the session but do NOT commit — the caller
    (or FastAPI dependency) owns the transaction boundary.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._return_repo = SalesReturnRepository(db)
        self._line_repo = ReturnLineRepository(db)
        self._seq_service = SalesSequenceService(db=db)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_return_or_raise(self, company_id: UUID, return_id: UUID) -> SalesReturn:
        ret = self._return_repo.get_by_id_or_none(return_id, company_id)
        if ret is None:
            raise NotFoundException(f"Sales return {return_id} not found.")
        return ret

    def _restock_inventory(
        self,
        company_id: UUID,
        return_id: UUID,
        lines: list[ReturnLine],
    ) -> None:
        """Best-effort inventory restock for accepted return lines (T189).

        For each line with quantity_accepted > 0 and a product_id, records
        an ADJUSTMENT_IN movement in the inventory module.  Failures are
        logged but do not abort the transaction.
        """
        for line in lines:
            if not line.product_id:
                continue
            qty_accepted = Decimal(str(line.quantity_accepted))
            if qty_accepted <= 0:
                continue

            try:
                from modules.inventory.repositories.snapshot_repository import (  # noqa: PLC0415
                    SnapshotRepository,
                )
                from modules.inventory.repositories.stock_movement_repository import (  # noqa: PLC0415
                    StockMovementRepository,
                )
                from modules.inventory.repositories.stock_position_repository import (  # noqa: PLC0415
                    StockPositionRepository,
                )
                from modules.inventory.repositories.warehouse_repository import (  # noqa: PLC0415
                    WarehouseRepository,
                )
                from modules.inventory.services.stock_service import (
                    StockLedgerService,  # noqa: PLC0415
                )

                wh_repo = WarehouseRepository(self._db)
                # Pick the first active warehouse for this company
                warehouses = wh_repo.list_for_company(company_id)
                if not warehouses:
                    logger.warning(
                        "No warehouse found for company %s; skipping restock of product %s",
                        company_id,
                        line.product_id,
                    )
                    continue

                warehouse_id = warehouses[0].id

                ledger = StockLedgerService(
                    db=self._db,
                    position_repo=StockPositionRepository(self._db),
                    movement_repo=StockMovementRepository(self._db),
                    snapshot_repo=SnapshotRepository(self._db),
                    warehouse_repo=wh_repo,
                )
                ledger.record_adjustment(
                    company_id=company_id,
                    product_id=UUID(line.product_id),
                    warehouse_id=warehouse_id,
                    movement_type="ADJUSTMENT_IN",
                    quantity=qty_accepted,
                    reference_type="SALES_RETURN",
                    reference_id=return_id,
                )
                logger.info(
                    "Restocked %s units of product %s for return %s",
                    qty_accepted,
                    line.product_id,
                    return_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Inventory restock skipped for product %s on return %s: %s",
                    line.product_id,
                    return_id,
                    exc,
                )

    def _create_replacement_order(
        self,
        company_id: UUID,
        sales_return: SalesReturn,
        completed_by: UUID,
    ) -> str | None:
        """Stub: create a zero-value replacement SO for REPLACEMENT resolution (T190).

        Returns the new order ID as a string, or None if creation fails.
        Full implementation deferred to a future phase when the replacement
        workflow is fully specified.
        """
        try:
            from modules.sales.models.order import SalesOrder  # noqa: PLC0415

            new_order = SalesOrder(
                company_id=company_id,
                order_number=f"REPL-{sales_return.return_number}",
                customer_id=sales_return.customer_id,
                order_date=utcnow().date().isoformat(),
                status="DRAFT",
                subtotal=Decimal("0"),
                discount_amount=Decimal("0"),
                tax_amount=Decimal("0"),
                total_amount=Decimal("0"),
                internal_notes=(
                    f"Replacement order for return {sales_return.return_number}"
                ),
                created_by=completed_by,
                version=1,
            )
            self._db.add(new_order)
            self._db.flush()
            return str(new_order.id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Could not create replacement order for return %s: %s",
                sales_return.return_number,
                exc,
            )
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_return(
        self,
        company_id: UUID,
        data: SalesReturnCreate,
        created_by: UUID,
    ) -> SalesReturn:
        """Create a new SalesReturn in DRAFT status.

        Validates references (order_id, invoice_id if provided).
        Generates a gap-free return number using SalesSequenceService.

        Returns the newly created SalesReturn (DRAFT).
        Raises NotFoundException if referenced order/invoice does not exist.
        """
        # ---- Gap-free return number -----------------------------------------
        return_number = self._seq_service.generate_next_number(
            company_id=company_id,
            document_type="SR",
        )

        # ---- Validate order reference (optional) ----------------------------
        if data.order_id:
            from modules.sales.models.order import SalesOrder  # noqa: PLC0415

            order = (
                self._db.query(SalesOrder)
                .filter(
                    SalesOrder.id == str(data.order_id),
                    SalesOrder.company_id == company_id,
                    SalesOrder.is_deleted.is_(False),
                )
                .first()
            )
            if order is None:
                raise NotFoundException(f"Sales order {data.order_id} not found.")

        # ---- Validate invoice reference (optional) --------------------------
        if data.invoice_id:
            from modules.sales.models.invoice import SalesInvoice  # noqa: PLC0415

            invoice = (
                self._db.query(SalesInvoice)
                .filter(
                    SalesInvoice.id == str(data.invoice_id),
                    SalesInvoice.company_id == company_id,
                    SalesInvoice.is_deleted.is_(False),
                )
                .first()
            )
            if invoice is None:
                raise NotFoundException(f"Invoice {data.invoice_id} not found.")

        # ---- Create return header -------------------------------------------
        sales_return = SalesReturn(
            company_id=company_id,
            return_number=return_number,
            customer_id=str(data.customer_id),
            order_id=str(data.order_id) if data.order_id else None,
            invoice_id=str(data.invoice_id) if data.invoice_id else None,
            return_date=data.return_date,
            reason_code_id=str(data.reason_code_id),
            reason_description=data.reason_description,
            resolution_type=data.resolution_type,
            status="DRAFT",
            approval_version=1,
            internal_notes=data.internal_notes,
            credit_note_amount=None,
            version=1,
            created_by=created_by,
        )
        self._db.add(sales_return)
        self._db.flush()  # get sales_return.id

        return_id_str = str(sales_return.id)

        # ---- Create return lines --------------------------------------------
        for line_data in data.lines:
            extended = (line_data.quantity_returned * line_data.unit_price).quantize(
                Decimal("0.01")
            )
            line = ReturnLine(
                company_id=company_id,
                return_id=return_id_str,
                product_id=str(line_data.product_id) if line_data.product_id else None,
                description=line_data.description,
                quantity_returned=line_data.quantity_returned,
                quantity_accepted=Decimal("0"),
                quantity_rejected=Decimal("0"),
                unit_price=line_data.unit_price,
                extended_amount=extended,
                condition=line_data.condition,
                reason_code_id=(
                    str(line_data.reason_code_id) if line_data.reason_code_id else None
                ),
                created_by=created_by,
            )
            self._db.add(line)

        self._db.flush()

        # ---- Publish event --------------------------------------------------
        try:
            get_event_bus().publish(
                ReturnCreated(
                    aggregate_id=sales_return.id,
                    company_id=company_id,
                    return_id=sales_return.id,
                    return_number=return_number,
                    customer_id=str(data.customer_id),
                    resolution_type=data.resolution_type,
                )
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to publish ReturnCreated event")

        logger.info(
            "Sales return created: %s (company=%s status=DRAFT)",
            return_number,
            company_id,
        )
        return sales_return

    def submit_return(
        self,
        company_id: UUID,
        return_id: UUID,
        submitted_by: UUID,
    ) -> SalesReturn:
        """Transition DRAFT → PENDING_APPROVAL.

        Increments approval_version to invalidate any stale approval records.
        Returns the updated SalesReturn.
        """
        sales_return = self._get_return_or_raise(company_id, return_id)
        _assert_return_transition(sales_return.status, "PENDING_APPROVAL")

        sales_return.status = "PENDING_APPROVAL"
        sales_return.approval_version += 1
        sales_return.updated_at = utcnow()
        self._db.flush()

        try:
            get_event_bus().publish(
                ReturnSubmitted(
                    aggregate_id=sales_return.id,
                    company_id=company_id,
                    return_id=sales_return.id,
                    return_number=sales_return.return_number,
                    customer_id=sales_return.customer_id,
                    submitted_by=str(submitted_by),
                )
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to publish ReturnSubmitted event")

        logger.info(
            "Return submitted: %s (company=%s)", sales_return.return_number, company_id
        )
        return sales_return

    def approve_return(
        self,
        company_id: UUID,
        return_id: UUID,
        data: ReturnApproveRequest,
        approved_by: UUID,
    ) -> SalesReturn:
        """Transition PENDING_APPROVAL → APPROVED.

        Returns the updated SalesReturn.
        """
        sales_return = self._get_return_or_raise(company_id, return_id)
        _assert_return_transition(sales_return.status, "APPROVED")

        sales_return.status = "APPROVED"
        sales_return.updated_at = utcnow()
        self._db.flush()

        try:
            get_event_bus().publish(
                ReturnApproved(
                    aggregate_id=sales_return.id,
                    company_id=company_id,
                    return_id=sales_return.id,
                    return_number=sales_return.return_number,
                    customer_id=sales_return.customer_id,
                    approved_by=str(approved_by),
                    auto_approved=data.auto_approved,
                )
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to publish ReturnApproved event")

        logger.info(
            "Return approved: %s (company=%s)", sales_return.return_number, company_id
        )
        return sales_return

    def reject_return(
        self,
        company_id: UUID,
        return_id: UUID,
        data: ReturnRejectRequest,
        rejected_by: UUID,
    ) -> SalesReturn:
        """Transition PENDING_APPROVAL → REJECTED (terminal).

        Returns the updated SalesReturn.
        """
        sales_return = self._get_return_or_raise(company_id, return_id)
        _assert_return_transition(sales_return.status, "REJECTED")

        sales_return.status = "REJECTED"
        sales_return.updated_at = utcnow()
        if data.rejection_reason:
            sales_return.internal_notes = (
                (sales_return.internal_notes or "")
                + f"\nRejected: {data.rejection_reason}"
            ).strip()
        self._db.flush()

        try:
            get_event_bus().publish(
                ReturnRejected(
                    aggregate_id=sales_return.id,
                    company_id=company_id,
                    return_id=sales_return.id,
                    return_number=sales_return.return_number,
                    customer_id=sales_return.customer_id,
                    rejected_by=str(rejected_by),
                    rejection_reason=data.rejection_reason,
                )
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to publish ReturnRejected event")

        logger.info(
            "Return rejected: %s (company=%s)", sales_return.return_number, company_id
        )
        return sales_return

    def receive_return(
        self,
        company_id: UUID,
        return_id: UUID,
        data: ReturnReceiveRequest,
        received_by: UUID,
    ) -> SalesReturn:
        """Transition APPROVED → RECEIVED.

        Records accepted/rejected quantities per line.
        Triggers inventory restock for accepted items (T189).
        Returns the updated SalesReturn.
        """
        sales_return = self._get_return_or_raise(company_id, return_id)
        _assert_return_transition(sales_return.status, "RECEIVED")

        # ---- Update line quantities -----------------------------------------
        lines = self._line_repo.list_for_return(company_id, return_id)
        line_map = {str(line.id): line for line in lines}

        for receipt_item in data.accepted_lines:
            line = line_map.get(str(receipt_item.line_id))
            if line is None:
                raise NotFoundException(
                    f"Return line {receipt_item.line_id} not found on return {return_id}."
                )
            total = receipt_item.quantity_accepted + receipt_item.quantity_rejected
            if total > line.quantity_returned:
                raise ConflictException(
                    f"Accepted + rejected ({total}) exceeds quantity_returned "
                    f"({line.quantity_returned}) for line {receipt_item.line_id}."
                )
            line.quantity_accepted = receipt_item.quantity_accepted
            line.quantity_rejected = receipt_item.quantity_rejected
            line.updated_at = utcnow()

        # ---- Transition header ----------------------------------------------
        sales_return.status = "RECEIVED"
        sales_return.received_by = str(received_by)
        sales_return.received_at = utcnow().isoformat()
        sales_return.updated_at = utcnow()
        self._db.flush()

        # ---- Inventory restock (T189) ---------------------------------------
        self._restock_inventory(company_id, sales_return.id, lines)

        total_accepted_lines = sum(
            1 for ln in lines if Decimal(str(ln.quantity_accepted)) > 0
        )

        try:
            get_event_bus().publish(
                ReturnReceived(
                    aggregate_id=sales_return.id,
                    company_id=company_id,
                    return_id=sales_return.id,
                    return_number=sales_return.return_number,
                    customer_id=sales_return.customer_id,
                    received_by=str(received_by),
                    total_accepted_lines=total_accepted_lines,
                )
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to publish ReturnReceived event")

        logger.info(
            "Return received: %s (company=%s)", sales_return.return_number, company_id
        )
        return sales_return

    def complete_return(
        self,
        company_id: UUID,
        return_id: UUID,
        data: ReturnCompleteRequest,
        completed_by: UUID,
    ) -> SalesReturn:
        """Transition RECEIVED → COMPLETED and apply resolution (T190).

        Resolution logic:
          CREDIT_NOTE       — sets credit_note_amount on the return.
          REPLACEMENT       — creates a replacement SalesOrder (stub).
          REFUND_READINESS  — publishes ReturnRefundReady event.

        Returns the updated SalesReturn.
        """
        sales_return = self._get_return_or_raise(company_id, return_id)
        _assert_return_transition(sales_return.status, "COMPLETED")

        resolution = sales_return.resolution_type

        # ---- Apply resolution -----------------------------------------------
        if resolution == "CREDIT_NOTE":
            if data.credit_note_amount is None or data.credit_note_amount <= 0:
                raise ConflictException(
                    "credit_note_amount must be provided and positive for CREDIT_NOTE resolution."
                )
            sales_return.credit_note_amount = data.credit_note_amount

        elif resolution == "REPLACEMENT":
            replacement_id = self._create_replacement_order(
                company_id, sales_return, completed_by
            )
            if replacement_id:
                sales_return.replacement_order_id = replacement_id

        # REFUND_READINESS is handled via event below

        # ---- Transition header ----------------------------------------------
        sales_return.status = "COMPLETED"
        sales_return.updated_at = utcnow()
        if data.notes:
            sales_return.internal_notes = (
                (sales_return.internal_notes or "")
                + f"\nCompletion notes: {data.notes}"
            ).strip()
        self._db.flush()

        try:
            get_event_bus().publish(
                ReturnCompleted(
                    aggregate_id=sales_return.id,
                    company_id=company_id,
                    return_id=sales_return.id,
                    return_number=sales_return.return_number,
                    customer_id=sales_return.customer_id,
                    resolution_type=resolution,
                    completed_by=str(completed_by),
                )
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to publish ReturnCompleted event")

        # ---- Extra event for REFUND_READINESS (T190) -----------------------
        if resolution == "REFUND_READINESS":
            try:
                get_event_bus().publish(
                    ReturnRefundReady(
                        aggregate_id=sales_return.id,
                        company_id=company_id,
                        return_id=sales_return.id,
                        return_number=sales_return.return_number,
                        customer_id=sales_return.customer_id,
                        credit_note_amount=str(data.credit_note_amount or "0"),
                    )
                )
            except Exception:  # noqa: BLE001
                logger.exception("Failed to publish ReturnRefundReady event")

        logger.info(
            "Return completed: %s (company=%s resolution=%s)",
            sales_return.return_number,
            company_id,
            resolution,
        )
        return sales_return

    def cancel_return(
        self,
        company_id: UUID,
        return_id: UUID,
        cancelled_by: UUID,
    ) -> SalesReturn:
        """Cancel a return (DRAFT or PENDING_APPROVAL → CANCELLED).

        Only DRAFT and PENDING_APPROVAL returns can be cancelled.
        Returns the updated SalesReturn.
        """
        sales_return = self._get_return_or_raise(company_id, return_id)
        _assert_return_transition(sales_return.status, "CANCELLED")

        sales_return.status = "CANCELLED"
        sales_return.updated_at = utcnow()
        self._db.flush()

        logger.info(
            "Return cancelled: %s (company=%s cancelled_by=%s)",
            sales_return.return_number,
            company_id,
            cancelled_by,
        )
        return sales_return

    def get_return(self, company_id: UUID, return_id: UUID) -> SalesReturn:
        """Return a SalesReturn by ID, enforcing tenant isolation."""
        return self._get_return_or_raise(company_id, return_id)

    def list_returns(
        self,
        company_id: UUID,
        *,
        customer_id: str | None = None,
        status: str | None = None,
        order_id: str | None = None,
        resolution_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SalesReturn], int]:
        """List returns for a company with optional filters."""
        return self._return_repo.list_for_company(
            company_id,
            customer_id=customer_id,
            status=status,
            order_id=order_id,
            resolution_type=resolution_type,
            limit=limit,
            offset=offset,
        )

    def get_return_lines(
        self,
        company_id: UUID,
        return_id: UUID,
    ) -> list[ReturnLine]:
        """Return all lines for a sales return."""
        self._get_return_or_raise(company_id, return_id)
        return self._line_repo.list_for_return(company_id, return_id)

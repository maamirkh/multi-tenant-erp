"""Vendor Return (RMA) application service — Phase 7.

Provides the complete RMA lifecycle:
  create_rma      — initialise a DRAFT RMA against a CONFIRMED GR
  update_rma      — update RMA header (DRAFT only)
  replace_lines   — replace RMA lines (DRAFT only)
  submit_rma      — DRAFT → SUBMITTED
  approve_rma     — SUBMITTED → APPROVED
  dispatch_rma    — APPROVED → DISPATCHED (atomic: stock deduction via Epic 5)
  complete_rma    — DISPATCHED → COMPLETED (credit_note_pending = True)
  cancel_rma      — SUBMITTED/APPROVED → CANCELLED
  link_replacement_po — attach replacement PO (state-neutral)
  get_rma         — retrieve single RMA with lines
  list_rmas       — paginated RMA list

State Machine (T173):
  DRAFT → SUBMITTED → APPROVED → DISPATCHED → COMPLETED
  SUBMITTED/APPROVED → CANCELLED

Business Rules (T172-T176):
  - RMA only against a CONFIRMED GoodsReceipt
  - return_quantity per line ≤ (gr_line.quantity_received − gr_line.quantity_rejected)
  - Dispatch is atomic: RMA status + Epic 5 PURCHASE_RETURN_OUTBOUND — rollback if stock fails
  - COMPLETED sets credit_note_pending = True
  - DRAFT/SUBMITTED/APPROVED RMAs can be edited; DISPATCHED/COMPLETED/CANCELLED are immutable

Spec ref: specs/006-purchase-management/spec.md §18 Vendor Returns
Tasks: T172, T173, T174, T175, T176
"""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException, NotFoundException
from core.utils.datetime import utcnow
from modules.purchase.events import get_event_bus
from modules.purchase.events.rma_events import (
    GoodsReturnApproved,
    GoodsReturnCompleted,
    GoodsReturned,
    GoodsReturnInitiated,
)
from modules.purchase.models.vendor_return import ReturnLine, VendorReturn
from modules.purchase.repositories.goods_receipt import (
    GoodsReceiptRepository,
    GRLineRepository,
)
from modules.purchase.repositories.vendor_return import (
    ReturnLineRepository,
    VendorReturnRepository,
)
from modules.purchase.schemas.vendor_return import (
    ReturnLineCreate,
    ReturnLineRead,
    VendorReturnCreate,
    VendorReturnListRead,
    VendorReturnRead,
    VendorReturnUpdate,
)
from modules.purchase.services.sequence_service import PurchaseSequenceService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


class RMAImmutableError(Exception):
    """Raised when an edit is attempted on an immutable RMA."""

    def __init__(self, rma_id: UUID, status: str) -> None:
        super().__init__(
            f"VendorReturn {rma_id} is in status {status!r} and cannot be edited."
        )


class RMAInvalidGRStatusError(Exception):
    """Raised when trying to create an RMA against a non-CONFIRMED GR."""

    def __init__(self, gr_id: str, gr_status: str) -> None:
        super().__init__(
            f"GoodsReceipt {gr_id} is in status {gr_status!r}. "
            "RMA can only be created against CONFIRMED goods receipts."
        )


class RMAInvalidTransitionError(Exception):
    """Raised when a status transition is not allowed by the state machine."""

    def __init__(self, rma_id: UUID, from_status: str, to_status: str) -> None:
        super().__init__(
            f"VendorReturn {rma_id} cannot transition from {from_status!r} to {to_status!r}."
        )


class RMAReturnQuantityError(Exception):
    """Raised when return quantity exceeds accepted GR quantity."""

    def __init__(self, gr_line_id: str, return_qty: Decimal, max_qty: Decimal) -> None:
        super().__init__(
            f"GRLine {gr_line_id}: return quantity {return_qty} exceeds "
            f"accepted quantity {max_qty} (received − rejected)."
        )


# ---------------------------------------------------------------------------
# Valid transitions (T173)
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"SUBMITTED", "CANCELLED"},
    "SUBMITTED": {"APPROVED", "CANCELLED"},
    "APPROVED": {"DISPATCHED", "CANCELLED"},
    "DISPATCHED": {"COMPLETED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}

# Statuses where the RMA header / lines can still be edited
_MUTABLE_STATUSES = {"DRAFT"}


# ---------------------------------------------------------------------------
# RMAService
# ---------------------------------------------------------------------------


class RMAService:
    """Application service for Vendor Return (RMA) lifecycle."""

    def __init__(
        self,
        db: Session,
        rma_repo: VendorReturnRepository,
        line_repo: ReturnLineRepository,
        gr_repo: GoodsReceiptRepository,
        gr_line_repo: GRLineRepository,
        sequence_service: PurchaseSequenceService,
    ) -> None:
        self.db = db
        self.rma_repo = rma_repo
        self.line_repo = line_repo
        self.gr_repo = gr_repo
        self.gr_line_repo = gr_line_repo
        self.sequence_service = sequence_service

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _assert_mutable(self, rma: VendorReturn) -> None:
        """Raise RMAImmutableError if the RMA cannot be edited."""
        if rma.status not in _MUTABLE_STATUSES:
            raise RMAImmutableError(rma.id, rma.status)

    def _assert_transition(self, rma: VendorReturn, to_status: str) -> None:
        """Raise RMAInvalidTransitionError if the transition is not allowed."""
        allowed = _VALID_TRANSITIONS.get(rma.status, set())
        if to_status not in allowed:
            raise RMAInvalidTransitionError(rma.id, rma.status, to_status)

    def _get_rma_or_404(self, rma_id: UUID, company_id: UUID) -> VendorReturn:
        rma = self.rma_repo.get_by_id_or_none(rma_id, company_id)
        if rma is None:
            raise NotFoundException(f"VendorReturn {rma_id} not found.")
        return rma

    # ------------------------------------------------------------------
    # Create (T172 + T173)
    # ------------------------------------------------------------------

    def create_rma(
        self,
        payload: VendorReturnCreate,
        company_id: UUID,
        user_id: UUID,
    ) -> VendorReturnRead:
        """Create a DRAFT RMA against a CONFIRMED GR."""

        # Validate GR exists and is CONFIRMED
        gr = self.gr_repo.get_by_id_or_none(payload.gr_id, company_id)
        if gr is None:
            raise NotFoundException(f"GoodsReceipt {payload.gr_id} not found.")
        if gr.status != "CONFIRMED":
            raise RMAInvalidGRStatusError(str(payload.gr_id), gr.status)

        # Generate RMA number
        rma_number = self.sequence_service.generate_next_number(company_id, "RMA")

        rma = VendorReturn(
            id=uuid4(),
            company_id=company_id,
            rma_number=rma_number,
            status="DRAFT",
            gr_id=str(payload.gr_id),
            supplier_id=gr.supplier_id,
            initiated_by=str(user_id),
            reason_id=str(payload.reason_id) if payload.reason_id else None,
            notes=payload.notes,
            credit_note_pending=False,
            created_by=user_id,
        )
        self.db.add(rma)
        self.db.flush()

        # Create lines
        lines = []
        for line_in in payload.lines:
            line = self._build_return_line(rma, line_in, company_id, user_id)
            lines.append(line)

        return self._to_read(rma, lines)

    def _build_return_line(
        self,
        rma: VendorReturn,
        line_in: ReturnLineCreate,
        company_id: UUID,
        user_id: UUID,
    ) -> ReturnLine:
        """Validate and create a ReturnLine, enforcing return quantity invariant."""
        # Fetch the referenced GR line (T172)
        gr_line = self.gr_line_repo.get_by_id_or_none(line_in.gr_line_id, company_id)
        if gr_line is None:
            raise NotFoundException(f"GRLine {line_in.gr_line_id} not found.")

        accepted_qty = Decimal(str(gr_line.quantity_received)) - Decimal(
            str(gr_line.quantity_rejected)
        )
        if line_in.quantity_returned > accepted_qty:
            raise RMAReturnQuantityError(
                str(line_in.gr_line_id), line_in.quantity_returned, accepted_qty
            )

        ln = ReturnLine(
            id=uuid4(),
            company_id=company_id,
            return_id=str(rma.id),
            gr_line_id=str(line_in.gr_line_id),
            product_id=gr_line.product_id,
            quantity_returned=line_in.quantity_returned,
            reason_id=str(line_in.reason_id) if line_in.reason_id else None,
            notes=line_in.notes,
            created_by=user_id,
        )
        self.db.add(ln)
        self.db.flush()
        return ln

    # ------------------------------------------------------------------
    # Update (header — DRAFT only)
    # ------------------------------------------------------------------

    def update_rma(
        self,
        rma_id: UUID,
        company_id: UUID,
        payload: VendorReturnUpdate,
    ) -> VendorReturnRead:
        rma = self._get_rma_or_404(rma_id, company_id)
        self._assert_mutable(rma)

        if payload.reason_id is not None:
            rma.reason_id = str(payload.reason_id)
        if payload.notes is not None:
            rma.notes = payload.notes
        # replacement_po_id can be set at any non-immutable state
        if payload.replacement_po_id is not None:
            rma.replacement_po_id = str(payload.replacement_po_id)

        self.db.flush()
        lines = self.line_repo.list_for_rma(rma_id, company_id)
        return self._to_read(rma, lines)

    def replace_lines(
        self,
        rma_id: UUID,
        company_id: UUID,
        new_lines: list[ReturnLineCreate],
        user_id: UUID,
    ) -> VendorReturnRead:
        rma = self._get_rma_or_404(rma_id, company_id)
        self._assert_mutable(rma)

        self.line_repo.delete_all_for_rma(rma_id, company_id)

        lines = []
        for line_in in new_lines:
            line = self._build_return_line(rma, line_in, company_id, user_id)
            lines.append(line)

        return self._to_read(rma, lines)

    # ------------------------------------------------------------------
    # State transitions (T173)
    # ------------------------------------------------------------------

    def submit_rma(
        self, rma_id: UUID, company_id: UUID, user_id: UUID
    ) -> VendorReturnRead:
        """DRAFT → SUBMITTED."""
        rma = self._get_rma_or_404(rma_id, company_id)
        self._assert_transition(rma, "SUBMITTED")

        lines = self.line_repo.list_for_rma(rma_id, company_id)
        if not lines:
            raise ConflictException("Cannot submit a VendorReturn with no lines.")

        rma.status = "SUBMITTED"
        self.db.flush()

        get_event_bus().publish(
            GoodsReturnInitiated.create(
                aggregate_id=rma.id,
                company_id=company_id,
                rma_number=rma.rma_number,
                gr_id=rma.gr_id,
                supplier_id=rma.supplier_id,
                actor_id=user_id,
            )
        )
        return self._to_read(rma, lines)

    def approve_rma(
        self, rma_id: UUID, company_id: UUID, user_id: UUID
    ) -> VendorReturnRead:
        """SUBMITTED → APPROVED."""
        rma = self._get_rma_or_404(rma_id, company_id)
        self._assert_transition(rma, "APPROVED")

        rma.status = "APPROVED"
        self.db.flush()

        lines = self.line_repo.list_for_rma(rma_id, company_id)
        get_event_bus().publish(
            GoodsReturnApproved.create(
                aggregate_id=rma.id,
                company_id=company_id,
                rma_number=rma.rma_number,
                gr_id=rma.gr_id,
                supplier_id=rma.supplier_id,
                actor_id=user_id,
            )
        )
        return self._to_read(rma, lines)

    def dispatch_rma(
        self, rma_id: UUID, company_id: UUID, user_id: UUID
    ) -> VendorReturnRead:
        """APPROVED → DISPATCHED (atomic with Epic 5 stock deduction — T174).

        Steps within the same database transaction:
          1. Validate return quantities are still within accepted GR quantities
          2. Create PURCHASE_RETURN_OUTBOUND stock movement per line with product
          3. Set status to DISPATCHED and record dispatched_at timestamp
          4. Publish GoodsReturned event

        If any stock movement fails the entire operation rolls back.
        """
        rma = self._get_rma_or_404(rma_id, company_id)
        self._assert_transition(rma, "DISPATCHED")

        lines = self.line_repo.list_for_rma(rma_id, company_id)
        if not lines:
            raise ConflictException("Cannot dispatch a VendorReturn with no lines.")

        # Fetch the parent GR for warehouse_id
        gr = self.gr_repo.get_by_id_or_none(UUID(rma.gr_id), company_id)
        warehouse_id: UUID | None = (
            UUID(gr.warehouse_id) if gr and gr.warehouse_id else None
        )

        total_returned = Decimal("0")

        for line in lines:
            qty = Decimal(str(line.quantity_returned))
            total_returned += qty

            if line.product_id and warehouse_id:
                self._create_return_stock_movement(
                    rma=rma,
                    return_line=line,
                    company_id=company_id,
                    product_id=UUID(line.product_id),
                    warehouse_id=warehouse_id,
                    quantity=qty,
                    actor_id=user_id,
                )

        rma.status = "DISPATCHED"
        rma.dispatched_at = utcnow()
        self.db.flush()

        get_event_bus().publish(
            GoodsReturned.create(
                aggregate_id=rma.id,
                company_id=company_id,
                rma_number=rma.rma_number,
                gr_id=rma.gr_id,
                supplier_id=rma.supplier_id,
                total_returned=str(total_returned),
                actor_id=user_id,
            )
        )
        return self._to_read(rma, lines)

    def complete_rma(
        self, rma_id: UUID, company_id: UUID, user_id: UUID
    ) -> VendorReturnRead:
        """DISPATCHED → COMPLETED, sets credit_note_pending = True (T175)."""
        rma = self._get_rma_or_404(rma_id, company_id)
        self._assert_transition(rma, "COMPLETED")

        rma.status = "COMPLETED"
        rma.completed_at = utcnow()
        rma.credit_note_pending = True
        self.db.flush()

        lines = self.line_repo.list_for_rma(rma_id, company_id)
        get_event_bus().publish(
            GoodsReturnCompleted.create(
                aggregate_id=rma.id,
                company_id=company_id,
                rma_number=rma.rma_number,
                gr_id=rma.gr_id,
                supplier_id=rma.supplier_id,
                credit_note_pending=True,
                actor_id=user_id,
            )
        )
        return self._to_read(rma, lines)

    def cancel_rma(
        self, rma_id: UUID, company_id: UUID, user_id: UUID
    ) -> VendorReturnRead:
        """SUBMITTED/APPROVED → CANCELLED."""
        rma = self._get_rma_or_404(rma_id, company_id)
        self._assert_transition(rma, "CANCELLED")

        rma.status = "CANCELLED"
        self.db.flush()

        lines = self.line_repo.list_for_rma(rma_id, company_id)
        return self._to_read(rma, lines)

    # ------------------------------------------------------------------
    # Replacement PO linkage (T176) — state-neutral
    # ------------------------------------------------------------------

    def link_replacement_po(
        self, rma_id: UUID, company_id: UUID, po_id: UUID
    ) -> VendorReturnRead:
        """Store replacement_po_id on the RMA. Does not affect RMA state (T176)."""
        rma = self._get_rma_or_404(rma_id, company_id)
        if rma.status in {"COMPLETED", "CANCELLED"}:
            raise RMAImmutableError(rma.id, rma.status)

        rma.replacement_po_id = str(po_id)
        self.db.flush()

        lines = self.line_repo.list_for_rma(rma_id, company_id)
        return self._to_read(rma, lines)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_rma(self, rma_id: UUID, company_id: UUID) -> VendorReturnRead:
        rma = self._get_rma_or_404(rma_id, company_id)
        lines = self.line_repo.list_for_rma(rma_id, company_id)
        return self._to_read(rma, lines)

    def list_rmas(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        gr_id: str | None = None,
        supplier_id: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[VendorReturnListRead]:
        rmas = self.rma_repo.list_for_company(
            company_id,
            status=status,
            gr_id=gr_id,
            supplier_id=supplier_id,
            skip=skip,
            limit=limit,
        )
        return [VendorReturnListRead.model_validate(r) for r in rmas]

    # ------------------------------------------------------------------
    # Epic 5 stock movement integration (T174)
    # ------------------------------------------------------------------

    def _create_return_stock_movement(
        self,
        rma: VendorReturn,
        return_line: ReturnLine,
        company_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
        quantity: Decimal,
        actor_id: UUID,
    ) -> None:
        """Create a PURCHASE_RETURN_OUTBOUND stock movement via Epic 5 repositories."""
        from modules.inventory.models.stock import StockMovement
        from modules.inventory.repositories.stock_repository import (
            StockMovementRepository,
            StockPositionRepository,
        )

        pos_repo = StockPositionRepository(self.db)
        mov_repo = StockMovementRepository(self.db)

        pos, _ = pos_repo.get_or_create(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
        )

        movement = StockMovement(
            id=uuid4(),
            company_id=company_id,
            product_id=str(product_id),
            warehouse_id=str(warehouse_id),
            movement_type="PURCHASE_RETURN_OUTBOUND",
            direction="OUT",
            quantity=quantity,
            unit_cost=pos.unit_cost,
            total_cost=quantity
            * (Decimal(str(pos.unit_cost)) if pos.unit_cost else Decimal("0")),
            reference_type="VENDOR_RETURN",
            reference_id=str(rma.id),
            notes=f"RMA {rma.rma_number}",
            performed_at=rma.dispatched_at or utcnow(),
            created_by=actor_id,
        )
        mov_repo.append(movement)

        current_qty = Decimal(str(pos.qty_on_hand))
        pos.qty_on_hand = max(Decimal("0"), current_qty - quantity)
        self.db.flush()

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def _to_read(self, rma: VendorReturn, lines: list[ReturnLine]) -> VendorReturnRead:
        data = VendorReturnRead.model_validate(rma)
        data.lines = [ReturnLineRead.model_validate(ln) for ln in lines]
        return data

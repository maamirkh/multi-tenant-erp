"""Goods Receipt application service — Phase 6.

Provides the complete GR lifecycle:
  create_gr      — initialise a DRAFT GR from an approved PO
  update_gr      — update GR header (DRAFT only)
  update_lines   — replace / update GR lines (DRAFT only)
  confirm_gr     — DRAFT → CONFIRMED (atomic: stock movements + PO status + rating)
  get_gr         — retrieve single GR with lines
  list_grs       — paginated GR list
  get_open_quantities — per-PO-line open qty for the GR creation UI

State Machine (T155):
  DRAFT → CONFIRMED (immutable after confirmation)

Business Rules (T151-T155):
  - GR can only be created against APPROVED or PARTIALLY_RECEIVED PO
  - Once CONFIRMED, no edits or deletes are allowed
  - Confirmation is atomic: GR, stock, PO status all-or-nothing in one transaction
  - Over-receipt policy: BLOCK (raise), WARN (publish event), ALLOW (silent)
  - PPV = (gr_unit_cost − po_unit_cost) × quantity_received
  - Stock movement created per line when product_id + warehouse_id are set

Spec ref: specs/006-purchase-management/spec.md §17 Goods Receiving
Tasks: T151, T152, T153, T154, T155
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException, NotFoundException
from core.utils.datetime import utcnow
from modules.purchase.events import get_event_bus
from modules.purchase.events.gr_events import (
    GoodsPartiallyReceived,
    GoodsReceived,
    GoodsRejected,
    OverReceiptDetected,
)
from modules.purchase.models.goods_receipt import GoodsReceipt, GRLine
from modules.purchase.models.purchase_order import POLine, PurchaseOrder
from modules.purchase.repositories.goods_receipt import (
    GoodsReceiptRepository,
    GRLineRepository,
)
from modules.purchase.repositories.purchase_order import (
    POLineRepository,
    PurchaseOrderRepository,
)
from modules.purchase.schemas.goods_receipt import (
    GoodsReceiptCreate,
    GoodsReceiptListRead,
    GoodsReceiptRead,
    GoodsReceiptUpdate,
    GRLineCreate,
    GRLineRead,
    GROpenQuantity,
)
from modules.purchase.services.sequence_service import PurchaseSequenceService

if TYPE_CHECKING:
    from modules.inventory.services.stock_service import StockLedgerService
    from modules.purchase.services.cost_service import CostService
    from modules.purchase.services.po_service import POService
    from modules.purchase.services.supplier_rating_service import (
        SupplierRatingService,
    )

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


class GRImmutableError(Exception):
    """Raised when an edit is attempted on a CONFIRMED GR."""

    def __init__(self, gr_id: UUID) -> None:
        super().__init__(
            f"GoodsReceipt {gr_id} is CONFIRMED and cannot be edited. "
            "GR corrections must be made via Vendor Return."
        )


class GRInvalidPOStatusError(Exception):
    """Raised when a GR is created against a PO that is not APPROVED or PARTIALLY_RECEIVED."""

    def __init__(self, po_id: UUID, po_status: str) -> None:
        super().__init__(
            f"Cannot create a GR against PurchaseOrder {po_id} "
            f"in status {po_status!r}. PO must be APPROVED or PARTIALLY_RECEIVED."
        )


class GROverReceiptError(Exception):
    """Raised when over-receipt policy is BLOCK and a line exceeds open quantity."""

    def __init__(self, po_line_id: str, received: Decimal, open_qty: Decimal) -> None:
        super().__init__(
            f"Over-receipt blocked for POLine {po_line_id}: "
            f"received={received}, open_qty={open_qty}. "
            "Reduce quantity or change the over-receipt policy to WARN/ALLOW."
        )


# ---------------------------------------------------------------------------
# PPV computation (T154)
# ---------------------------------------------------------------------------


def _compute_ppv(
    unit_cost: Decimal,
    po_unit_cost: Decimal,
    quantity_received: Decimal,
) -> tuple[Decimal, Decimal]:
    """Return (ppv_amount, ppv_percentage).

    ppv_amount      = (unit_cost - po_unit_cost) * quantity_received
    ppv_percentage  = ppv_amount / (po_unit_cost * quantity_received) * 100
                      (0.0 if po cost is zero)
    """
    ppv_amount = (unit_cost - po_unit_cost) * quantity_received
    base = po_unit_cost * quantity_received
    ppv_percentage = (ppv_amount / base * Decimal("100")) if base != 0 else Decimal("0")
    return (
        ppv_amount.quantize(Decimal("0.01")),
        ppv_percentage.quantize(Decimal("0.0001")),
    )


# ---------------------------------------------------------------------------
# GRService
# ---------------------------------------------------------------------------


class GRService:
    """Application service for the GoodsReceipt aggregate."""

    def __init__(
        self,
        db: Session,
        gr_repo: GoodsReceiptRepository,
        line_repo: GRLineRepository,
        po_repo: PurchaseOrderRepository,
        po_line_repo: POLineRepository,
        sequence_service: PurchaseSequenceService,
        po_service: POService
        | None = None,  # injected to avoid circular import at module load
        rating_service: SupplierRatingService | None = None,
        stock_ledger_service: StockLedgerService | None = None,  # Epic 5
        cost_service: CostService | None = None,  # Phase 8 cost entry creation
    ) -> None:
        self.db = db
        self.gr_repo = gr_repo
        self.line_repo = line_repo
        self.po_repo = po_repo
        self.po_line_repo = po_line_repo
        self.sequence_service = sequence_service
        self.po_service = po_service
        self.rating_service = rating_service
        self.stock_ledger_service = stock_ledger_service
        self.cost_service = cost_service

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_gr_or_404(self, gr_id: UUID, company_id: UUID) -> GoodsReceipt:
        gr = self.gr_repo.get_by_id_or_none(gr_id, company_id)
        if gr is None:
            raise NotFoundException(f"GoodsReceipt {gr_id} not found.")
        return gr

    def _get_po_or_404(self, po_id: UUID, company_id: UUID) -> PurchaseOrder:
        po = self.po_repo.get_by_id_or_none(po_id, company_id)
        if po is None:
            raise NotFoundException(f"PurchaseOrder {po_id} not found.")
        return po

    def _assert_draft(self, gr: GoodsReceipt) -> None:
        if gr.status != "DRAFT":
            raise GRImmutableError(gr.id)

    def _build_gr_read(self, gr: GoodsReceipt) -> GoodsReceiptRead:
        lines = self.line_repo.list_for_gr(gr.id, gr.company_id)
        return GoodsReceiptRead(
            id=gr.id,
            company_id=gr.company_id,
            gr_number=gr.gr_number,
            status=gr.status,
            po_id=str(gr.po_id),
            supplier_id=str(gr.supplier_id),
            received_by=str(gr.received_by) if gr.received_by else None,
            received_at=gr.received_at,
            delivery_note_number=gr.delivery_note_number,
            notes=gr.notes,
            warehouse_id=str(gr.warehouse_id) if gr.warehouse_id else None,
            landed_cost_ready=gr.landed_cost_ready,
            lines=[GRLineRead.model_validate(ln) for ln in lines],
        )

    # ------------------------------------------------------------------
    # T152: Open quantity computation
    # ------------------------------------------------------------------

    def _compute_open_qty(
        self,
        po_line: POLine,
        company_id: UUID,
        exclude_gr_id: UUID | None = None,
    ) -> Decimal:
        """open_qty = quantity_ordered - sum(confirmed GR lines for this po_line).

        Excludes the current DRAFT GR (if exclude_gr_id provided) so the
        calculation uses only previously CONFIRMED receipts.
        """
        received_so_far = self.line_repo.get_received_qty_for_po_line(
            UUID(str(po_line.id)),
            company_id,
            exclude_gr_id=exclude_gr_id,
        )
        return Decimal(str(po_line.quantity_ordered)) - received_so_far

    def get_open_quantities(
        self, po_id: UUID, company_id: UUID
    ) -> list[GROpenQuantity]:
        """Return per-line open quantities for the GR creation UI (T152)."""
        self._get_po_or_404(po_id, company_id)  # validate PO exists
        lines = self.po_line_repo.list_for_po(po_id, company_id)
        result = []
        for ln in lines:
            received_so_far = self.line_repo.get_received_qty_for_po_line(
                UUID(str(ln.id)), company_id
            )
            open_qty = Decimal(str(ln.quantity_ordered)) - received_so_far
            result.append(
                GROpenQuantity(
                    po_line_id=str(ln.id),
                    product_description=ln.product_description,
                    quantity_ordered=Decimal(str(ln.quantity_ordered)),
                    quantity_received_so_far=received_so_far,
                    open_quantity=open_qty,
                    unit_cost=Decimal(str(ln.unit_cost)),
                )
            )
        return result

    # ------------------------------------------------------------------
    # T153: Over-receipt policy validation
    # ------------------------------------------------------------------

    def _validate_over_receipt(
        self,
        gr: GoodsReceipt,
        lines: list[GRLine],
        policy: str,
    ) -> list[GRLine]:
        """Validate lines against open quantities per the over-receipt policy.

        policy:
          BLOCK — raise GROverReceiptError if any line exceeds open_qty
          WARN  — publish OverReceiptDetected, allow
          ALLOW — silent, allow

        Returns the list of lines unchanged (side-effects may include events).
        """
        over_receipt_lines: list[GRLine] = []

        for ln in lines:
            open_qty = self._compute_open_qty(
                self._get_po_line(UUID(str(ln.po_line_id)), gr.company_id),
                gr.company_id,
                exclude_gr_id=gr.id,
            )
            received = Decimal(str(ln.quantity_received))

            if received > open_qty:
                if policy == "BLOCK":
                    raise GROverReceiptError(str(ln.po_line_id), received, open_qty)
                over_receipt_lines.append(ln)

        if over_receipt_lines and policy == "WARN":
            get_event_bus().publish(
                OverReceiptDetected.create(
                    aggregate_id=gr.id,
                    company_id=gr.company_id,
                    gr_number=gr.gr_number,
                    po_id=str(gr.po_id),
                    supplier_id=str(gr.supplier_id),
                    over_received_lines=len(over_receipt_lines),
                )
            )

        return lines

    def _get_po_line(self, po_line_id: UUID, company_id: UUID) -> POLine:
        """Retrieve a single PO line or raise NotFoundException."""
        from sqlalchemy import select as sa_select

        stmt = (
            sa_select(POLine)
            .where(POLine.id == po_line_id)
            .where(POLine.company_id == company_id)
            .where(POLine.is_deleted == False)  # noqa: E712
        )
        line = self.db.execute(stmt).scalars().one_or_none()
        if line is None:
            raise NotFoundException(f"POLine {po_line_id} not found.")
        return line

    # ------------------------------------------------------------------
    # T151: create_gr
    # ------------------------------------------------------------------

    def create_gr(
        self,
        payload: GoodsReceiptCreate,
        company_id: UUID,
        user_id: UUID,
    ) -> GoodsReceiptRead:
        """Create a DRAFT GR against an APPROVED or PARTIALLY_RECEIVED PO (T151)."""
        po = self._get_po_or_404(payload.po_id, company_id)

        if po.status not in ("APPROVED", "PARTIALLY_RECEIVED"):
            raise GRInvalidPOStatusError(payload.po_id, po.status)

        gr_number = self.sequence_service.generate_next_number(company_id, "GR")

        gr = GoodsReceipt(
            id=uuid4(),
            company_id=company_id,
            gr_number=gr_number,
            status="DRAFT",
            po_id=str(payload.po_id),
            supplier_id=str(po.supplier_id) if po.supplier_id else "",
            received_by=str(user_id),
            delivery_note_number=payload.delivery_note_number,
            notes=payload.notes,
            warehouse_id=str(payload.warehouse_id) if payload.warehouse_id else None,
            landed_cost_ready=True,
            created_by=user_id,
        )
        self.db.add(gr)
        self.db.flush()

        # Create initial lines from payload
        for line_data in payload.lines:
            self._create_line(gr, line_data, company_id, user_id)

        self.db.flush()
        # Missing-commit defect fixed during Epic 1-8 live verification
        # (2026-08-14) — see backend/modules/inventory/services/
        # warehouse_service.py::create_warehouse's comment for the full
        # root-cause explanation.
        self.db.commit()
        return self._build_gr_read(gr)

    def _create_line(
        self,
        gr: GoodsReceipt,
        line_data: GRLineCreate,
        company_id: UUID,
        user_id: UUID,
    ) -> GRLine:
        """Create a single GR line, capturing PO unit cost for PPV."""
        po_line = self._get_po_line(line_data.po_line_id, company_id)
        po_unit_cost = Decimal(str(po_line.unit_cost))
        unit_cost = (
            line_data.unit_cost if line_data.unit_cost is not None else po_unit_cost
        )

        ppv_amount, ppv_pct = _compute_ppv(
            unit_cost, po_unit_cost, line_data.quantity_received
        )

        ln = GRLine(
            id=uuid4(),
            company_id=company_id,
            gr_id=str(gr.id),
            po_line_id=str(line_data.po_line_id),
            product_id=str(po_line.product_id) if po_line.product_id else None,
            quantity_received=line_data.quantity_received,
            quantity_rejected=line_data.quantity_rejected,
            rejection_reason_id=(
                str(line_data.rejection_reason_id)
                if line_data.rejection_reason_id
                else None
            ),
            unit_cost=unit_cost,
            po_unit_cost=po_unit_cost,
            ppv_amount=ppv_amount,
            ppv_percentage=ppv_pct,
            notes=line_data.notes,
            created_by=user_id,
        )
        self.db.add(ln)
        return ln

    # ------------------------------------------------------------------
    # Update GR header (T155 — DRAFT only)
    # ------------------------------------------------------------------

    def update_gr(
        self,
        gr_id: UUID,
        company_id: UUID,
        payload: GoodsReceiptUpdate,
    ) -> GoodsReceiptRead:
        """Update GR header fields. Only permitted in DRAFT status."""
        gr = self._get_gr_or_404(gr_id, company_id)
        self._assert_draft(gr)

        if payload.delivery_note_number is not None:
            gr.delivery_note_number = payload.delivery_note_number
        if payload.notes is not None:
            gr.notes = payload.notes
        if payload.warehouse_id is not None:
            gr.warehouse_id = str(payload.warehouse_id)

        self.db.flush()
        return self._build_gr_read(gr)

    # ------------------------------------------------------------------
    # Update GR lines (T155 — DRAFT only)
    # ------------------------------------------------------------------

    def replace_lines(
        self,
        gr_id: UUID,
        company_id: UUID,
        lines: list[GRLineCreate],
        user_id: UUID,
    ) -> GoodsReceiptRead:
        """Replace all GR lines (soft-delete existing, create new). DRAFT only."""
        gr = self._get_gr_or_404(gr_id, company_id)
        self._assert_draft(gr)

        self.line_repo.delete_all_for_gr(gr_id, company_id)
        for line_data in lines:
            self._create_line(gr, line_data, company_id, user_id)

        self.db.flush()
        return self._build_gr_read(gr)

    # ------------------------------------------------------------------
    # T154: confirm_gr — atomic confirmation
    # ------------------------------------------------------------------

    def confirm_gr(
        self,
        gr_id: UUID,
        company_id: UUID,
        user_id: UUID,
        over_receipt_policy: str = "WARN",
    ) -> GoodsReceiptRead:
        """Confirm a DRAFT GR — atomic: validate, set CONFIRMED, stock, PO status, rating (T154).

        Steps (all-or-nothing in one DB transaction):
          1. Load GR, assert DRAFT
          2. Load lines; validate over-receipt policy (T153)
          3. Update GR status → CONFIRMED; stamp received_at
          4. For each line with product_id + warehouse_id → create PURCHASE_RECEIPT stock movement
          5. Update POLine.quantity_received / open_quantity for each line
          6. Call POService.auto_update_status_on_gr → PARTIALLY_RECEIVED / FULLY_RECEIVED
          7. Recompute supplier rating (T154)
          8. Publish domain events (T157)
        """
        gr = self._get_gr_or_404(gr_id, company_id)
        self._assert_draft(gr)

        lines = self.line_repo.list_for_gr(gr_id, company_id)
        if not lines:
            raise ConflictException("Cannot confirm a GR with no lines.")

        # Step 2: over-receipt policy check
        policy = over_receipt_policy.upper() if over_receipt_policy else "WARN"
        self._validate_over_receipt(gr, lines, policy)

        # Step 3: mark GR as CONFIRMED
        now = utcnow()
        gr.status = "CONFIRMED"
        gr.received_at = now
        self.db.flush()

        # Step 4 + 5: stock movements and PO line updates
        self._apply_stock_and_po_lines(gr, lines, company_id, user_id)

        # Step 6: PO status update
        po_id = UUID(str(gr.po_id))
        if self.po_service is not None:
            try:
                self.po_service.auto_update_status_on_gr(po_id, company_id)
            except Exception:
                logger.exception("auto_update_status_on_gr failed for PO %s", po_id)

        # Step 7: supplier rating recompute
        if self.rating_service is not None and gr.supplier_id:
            try:
                self._recompute_supplier_rating(gr, lines, company_id, user_id)
            except Exception:
                logger.exception(
                    "Supplier rating recompute failed for supplier %s", gr.supplier_id
                )

        # Step 8: domain events
        self._publish_gr_events(gr, lines)

        # Step 9: purchase cost entry snapshot (Phase 8) — optional service
        if self.cost_service is not None:
            try:
                self.cost_service.create_cost_entry_on_gr_confirm(
                    gr=gr, lines=lines, company_id=company_id
                )
            except Exception:
                logger.exception(
                    "Cost entry creation failed for GR %s — rolling back", gr_id
                )
                raise

            # Step 10: PPV alerts (Phase 8)
            try:
                self.cost_service.check_ppv_alerts(gr, lines, company_id)
            except Exception:
                logger.exception("PPV alert check failed for GR %s (non-fatal)", gr_id)

        self.db.flush()
        # Missing-commit defect fixed during Epic 1-8 live verification
        # (2026-08-14) — see create_gr() above. This atomic multi-step
        # operation (GR status + stock movements + PO line quantities +
        # cost entries) was entirely uncommitted despite its own docstring
        # describing it as "all-or-nothing in one DB transaction" — the
        # transaction was real, it just never reached COMMIT.
        self.db.commit()
        return self._build_gr_read(gr)

    def _apply_stock_and_po_lines(
        self,
        gr: GoodsReceipt,
        lines: list[GRLine],
        company_id: UUID,
        user_id: UUID,
    ) -> None:
        """Create stock movements (if possible) and update POLine received quantities."""
        for ln in lines:
            quantity_received = Decimal(str(ln.quantity_received))
            unit_cost = Decimal(str(ln.unit_cost))

            # Stock movement (Epic 5) — only when product_id and warehouse_id are set
            if (
                ln.product_id
                and gr.warehouse_id
                and self.stock_ledger_service is not None
            ):
                try:
                    self._record_purchase_receipt_movement(
                        gr=gr,
                        gr_line=ln,
                        company_id=company_id,
                        product_id=UUID(str(ln.product_id)),
                        warehouse_id=UUID(str(gr.warehouse_id)),
                        quantity=quantity_received,
                        unit_cost=unit_cost,
                        actor_id=user_id,
                    )
                except Exception:
                    logger.exception(
                        "Stock movement failed for GRLine %s product %s",
                        ln.id,
                        ln.product_id,
                    )
                    raise

            # Update POLine.quantity_received and open_quantity
            self._update_po_line_quantities(
                UUID(str(ln.po_line_id)),
                company_id,
                quantity_received=quantity_received,
                quantity_rejected=Decimal(str(ln.quantity_rejected)),
            )

    def _record_purchase_receipt_movement(
        self,
        *,
        gr: GoodsReceipt,
        gr_line: GRLine,
        company_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
        quantity: Decimal,
        unit_cost: Decimal,
        actor_id: UUID,
    ) -> None:
        """Delegate PURCHASE_RECEIPT movement to StockLedgerService (Epic 5)."""
        from modules.inventory.models.stock import StockMovement
        from modules.inventory.repositories.stock_repository import (
            StockMovementRepository,
            StockPositionRepository,
        )

        # Direct repository approach — same pattern as StockLedgerService
        pos_repo = StockPositionRepository(self.db)
        mov_repo = StockMovementRepository(self.db)

        pos, _ = pos_repo.get_or_create(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
        )

        # WAC cost update
        from decimal import Decimal as D  # noqa: N817

        current_qty = D(str(pos.qty_on_hand))
        current_cost = D(str(pos.unit_cost)) if pos.unit_cost is not None else None

        if current_qty <= 0 or current_cost is None:
            new_cost = unit_cost
        else:
            total_value = (current_qty * current_cost) + (quantity * unit_cost)
            new_cost = total_value / (current_qty + quantity)

        movement = StockMovement(
            id=uuid4(),
            company_id=company_id,
            product_id=str(product_id),
            warehouse_id=str(warehouse_id),
            movement_type="PURCHASE_RECEIPT",
            direction="IN",
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=quantity * unit_cost,
            reference_type="GOODS_RECEIPT",
            reference_id=str(gr.id),
            notes=f"GR {gr.gr_number}",
            performed_at=gr.received_at or utcnow(),
            created_by=actor_id,
        )
        mov_repo.append(movement)

        pos.qty_on_hand = current_qty + quantity
        pos.unit_cost = new_cost
        self.db.flush()

    def _update_po_line_quantities(
        self,
        po_line_id: UUID,
        company_id: UUID,
        quantity_received: Decimal,
        quantity_rejected: Decimal,
    ) -> None:
        """Update POLine.quantity_received, quantity_rejected, and open_quantity."""
        from sqlalchemy import select as sa_select

        line = (
            self.db.execute(
                sa_select(POLine)
                .where(POLine.id == po_line_id)
                .where(POLine.company_id == company_id)
                .where(POLine.is_deleted == False)  # noqa: E712
            )
            .scalars()
            .one_or_none()
        )

        if line is None:
            logger.warning("POLine %s not found during GR confirmation", po_line_id)
            return

        current_received = Decimal(str(line.quantity_received))
        current_rejected = Decimal(str(line.quantity_rejected))
        ordered = Decimal(str(line.quantity_ordered))

        new_received = current_received + quantity_received
        new_rejected = current_rejected + quantity_rejected
        new_open = max(Decimal("0"), ordered - new_received)

        line.quantity_received = new_received
        line.quantity_rejected = new_rejected
        line.open_quantity = new_open
        self.db.flush()

    def _recompute_supplier_rating(
        self,
        gr: GoodsReceipt,
        lines: list[GRLine],
        company_id: UUID,
        actor_id: UUID,
    ) -> None:
        """Trigger supplier rating recomputation after GR confirmation (T154)."""
        supplier_id = UUID(str(gr.supplier_id))

        # Compute fill rate and rejection rate from this GR
        total_received = sum(
            (Decimal(str(ln.quantity_received)) for ln in lines), start=Decimal("0")
        )
        total_rejected = sum(
            (Decimal(str(ln.quantity_rejected)) for ln in lines), start=Decimal("0")
        )

        # Get PO to compute fill rate and on-time rate
        po = self.po_repo.get_by_id_or_none(UUID(str(gr.po_id)), company_id)
        po_lines = self.po_line_repo.list_for_po(UUID(str(gr.po_id)), company_id)
        total_ordered = sum(
            Decimal(str(ln.quantity_ordered)) for ln in po_lines
        ) or Decimal("1")

        fill_rate = (total_received / total_ordered * Decimal("100")).quantize(
            Decimal("0.01")
        )
        rejection_rate = (
            (total_rejected / total_received * Decimal("100")).quantize(Decimal("0.01"))
            if total_received > 0
            else Decimal("0")
        )

        # On-time rate: was received_at ≤ expected_delivery_date?
        on_time = Decimal("100")
        if po and po.expected_delivery_date and gr.received_at:
            delivery_date = gr.received_at.date()
            if delivery_date > po.expected_delivery_date:
                on_time = Decimal("0")

        if self.rating_service is not None:
            self.rating_service.upsert_rating(
                company_id=company_id,
                supplier_id=supplier_id,
                on_time_rate=on_time,
                fill_rate=fill_rate,
                rejection_rate=rejection_rate,
                gr_count_window=1,
                actor_id=actor_id,
            )

    def _publish_gr_events(
        self,
        gr: GoodsReceipt,
        lines: list[GRLine],
    ) -> None:
        """Publish domain events after GR confirmation (T157)."""
        bus = get_event_bus()
        total_received = str(sum(Decimal(str(ln.quantity_received)) for ln in lines))

        bus.publish(
            GoodsReceived.create(
                aggregate_id=gr.id,
                company_id=gr.company_id,
                gr_number=gr.gr_number,
                po_id=str(gr.po_id),
                supplier_id=str(gr.supplier_id),
                total_received=total_received,
            )
        )

        if any(Decimal(str(ln.quantity_rejected)) > 0 for ln in lines):
            total_rejected = str(
                sum(Decimal(str(ln.quantity_rejected)) for ln in lines)
            )
            bus.publish(
                GoodsRejected.create(
                    aggregate_id=gr.id,
                    company_id=gr.company_id,
                    gr_number=gr.gr_number,
                    po_id=str(gr.po_id),
                    supplier_id=str(gr.supplier_id),
                    total_rejected=total_rejected,
                )
            )

        # Determine partial receipt: any line where received < open_qty (before confirmation)
        has_partial = any(
            Decimal(str(ln.quantity_received))
            < Decimal(
                str(
                    self._get_po_line(
                        UUID(str(ln.po_line_id)), gr.company_id
                    ).quantity_ordered
                )
            )
            for ln in lines
        )
        if has_partial:
            bus.publish(
                GoodsPartiallyReceived.create(
                    aggregate_id=gr.id,
                    company_id=gr.company_id,
                    gr_number=gr.gr_number,
                    po_id=str(gr.po_id),
                    supplier_id=str(gr.supplier_id),
                )
            )

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_gr(self, gr_id: UUID, company_id: UUID) -> GoodsReceiptRead:
        gr = self._get_gr_or_404(gr_id, company_id)
        return self._build_gr_read(gr)

    def list_grs(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        po_id: str | None = None,
        supplier_id: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[GoodsReceiptListRead], int]:
        items = self.gr_repo.list_for_company(
            company_id,
            status=status,
            po_id=po_id,
            supplier_id=supplier_id,
            skip=skip,
            limit=limit,
        )
        total = self.gr_repo.count_for_company(
            company_id,
            status=status,
            po_id=po_id,
            supplier_id=supplier_id,
        )
        reads = [GoodsReceiptListRead.model_validate(gr) for gr in items]
        return reads, total

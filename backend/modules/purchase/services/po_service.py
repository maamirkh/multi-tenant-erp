"""Purchase Order application service — Phase 5.

Provides the complete PO lifecycle:
  create_po          — create a new PO in DRAFT status
  update_po          — update PO metadata (DRAFT only)
  add_line           — add a line item to a DRAFT PO
  update_line        — update a line on a DRAFT PO
  remove_line        — soft-delete a line from a DRAFT PO
  add_charge         — add an additional charge to a DRAFT PO
  update_charge      — update a charge on a DRAFT PO
  remove_charge      — soft-delete a charge from a DRAFT PO
  submit_po          — DRAFT → PENDING_APPROVAL; trigger approval routing
  approve_po         — PENDING_APPROVAL → APPROVED
  reject_po          — PENDING_APPROVAL → REJECTED (revise and resubmit)
  amend_po           — APPROVED+ → create amendment, reset to PENDING_APPROVAL
  cancel_po          — DRAFT/PENDING_APPROVAL/APPROVED → CANCELLED
  close_po           — APPROVED/PARTIALLY_RECEIVED/FULLY_RECEIVED → CLOSED
  auto_update_status_on_gr — called by GRService; transitions PO on GR confirmation
  get_po             — retrieve a single PO with lines, charges, amendments
  list_pos           — paginated PO list
  get_overdue_pos    — POs past expected_delivery_date

State Machine (T123):
  DRAFT              → PENDING_APPROVAL  (submit_po)
  PENDING_APPROVAL   → APPROVED          (approve_po, or auto-approved)
  PENDING_APPROVAL   → REJECTED          (reject_po — revise and resubmit)
  REJECTED           → DRAFT             (revert — resubmit path)
  APPROVED           → PARTIALLY_RECEIVED (first GR confirmed)
  APPROVED / PARTIALLY_RECEIVED → FULLY_RECEIVED (all lines received)
  FULLY_RECEIVED     → CLOSED            (close_po or auto-close)
  APPROVED / PARTIALLY_RECEIVED / FULLY_RECEIVED → CLOSED (manual close)
  DRAFT / PENDING_APPROVAL / APPROVED → CANCELLED (cancel_po)

Business Rules (T124, T125, T126, T127, T128, T129):
  - APPROVED+ status: no direct field edits; amend_po is the only change path
  - Supplier must be set and ACTIVE before submission
  - PO must have at least one active line before submission
  - Credit limit checked at approval time (not creation)
  - Cancellation blocked if any confirmed GR exists
  - total = subtotal + total_charges − total_discounts + tax_amount

Spec ref: specs/006-purchase-management/spec.md §16 Purchase Orders
Tasks: T123–T130
"""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException, NotFoundException
from modules.purchase.events import get_event_bus
from modules.purchase.events.po_events import (
    PurchaseOrderAmended,
    PurchaseOrderApproved,
    PurchaseOrderCancelled,
    PurchaseOrderClosed,
    PurchaseOrdered,
    PurchaseOrderFullyReceived,
    PurchaseOrderRejected,
)
from modules.purchase.models.purchase_order import (
    POAdditionalCharge,
    POAmendment,
    POLine,
    PurchaseOrder,
)
from modules.purchase.repositories.feature_flag_repository import (
    PurchaseFeatureFlagRepository,
)
from modules.purchase.repositories.purchase_order import (
    POAdditionalChargeRepository,
    POAmendmentRepository,
    POLineRepository,
    PurchaseOrderRepository,
)
from modules.purchase.schemas.purchase_order import (
    POAdditionalChargeCreate,
    POAdditionalChargeRead,
    POAdditionalChargeUpdate,
    POAmendmentRead,
    POLineCreate,
    POLineRead,
    POLineUpdate,
    PurchaseOrderCreate,
    PurchaseOrderListRead,
    PurchaseOrderRead,
    PurchaseOrderUpdate,
)
from modules.purchase.services.feature_flag_service import PurchaseFeatureFlagService
from modules.purchase.services.sequence_service import PurchaseSequenceService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain exceptions  (T123)
# ---------------------------------------------------------------------------


class InvalidPOStatusTransitionError(Exception):
    """Raised when an illegal state machine transition is attempted."""

    def __init__(self, po_id: UUID, current: str, target: str) -> None:
        super().__init__(
            f"Cannot transition PO {po_id} from {current!r} to {target!r}."
        )


class POImmutableError(Exception):
    """Raised when a direct edit is attempted on an APPROVED+ PO."""

    def __init__(self, po_id: UUID, status: str) -> None:
        super().__init__(
            f"PurchaseOrder {po_id} is in {status!r} and cannot be edited directly. "
            f"Use the amendment workflow."
        )


class POMissingLinesError(Exception):
    """Raised when submit is called on a PO with no active lines."""

    def __init__(self, po_id: UUID) -> None:
        super().__init__(
            f"PurchaseOrder {po_id} must have at least one line before submission."
        )


class POMissingSupplierError(Exception):
    """Raised when submit is called without a supplier_id set."""

    def __init__(self, po_id: UUID) -> None:
        super().__init__(
            f"PurchaseOrder {po_id} must have a supplier assigned before submission."
        )


class POCancelBlockedError(Exception):
    """Raised when cancel is attempted after a confirmed GR exists."""

    def __init__(self, po_id: UUID) -> None:
        super().__init__(
            f"PurchaseOrder {po_id} cannot be cancelled because a confirmed GR exists."
        )


# ---------------------------------------------------------------------------
# Allowed state machine transitions  (T123)
# ---------------------------------------------------------------------------

ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "DRAFT": ["PENDING_APPROVAL", "CANCELLED"],
    "PENDING_APPROVAL": ["APPROVED", "REJECTED", "CANCELLED"],
    "REJECTED": ["DRAFT"],  # Revert to DRAFT for revision
    "APPROVED": ["PARTIALLY_RECEIVED", "FULLY_RECEIVED", "CLOSED", "CANCELLED"],
    "PARTIALLY_RECEIVED": ["FULLY_RECEIVED", "CLOSED"],
    "FULLY_RECEIVED": ["CLOSED"],
    "CLOSED": [],
    "CANCELLED": [],
}

# Statuses where direct field edits are forbidden (immutability invariant)
IMMUTABLE_STATUSES = {"APPROVED", "PARTIALLY_RECEIVED", "FULLY_RECEIVED", "CLOSED"}


def _assert_transition(po_id: UUID, current: str, target: str) -> None:
    """Validate that the transition current → target is permitted."""
    if target not in ALLOWED_TRANSITIONS.get(current, []):
        raise InvalidPOStatusTransitionError(po_id, current, target)


# ---------------------------------------------------------------------------
# POService
# ---------------------------------------------------------------------------


class POService:
    """Application service for the PurchaseOrder aggregate."""

    def __init__(
        self,
        db: Session,
        po_repo: PurchaseOrderRepository,
        line_repo: POLineRepository,
        charge_repo: POAdditionalChargeRepository,
        amendment_repo: POAmendmentRepository,
        sequence_service: PurchaseSequenceService,
    ) -> None:
        self.db = db
        self.po_repo = po_repo
        self.line_repo = line_repo
        self.charge_repo = charge_repo
        self.amendment_repo = amendment_repo
        self.sequence_service = sequence_service

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_or_404(self, po_id: UUID, company_id: UUID) -> PurchaseOrder:
        po = self.po_repo.get_by_id_or_none(po_id, company_id)
        if po is None:
            raise NotFoundException(f"PurchaseOrder {po_id} not found.")
        return po

    def _assert_editable(self, po: PurchaseOrder) -> None:
        """Raise POImmutableError if the PO is in an immutable status."""
        if po.status in IMMUTABLE_STATUSES:
            raise POImmutableError(po.id, po.status)

    def _assert_draft(self, po: PurchaseOrder) -> None:
        """Raise ConflictException if PO is not in DRAFT status."""
        if po.status != "DRAFT":
            raise ConflictException(
                f"PurchaseOrder {po.id} must be in DRAFT to modify lines/charges "
                f"(current: {po.status!r})."
            )

    def _compute_line_total(
        self,
        unit_cost: Decimal,
        quantity_ordered: Decimal,
        line_discount_amount: Decimal | None,
        line_discount_percent: Decimal | None,
    ) -> tuple[Decimal, Decimal]:
        """Return (line_total, discount_amount) using Python Decimal arithmetic."""
        gross = (unit_cost * quantity_ordered).quantize(Decimal("0.01"))

        if line_discount_amount is not None:
            discount = line_discount_amount.quantize(Decimal("0.01"))
        elif line_discount_percent is not None:
            discount = (gross * line_discount_percent / Decimal("100")).quantize(
                Decimal("0.01")
            )
        else:
            discount = Decimal("0.00")

        line_total = max(Decimal("0.00"), gross - discount)
        return line_total, discount

    def _recalculate_totals(self, po_id: UUID, company_id: UUID) -> None:
        """Recompute and persist PO totals from lines and charges (T125)."""
        lines = self.line_repo.list_for_po(po_id, company_id)
        charges = self.charge_repo.list_for_po(po_id, company_id)

        subtotal = sum(
            (Decimal(str(ln.line_total)) for ln in lines),
            Decimal("0.00"),
        )
        total_charges = sum(
            (Decimal(str(ch.amount)) for ch in charges),
            Decimal("0.00"),
        )
        # total_discounts is already accounted for in line_totals
        total_discounts = Decimal("0.00")
        tax_amount = Decimal("0.00")
        total = subtotal + total_charges - total_discounts + tax_amount

        self.po_repo.update_totals(
            po_id,
            company_id,
            subtotal=subtotal,
            total_charges=total_charges,
            total_discounts=total_discounts,
            tax_amount=tax_amount,
            total=total,
        )

    def _build_po_read(self, po: PurchaseOrder) -> PurchaseOrderRead:
        """Build the full read schema including lines, charges, amendments."""
        company_id = po.company_id
        lines = self.line_repo.list_for_po(po.id, company_id)
        charges = self.charge_repo.list_for_po(po.id, company_id)
        amendments = self.amendment_repo.list_for_po(po.id, company_id)

        return PurchaseOrderRead(
            id=po.id,
            company_id=po.company_id,
            po_number=po.po_number,
            status=po.status,
            supplier_id=str(po.supplier_id) if po.supplier_id else None,
            purchase_request_id=(
                str(po.purchase_request_id) if po.purchase_request_id else None
            ),
            payment_terms_id=str(po.payment_terms_id) if po.payment_terms_id else None,
            expected_delivery_date=po.expected_delivery_date,
            supplier_reference=po.supplier_reference,
            currency_code=po.currency_code,
            subtotal=Decimal(str(po.subtotal)),
            total_charges=Decimal(str(po.total_charges)),
            total_discounts=Decimal(str(po.total_discounts)),
            tax_amount=Decimal(str(po.tax_amount)),
            total=Decimal(str(po.total)),
            notes=po.notes,
            version=po.version,
            lines=[POLineRead.model_validate(ln) for ln in lines],
            charges=[POAdditionalChargeRead.model_validate(ch) for ch in charges],
            amendments=[POAmendmentRead.model_validate(am) for am in amendments],
        )

    def _create_line(
        self,
        po_id: UUID,
        company_id: UUID,
        line_number: int,
        data: POLineCreate,
        actor_id: UUID | None = None,
    ) -> POLine:
        line_total, discount_amount = self._compute_line_total(
            Decimal(str(data.unit_cost)),
            Decimal(str(data.quantity_ordered)),
            (
                Decimal(str(data.line_discount_amount))
                if data.line_discount_amount is not None
                else None
            ),
            (
                Decimal(str(data.line_discount_percent))
                if data.line_discount_percent is not None
                else None
            ),
        )
        open_quantity = Decimal(str(data.quantity_ordered))
        line = POLine(
            company_id=company_id,
            po_id=str(po_id),
            pr_line_id=str(data.pr_line_id) if data.pr_line_id else None,
            line_number=line_number,
            product_id=str(data.product_id) if data.product_id else None,
            product_description=data.product_description,
            quantity_ordered=open_quantity,
            quantity_received=Decimal("0.000"),
            quantity_rejected=Decimal("0.000"),
            open_quantity=open_quantity,
            uom_id=str(data.uom_id) if data.uom_id else None,
            unit_cost=Decimal(str(data.unit_cost)),
            line_discount_percent=(
                Decimal(str(data.line_discount_percent))
                if data.line_discount_percent is not None
                else None
            ),
            line_discount_amount=discount_amount if discount_amount else None,
            line_total=line_total,
            tax_code=getattr(data, "tax_code", None),
            tax_rate=(
                Decimal(str(data.tax_rate))
                if getattr(data, "tax_rate", None) is not None
                else None
            ),
            tax_amount=(
                Decimal(str(data.tax_amount))
                if getattr(data, "tax_amount", None) is not None
                else None
            ),
            notes=data.notes,
            created_by=actor_id,
        )
        self.db.add(line)
        self.db.flush()
        return line

    # ------------------------------------------------------------------
    # Create  (T123)
    # ------------------------------------------------------------------

    def create_po(
        self,
        payload: PurchaseOrderCreate,
        company_id: UUID,
        actor_id: UUID,
    ) -> PurchaseOrderRead:
        """Create a new PurchaseOrder in DRAFT status with optional lines."""
        po_number = self.sequence_service.generate_next_number(company_id, "PO")

        po = PurchaseOrder(
            company_id=company_id,
            po_number=po_number,
            status="DRAFT",
            supplier_id=str(payload.supplier_id) if payload.supplier_id else None,
            purchase_request_id=(
                str(payload.purchase_request_id)
                if payload.purchase_request_id
                else None
            ),
            payment_terms_id=(
                str(payload.payment_terms_id) if payload.payment_terms_id else None
            ),
            expected_delivery_date=payload.expected_delivery_date,
            supplier_reference=payload.supplier_reference,
            currency_code=payload.currency_code,
            notes=payload.notes,
            subtotal=Decimal("0.00"),
            total_charges=Decimal("0.00"),
            total_discounts=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("0.00"),
            version=1,
            created_by=actor_id,
        )
        created = self.po_repo.create(po)
        self.db.flush()

        for idx, line_data in enumerate(payload.lines, start=1):
            self._create_line(created.id, company_id, idx, line_data, actor_id)

        self._recalculate_totals(created.id, company_id)
        self.db.expire(created)

        logger.info("PurchaseOrder created: %s (%s)", po_number, created.id)
        return self._build_po_read(created)

    # ------------------------------------------------------------------
    # Update PO metadata  (DRAFT only — T124)
    # ------------------------------------------------------------------

    def update_po(
        self,
        po_id: UUID,
        company_id: UUID,
        payload: PurchaseOrderUpdate,
        actor_id: UUID,
    ) -> PurchaseOrderRead:
        """Update metadata on a DRAFT PO."""
        po = self._get_or_404(po_id, company_id)
        self._assert_editable(po)
        self._assert_draft(po)

        if payload.supplier_id is not None:
            po.supplier_id = str(payload.supplier_id)
        if payload.payment_terms_id is not None:
            po.payment_terms_id = str(payload.payment_terms_id)
        if payload.expected_delivery_date is not None:
            po.expected_delivery_date = payload.expected_delivery_date
        if payload.supplier_reference is not None:
            po.supplier_reference = payload.supplier_reference
        if payload.currency_code is not None:
            po.currency_code = payload.currency_code
        if payload.notes is not None:
            po.notes = payload.notes

        self.po_repo.update(po)
        return self._build_po_read(po)

    # ------------------------------------------------------------------
    # Line management (DRAFT only)
    # ------------------------------------------------------------------

    def add_line(
        self,
        po_id: UUID,
        company_id: UUID,
        data: POLineCreate,
        actor_id: UUID,
    ) -> PurchaseOrderRead:
        po = self._get_or_404(po_id, company_id)
        self._assert_draft(po)
        next_num = self.line_repo.get_max_line_number(po_id, company_id) + 1
        self._create_line(po_id, company_id, next_num, data, actor_id)
        self._recalculate_totals(po_id, company_id)
        self.db.expire(po)
        return self._build_po_read(po)

    def update_line(
        self,
        po_id: UUID,
        line_id: UUID,
        company_id: UUID,
        data: POLineUpdate,
        actor_id: UUID,
    ) -> PurchaseOrderRead:
        po = self._get_or_404(po_id, company_id)
        self._assert_draft(po)

        line = self.line_repo.get_by_id_or_none(line_id, company_id)
        if line is None or str(line.po_id) != str(po_id):
            raise NotFoundException(f"POLine {line_id} not found on PO {po_id}.")

        if data.product_description is not None:
            line.product_description = data.product_description
        if data.quantity_ordered is not None:
            line.quantity_ordered = data.quantity_ordered
            line.open_quantity = data.quantity_ordered  # reset open qty on draft
        if data.unit_cost is not None:
            line.unit_cost = data.unit_cost
        if data.notes is not None:
            line.notes = data.notes

        # Recompute line total
        line_total, discount_amount = self._compute_line_total(
            Decimal(str(line.unit_cost)),
            Decimal(str(line.quantity_ordered)),
            (
                Decimal(str(data.line_discount_amount))
                if data.line_discount_amount is not None
                else (
                    Decimal(str(line.line_discount_amount))
                    if line.line_discount_amount is not None
                    else None
                )
            ),
            (
                Decimal(str(data.line_discount_percent))
                if data.line_discount_percent is not None
                else (
                    Decimal(str(line.line_discount_percent))
                    if line.line_discount_percent is not None
                    else None
                )
            ),
        )
        if data.line_discount_percent is not None:
            line.line_discount_percent = data.line_discount_percent
        if data.line_discount_amount is not None:
            line.line_discount_amount = data.line_discount_amount
        line.line_total = line_total
        self.line_repo.update(line)

        self._recalculate_totals(po_id, company_id)
        self.db.expire(po)
        return self._build_po_read(po)

    def remove_line(
        self,
        po_id: UUID,
        line_id: UUID,
        company_id: UUID,
    ) -> PurchaseOrderRead:
        po = self._get_or_404(po_id, company_id)
        self._assert_draft(po)

        line = self.line_repo.get_by_id_or_none(line_id, company_id)
        if line is None or str(line.po_id) != str(po_id):
            raise NotFoundException(f"POLine {line_id} not found on PO {po_id}.")

        self.line_repo.soft_delete(id=line_id, company_id=company_id)
        self._recalculate_totals(po_id, company_id)
        self.db.expire(po)
        return self._build_po_read(po)

    # ------------------------------------------------------------------
    # Charge management (DRAFT only)
    # ------------------------------------------------------------------

    def add_charge(
        self,
        po_id: UUID,
        company_id: UUID,
        data: POAdditionalChargeCreate,
        actor_id: UUID,
    ) -> PurchaseOrderRead:
        po = self._get_or_404(po_id, company_id)
        self._assert_draft(po)

        charge = POAdditionalCharge(
            company_id=company_id,
            po_id=str(po_id),
            charge_type=data.charge_type,
            description=data.description,
            amount=Decimal(str(data.amount)),
            created_by=actor_id,
        )
        self.db.add(charge)
        self.db.flush()
        self._recalculate_totals(po_id, company_id)
        self.db.expire(po)
        return self._build_po_read(po)

    def update_charge(
        self,
        po_id: UUID,
        charge_id: UUID,
        company_id: UUID,
        data: POAdditionalChargeUpdate,
        actor_id: UUID,
    ) -> PurchaseOrderRead:
        po = self._get_or_404(po_id, company_id)
        self._assert_draft(po)

        charge = self.charge_repo.get_by_id_or_none(charge_id, company_id)
        if charge is None or str(charge.po_id) != str(po_id):
            raise NotFoundException(
                f"POAdditionalCharge {charge_id} not found on PO {po_id}."
            )

        if data.description is not None:
            charge.description = data.description
        if data.amount is not None:
            charge.amount = Decimal(str(data.amount))
        self.charge_repo.update(charge)
        self._recalculate_totals(po_id, company_id)
        self.db.expire(po)
        return self._build_po_read(po)

    def remove_charge(
        self,
        po_id: UUID,
        charge_id: UUID,
        company_id: UUID,
    ) -> PurchaseOrderRead:
        po = self._get_or_404(po_id, company_id)
        self._assert_draft(po)
        charge = self.charge_repo.get_by_id_or_none(charge_id, company_id)
        if charge is None or str(charge.po_id) != str(po_id):
            raise NotFoundException(
                f"POAdditionalCharge {charge_id} not found on PO {po_id}."
            )
        self.charge_repo.soft_delete(id=charge_id, company_id=company_id)
        self._recalculate_totals(po_id, company_id)
        self.db.expire(po)
        return self._build_po_read(po)

    # ------------------------------------------------------------------
    # Submit  (T126)
    # ------------------------------------------------------------------

    def submit_po(
        self,
        po_id: UUID,
        company_id: UUID,
        actor_id: UUID,
    ) -> PurchaseOrderRead:
        """Transition DRAFT → PENDING_APPROVAL.

        Validates:
          - PO has at least one line
          - supplier_id is set
        """
        po = self._get_or_404(po_id, company_id)
        _assert_transition(po_id, po.status, "PENDING_APPROVAL")

        # Validate supplier is set
        if not po.supplier_id:
            raise POMissingSupplierError(po_id)

        # Validate at least one line
        lines = self.line_repo.list_for_po(po_id, company_id)
        if not lines:
            raise POMissingLinesError(po_id)

        self.po_repo.update_status(po_id, company_id, "PENDING_APPROVAL")
        po.status = "PENDING_APPROVAL"

        get_event_bus().publish(
            PurchaseOrdered.create(
                aggregate_id=po_id,
                company_id=company_id,
                po_number=po.po_number,
                supplier_id=str(po.supplier_id),
                total=str(Decimal(str(po.total))),
                currency_code=po.currency_code,
                actor_id=actor_id,
            )
        )

        logger.info("PurchaseOrder %s submitted by %s", po.po_number, actor_id)
        self.db.expire(po)
        return self._build_po_read(po)

    # ------------------------------------------------------------------
    # Approve  (called from router or approval engine callback)
    # ------------------------------------------------------------------

    def approve_po(
        self,
        po_id: UUID,
        company_id: UUID,
        actor_id: UUID,
        auto_approved: bool = False,
    ) -> PurchaseOrderRead:
        """Transition PENDING_APPROVAL → APPROVED."""
        po = self._get_or_404(po_id, company_id)
        _assert_transition(po_id, po.status, "APPROVED")

        self.po_repo.update_status(po_id, company_id, "APPROVED")
        po.status = "APPROVED"

        get_event_bus().publish(
            PurchaseOrderApproved.create(
                aggregate_id=po_id,
                company_id=company_id,
                po_number=po.po_number,
                supplier_id=str(po.supplier_id) if po.supplier_id else "",
                auto_approved=auto_approved,
                actor_id=actor_id,
            )
        )

        # T234 — purchase.po_email_supplier integration stub
        flag_svc = PurchaseFeatureFlagService(
            self.db, PurchaseFeatureFlagRepository(self.db)
        )
        if flag_svc.is_enabled(company_id, "purchase.po_email_supplier"):
            logger.info(
                "purchase.po_email_supplier: would send PO %s to supplier contact "
                "(stub — email provider not configured)",
                po.po_number,
            )

        logger.info("PurchaseOrder %s approved (auto=%s)", po.po_number, auto_approved)
        self.db.expire(po)
        return self._build_po_read(po)

    # ------------------------------------------------------------------
    # Reject  (PENDING_APPROVAL → REJECTED → back to DRAFT via resubmit)
    # ------------------------------------------------------------------

    def reject_po(
        self,
        po_id: UUID,
        company_id: UUID,
        actor_id: UUID,
        reason: str,
    ) -> PurchaseOrderRead:
        """Transition PENDING_APPROVAL → REJECTED."""
        if not reason or not reason.strip():
            raise ValueError("Rejection reason is required.")

        po = self._get_or_404(po_id, company_id)
        _assert_transition(po_id, po.status, "REJECTED")

        self.po_repo.update_status(po_id, company_id, "REJECTED")
        po.status = "REJECTED"

        get_event_bus().publish(
            PurchaseOrderRejected.create(
                aggregate_id=po_id,
                company_id=company_id,
                po_number=po.po_number,
                rejection_reason=reason,
                rejected_by=str(actor_id),
                actor_id=actor_id,
            )
        )

        logger.info("PurchaseOrder %s rejected by %s", po.po_number, actor_id)
        self.db.expire(po)
        return self._build_po_read(po)

    def revert_to_draft(
        self,
        po_id: UUID,
        company_id: UUID,
        actor_id: UUID,
    ) -> PurchaseOrderRead:
        """Transition REJECTED → DRAFT (revise and resubmit)."""
        po = self._get_or_404(po_id, company_id)
        _assert_transition(po_id, po.status, "DRAFT")
        self.po_repo.update_status(po_id, company_id, "DRAFT")
        po.status = "DRAFT"
        logger.info("PurchaseOrder %s reverted to DRAFT by %s", po.po_number, actor_id)
        self.db.expire(po)
        return self._build_po_read(po)

    # ------------------------------------------------------------------
    # Amend  (T127)
    # ------------------------------------------------------------------

    def amend_po(
        self,
        po_id: UUID,
        company_id: UUID,
        changes: dict,
        reason: str,
        actor_id: UUID,
    ) -> PurchaseOrderRead:
        """Create amendment record and reset PO to PENDING_APPROVAL.

        Only permitted when PO is APPROVED or above.
        The amendment records the before/after diff.
        PO status resets to PENDING_APPROVAL for re-approval.
        """
        po = self._get_or_404(po_id, company_id)
        if po.status not in ("APPROVED", "PARTIALLY_RECEIVED"):
            raise ConflictException(
                f"PurchaseOrder {po_id} must be APPROVED or PARTIALLY_RECEIVED to amend "
                f"(current: {po.status!r})."
            )

        # Build before/after diff
        before_state = {}
        after_state = {}
        for field_name, new_value in changes.items():
            before_state[field_name] = str(getattr(po, field_name, None))
            after_state[field_name] = str(new_value)
            setattr(po, field_name, new_value)

        # Create amendment record
        amendment_number = (
            self.amendment_repo.get_max_amendment_number(po_id, company_id) + 1
        )
        amendment = POAmendment(
            company_id=company_id,
            po_id=str(po_id),
            amendment_number=amendment_number,
            reason=reason,
            change_summary={"before": before_state, "after": after_state},
            requested_by=str(actor_id),
            status="PENDING",
            created_by=actor_id,
        )
        self.db.add(amendment)
        self.db.flush()

        # Reset PO to PENDING_APPROVAL
        self.po_repo.update_status(po_id, company_id, "PENDING_APPROVAL")
        po.status = "PENDING_APPROVAL"

        get_event_bus().publish(
            PurchaseOrderAmended.create(
                aggregate_id=po_id,
                company_id=company_id,
                po_number=po.po_number,
                amendment_number=amendment_number,
                reason=reason,
                actor_id=actor_id,
            )
        )

        logger.info(
            "PurchaseOrder %s amended (#%d) by %s",
            po.po_number,
            amendment_number,
            actor_id,
        )
        self.db.expire(po)
        return self._build_po_read(po)

    # ------------------------------------------------------------------
    # Cancel  (T128)
    # ------------------------------------------------------------------

    def cancel_po(
        self,
        po_id: UUID,
        company_id: UUID,
        actor_id: UUID,
        reason_code_id: UUID | None = None,
        reason: str | None = None,
        has_confirmed_gr: bool = False,
    ) -> PurchaseOrderRead:
        """Transition to CANCELLED.

        Args:
            has_confirmed_gr: caller should pass True if a confirmed GR exists
                              (this service does not query GRs directly to avoid
                              circular dependency with Phase 6 GRService).
        """
        if has_confirmed_gr:
            raise POCancelBlockedError(po_id)

        po = self._get_or_404(po_id, company_id)
        _assert_transition(po_id, po.status, "CANCELLED")

        if reason_code_id:
            po.reason_code_id = str(reason_code_id)
        self.po_repo.update_status(po_id, company_id, "CANCELLED")
        po.status = "CANCELLED"

        get_event_bus().publish(
            PurchaseOrderCancelled.create(
                aggregate_id=po_id,
                company_id=company_id,
                po_number=po.po_number,
                cancellation_reason=reason,
                actor_id=actor_id,
            )
        )

        logger.info("PurchaseOrder %s cancelled by %s", po.po_number, actor_id)
        self.db.expire(po)
        return self._build_po_read(po)

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def close_po(
        self,
        po_id: UUID,
        company_id: UUID,
        actor_id: UUID,
    ) -> PurchaseOrderRead:
        """Manually close a PO (APPROVED / PARTIALLY_RECEIVED / FULLY_RECEIVED → CLOSED)."""
        po = self._get_or_404(po_id, company_id)
        prior_status = po.status
        _assert_transition(po_id, po.status, "CLOSED")
        self.po_repo.update_status(po_id, company_id, "CLOSED")
        po.status = "CLOSED"

        get_event_bus().publish(
            PurchaseOrderClosed.create(
                aggregate_id=po_id,
                company_id=company_id,
                po_number=po.po_number,
                final_status_before_close=prior_status,
                actor_id=actor_id,
            )
        )

        logger.info("PurchaseOrder %s closed by %s", po.po_number, actor_id)
        self.db.expire(po)
        return self._build_po_read(po)

    # ------------------------------------------------------------------
    # Auto-update status on GR  (T129)
    # ------------------------------------------------------------------

    def auto_update_status_on_gr(
        self,
        po_id: UUID,
        company_id: UUID,
    ) -> str:
        """Called by GRService on GR confirmation.

        Evaluates total received vs ordered quantities and transitions PO to
        PARTIALLY_RECEIVED or FULLY_RECEIVED accordingly.

        Returns the new PO status.
        """
        po = self._get_or_404(po_id, company_id)

        if po.status not in ("APPROVED", "PARTIALLY_RECEIVED"):
            logger.warning(
                "auto_update_status_on_gr called on PO %s in unexpected status %s",
                po_id,
                po.status,
            )
            return po.status

        lines = self.line_repo.list_for_po(po_id, company_id)
        if not lines:
            return po.status

        all_fully_received = all(
            Decimal(str(ln.open_quantity)) <= Decimal("0.000") for ln in lines
        )

        if all_fully_received:
            self.po_repo.update_status(po_id, company_id, "FULLY_RECEIVED")
            new_status = "FULLY_RECEIVED"

            get_event_bus().publish(
                PurchaseOrderFullyReceived.create(
                    aggregate_id=po_id,
                    company_id=company_id,
                    po_number=po.po_number,
                    supplier_id=str(po.supplier_id) if po.supplier_id else "",
                )
            )
            logger.info("PurchaseOrder %s fully received", po.po_number)
        else:
            self.po_repo.update_status(po_id, company_id, "PARTIALLY_RECEIVED")
            new_status = "PARTIALLY_RECEIVED"
            logger.info("PurchaseOrder %s partially received", po.po_number)

        return new_status

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_po(self, po_id: UUID, company_id: UUID) -> PurchaseOrderRead:
        po = self._get_or_404(po_id, company_id)
        return self._build_po_read(po)

    def list_pos(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        statuses: list[str] | None = None,
        supplier_id: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PurchaseOrderListRead], int]:
        """Return a paginated list of POs."""
        items = self.po_repo.list_for_company(
            company_id,
            status=status,
            statuses=statuses,
            supplier_id=supplier_id,
            skip=skip,
            limit=limit,
        )
        total = self.po_repo.count_for_company(
            company_id,
            status=status,
            statuses=statuses,
            supplier_id=supplier_id,
        )
        reads = [PurchaseOrderListRead.model_validate(po) for po in items]
        return reads, total

    def get_overdue_pos(self, company_id: UUID) -> list[PurchaseOrderListRead]:
        """Return POs in APPROVED/PARTIALLY_RECEIVED with passed expected_delivery_date."""
        items = self.po_repo.get_overdue_pos(company_id)
        return [PurchaseOrderListRead.model_validate(po) for po in items]

"""Purchase Request application service — Phase 4.

Provides the complete PR lifecycle:
  create_pr        — create a new PR in DRAFT status with line items
  update_pr        — update PR metadata (DRAFT only)
  add_line         — add a line item to a DRAFT PR
  update_line      — update a line item on a DRAFT PR
  remove_line      — soft-delete a line item from a DRAFT PR
  submit_pr        — transition DRAFT → SUBMITTED; trigger approval routing
  approve_pr       — transition UNDER_REVIEW/SUBMITTED → APPROVED
  reject_pr        — transition UNDER_REVIEW/SUBMITTED → REJECTED
  cancel_pr        — transition DRAFT/SUBMITTED → CANCELLED
  convert_to_po    — transition APPROVED PR → DRAFT PurchaseOrder (stub)
  get_pr           — retrieve a single PR with lines
  list_prs         — list PRs with optional status/requestor filters

State Machine:
  DRAFT      → SUBMITTED    (submit_pr)
  SUBMITTED  → UNDER_REVIEW (approval engine moves it)
  SUBMITTED  → APPROVED     (auto-approved when no approval required)
  UNDER_REVIEW → APPROVED   (approve_pr, final approval level)
  UNDER_REVIEW → REJECTED   (reject_pr)
  DRAFT      → CANCELLED    (cancel_pr)
  SUBMITTED  → CANCELLED    (cancel_pr)

Business Rules (spec §25):
  - PR must have at least one non-deleted line before submission
  - Once APPROVED/REJECTED the PR may not be re-submitted
  - Once CANCELLED, status is terminal
  - total_estimated_cost is recalculated on every line add/update/remove
  - convert_to_po only allowed from APPROVED status

Spec ref: specs/006-purchase-management/spec.md §22 Business Workflows
Tasks: T101, T102, T103, T104
"""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import NotFoundException
from modules.purchase.events import get_event_bus
from modules.purchase.events.pr_events import (
    PurchaseRequestApproved,
    PurchaseRequestCancelled,
    PurchaseRequestConvertedToPO,
    PurchaseRequestCreated,
    PurchaseRequestRejected,
    PurchaseRequestSubmitted,
)
from modules.purchase.models.purchase_order import PurchaseOrder
from modules.purchase.models.purchase_request import PRLine, PurchaseRequest
from modules.purchase.repositories.purchase_request import (
    PRLineRepository,
    PurchaseRequestRepository,
)
from modules.purchase.schemas.purchase_request import (
    PRLineCreate,
    PRLineRead,
    PRLineUpdate,
    PurchaseRequestCreate,
    PurchaseRequestListRead,
    PurchaseRequestRead,
    PurchaseRequestUpdate,
)
from modules.purchase.services.sequence_service import PurchaseSequenceService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain exceptions  (T102)
# ---------------------------------------------------------------------------


class InvalidPRStatusTransitionError(Exception):
    """Raised when an illegal state machine transition is attempted."""

    def __init__(self, pr_id: UUID, current: str, target: str) -> None:
        super().__init__(
            f"Cannot transition PR {pr_id} from {current!r} to {target!r}."
        )


class PRMissingLinesError(Exception):
    """Raised when submit is called on a PR with no active lines."""

    def __init__(self, pr_id: UUID) -> None:
        super().__init__(
            f"Purchase Request {pr_id} must have at least one line before submission."
        )


class PRNotEditableError(Exception):
    """Raised when an edit is attempted on a PR that is not in DRAFT status."""

    def __init__(self, pr_id: UUID, status: str) -> None:
        super().__init__(
            f"Purchase Request {pr_id} is in status {status!r} and cannot be edited."
        )


class PRNotConvertibleError(Exception):
    """Raised when convert_to_po is called on a non-APPROVED PR."""

    def __init__(self, pr_id: UUID, status: str) -> None:
        super().__init__(
            f"Purchase Request {pr_id} must be APPROVED to convert to PO (current: {status!r})."
        )


# ---------------------------------------------------------------------------
# Allowed state machine transitions  (T101)
# ---------------------------------------------------------------------------

ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "DRAFT": ["SUBMITTED", "CANCELLED"],
    "SUBMITTED": ["UNDER_REVIEW", "APPROVED", "REJECTED", "CANCELLED"],
    "UNDER_REVIEW": ["APPROVED", "REJECTED"],
    "APPROVED": [],
    "REJECTED": [],
    "CANCELLED": [],
}


def _assert_transition(pr_id: UUID, current: str, target: str) -> None:
    """Validate that the transition current → target is permitted."""
    if target not in ALLOWED_TRANSITIONS.get(current, []):
        raise InvalidPRStatusTransitionError(pr_id, current, target)


# ---------------------------------------------------------------------------
# PRService
# ---------------------------------------------------------------------------


class PRService:
    """Application service for the PurchaseRequest aggregate."""

    def __init__(
        self,
        db: Session,
        pr_repo: PurchaseRequestRepository,
        line_repo: PRLineRepository,
        sequence_service: PurchaseSequenceService,
    ) -> None:
        self.db = db
        self.pr_repo = pr_repo
        self.line_repo = line_repo
        self.sequence_service = sequence_service

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_or_404(self, pr_id: UUID, company_id: UUID) -> PurchaseRequest:
        pr = self.pr_repo.get_by_id_or_none(pr_id, company_id)
        if pr is None:
            raise NotFoundException(f"PurchaseRequest {pr_id} not found.")
        return pr

    def _recalculate_total(self, pr_id: UUID, company_id: UUID) -> Decimal:
        """Sum estimated_line_total for all active lines and persist."""
        lines = self.line_repo.list_for_pr(pr_id, company_id)
        total = sum(
            (Decimal(str(ln.estimated_line_total)) for ln in lines),
            Decimal("0.00"),
        )
        self.pr_repo.update_total_cost(pr_id, company_id, total)
        return total

    def _build_pr_read(self, pr: PurchaseRequest) -> PurchaseRequestRead:
        """Build the full read schema including lines."""
        company_id = pr.company_id
        lines = self.line_repo.list_for_pr(pr.id, company_id)
        line_reads = [PRLineRead.model_validate(ln) for ln in lines]
        return PurchaseRequestRead(
            id=pr.id,
            company_id=pr.company_id,
            pr_number=pr.pr_number,
            title=pr.title,
            status=pr.status,
            requestor_id=str(pr.requestor_id),
            department=pr.department,
            required_by_date=pr.required_by_date,
            notes=pr.notes,
            total_estimated_cost=Decimal(str(pr.total_estimated_cost)),
            currency_code=pr.currency_code,
            converted_to_po_id=(
                str(pr.converted_to_po_id) if pr.converted_to_po_id else None
            ),
            branch_id=str(pr.branch_id) if pr.branch_id else None,
            lines=line_reads,
        )

    # ------------------------------------------------------------------
    # Create  (T101)
    # ------------------------------------------------------------------

    def create_pr(
        self,
        payload: PurchaseRequestCreate,
        company_id: UUID,
        requestor_id: UUID,
    ) -> PurchaseRequestRead:
        """Create a new PurchaseRequest in DRAFT status with optional lines."""
        pr_number = self.sequence_service.generate_next_number(company_id, "PR")

        pr = PurchaseRequest(
            company_id=company_id,
            pr_number=pr_number,
            title=payload.title,
            status="DRAFT",
            requestor_id=str(requestor_id),
            department=payload.department,
            required_by_date=payload.required_by_date,
            notes=payload.notes,
            total_estimated_cost=Decimal("0.00"),
            currency_code=payload.currency_code,
        )
        created = self.pr_repo.create(pr)
        self.db.flush()

        # Add lines if provided
        for idx, line_data in enumerate(payload.lines, start=1):
            self._create_line(created.id, company_id, idx, line_data)

        self._recalculate_total(created.id, company_id)

        get_event_bus().publish(
            PurchaseRequestCreated.create(
                aggregate_id=created.id,
                company_id=company_id,
                pr_number=pr_number,
                title=payload.title,
                requestor_id=str(requestor_id),
                department=payload.department,
                actor_id=requestor_id,
            )
        )

        logger.info("PurchaseRequest created: %s (%s)", pr_number, created.id)
        return self._build_pr_read(created)

    # ------------------------------------------------------------------
    # Update PR metadata  (T101)
    # ------------------------------------------------------------------

    def update_pr(
        self,
        pr_id: UUID,
        company_id: UUID,
        payload: PurchaseRequestUpdate,
    ) -> PurchaseRequestRead:
        """Update metadata on a DRAFT PR."""
        pr = self._get_or_404(pr_id, company_id)
        if pr.status != "DRAFT":
            raise PRNotEditableError(pr_id, pr.status)

        if payload.title is not None:
            pr.title = payload.title
        if payload.department is not None:
            pr.department = payload.department
        if payload.required_by_date is not None:
            pr.required_by_date = payload.required_by_date
        if payload.notes is not None:
            pr.notes = payload.notes
        if payload.currency_code is not None:
            pr.currency_code = payload.currency_code

        self.pr_repo.update(pr)
        return self._build_pr_read(pr)

    # ------------------------------------------------------------------
    # Line operations  (T101)
    # ------------------------------------------------------------------

    def _create_line(
        self,
        pr_id: UUID,
        company_id: UUID,
        line_number: int,
        data: PRLineCreate,
    ) -> PRLine:
        qty = Decimal(str(data.quantity))
        unit_cost = Decimal(str(data.estimated_unit_cost))
        line_total = (qty * unit_cost).quantize(Decimal("0.01"))

        line = PRLine(
            company_id=company_id,
            pr_id=str(pr_id),
            line_number=line_number,
            product_id=str(data.product_id) if data.product_id else None,
            product_description=data.product_description,
            quantity=qty,
            uom_id=str(data.uom_id) if data.uom_id else None,
            estimated_unit_cost=unit_cost,
            estimated_line_total=line_total,
            notes=data.notes,
        )
        return self.line_repo.create(line)

    def add_line(
        self,
        pr_id: UUID,
        company_id: UUID,
        data: PRLineCreate,
    ) -> PRLineRead:
        """Add a new line to a DRAFT PR."""
        pr = self._get_or_404(pr_id, company_id)
        if pr.status != "DRAFT":
            raise PRNotEditableError(pr_id, pr.status)

        next_number = self.line_repo.get_max_line_number(pr_id, company_id) + 1
        line = self._create_line(pr_id, company_id, next_number, data)
        self.db.flush()
        self._recalculate_total(pr_id, company_id)
        return PRLineRead.model_validate(line)

    def update_line(
        self,
        pr_id: UUID,
        line_id: UUID,
        company_id: UUID,
        data: PRLineUpdate,
    ) -> PRLineRead:
        """Update a line item on a DRAFT PR."""
        pr = self._get_or_404(pr_id, company_id)
        if pr.status != "DRAFT":
            raise PRNotEditableError(pr_id, pr.status)

        line = self.line_repo.get_by_id_or_none(line_id, company_id)
        if line is None or line.pr_id != str(pr_id):
            raise NotFoundException(f"PRLine {line_id} not found on PR {pr_id}.")

        if data.product_id is not None:
            line.product_id = str(data.product_id)
        if data.product_description is not None:
            line.product_description = data.product_description
        if data.uom_id is not None:
            line.uom_id = str(data.uom_id)
        if data.notes is not None:
            line.notes = data.notes

        qty = (
            Decimal(str(data.quantity))
            if data.quantity is not None
            else Decimal(str(line.quantity))
        )
        unit_cost = (
            Decimal(str(data.estimated_unit_cost))
            if data.estimated_unit_cost is not None
            else Decimal(str(line.estimated_unit_cost))
        )
        line.quantity = qty
        line.estimated_unit_cost = unit_cost
        line.estimated_line_total = (qty * unit_cost).quantize(Decimal("0.01"))

        self.line_repo.update(line)
        self._recalculate_total(pr_id, company_id)
        return PRLineRead.model_validate(line)

    def remove_line(
        self,
        pr_id: UUID,
        line_id: UUID,
        company_id: UUID,
    ) -> None:
        """Soft-delete a line from a DRAFT PR."""
        pr = self._get_or_404(pr_id, company_id)
        if pr.status != "DRAFT":
            raise PRNotEditableError(pr_id, pr.status)

        line = self.line_repo.get_by_id_or_none(line_id, company_id)
        if line is None or line.pr_id != str(pr_id):
            raise NotFoundException(f"PRLine {line_id} not found on PR {pr_id}.")

        self.line_repo.soft_delete(id=line_id, company_id=company_id)
        self._recalculate_total(pr_id, company_id)

    # ------------------------------------------------------------------
    # Submit  (T103)
    # ------------------------------------------------------------------

    def submit_pr(
        self,
        pr_id: UUID,
        company_id: UUID,
        actor_id: UUID,
    ) -> PurchaseRequestRead:
        """Submit a DRAFT PR for approval (DRAFT → SUBMITTED).

        Business rules:
          - PR must have at least one active line
          - Transitions to SUBMITTED; approval engine determines further routing
        """
        pr = self._get_or_404(pr_id, company_id)
        _assert_transition(pr_id, pr.status, "SUBMITTED")

        lines = self.line_repo.list_for_pr(pr_id, company_id)
        if not lines:
            raise PRMissingLinesError(pr_id)

        self.pr_repo.update_status(pr_id, company_id, "SUBMITTED")
        pr.status = "SUBMITTED"

        get_event_bus().publish(
            PurchaseRequestSubmitted.create(
                aggregate_id=pr_id,
                company_id=company_id,
                pr_number=pr.pr_number,
                requestor_id=str(pr.requestor_id),
                actor_id=actor_id,
            )
        )

        logger.info("PurchaseRequest %s submitted by %s", pr.pr_number, actor_id)
        return self._build_pr_read(pr)

    # ------------------------------------------------------------------
    # Approve / Reject  (T103)
    # ------------------------------------------------------------------

    def approve_pr(
        self,
        pr_id: UUID,
        company_id: UUID,
        actor_id: UUID,
        auto_approved: bool = False,
    ) -> PurchaseRequestRead:
        """Mark PR as APPROVED.

        Called by the approval engine after the final approval level is satisfied,
        or directly when auto-approval applies.
        """
        pr = self._get_or_404(pr_id, company_id)
        _assert_transition(pr_id, pr.status, "APPROVED")

        self.pr_repo.update_status(pr_id, company_id, "APPROVED")
        pr.status = "APPROVED"

        get_event_bus().publish(
            PurchaseRequestApproved.create(
                aggregate_id=pr_id,
                company_id=company_id,
                pr_number=pr.pr_number,
                auto_approved=auto_approved,
                actor_id=actor_id,
            )
        )

        logger.info(
            "PurchaseRequest %s approved (auto=%s)", pr.pr_number, auto_approved
        )
        return self._build_pr_read(pr)

    def reject_pr(
        self,
        pr_id: UUID,
        company_id: UUID,
        actor_id: UUID,
        reason: str,
    ) -> PurchaseRequestRead:
        """Reject a PR (SUBMITTED/UNDER_REVIEW → REJECTED)."""
        if not reason or not reason.strip():
            raise ValueError("Rejection reason is required.")

        pr = self._get_or_404(pr_id, company_id)
        _assert_transition(pr_id, pr.status, "REJECTED")

        self.pr_repo.update_status(pr_id, company_id, "REJECTED")
        pr.status = "REJECTED"

        get_event_bus().publish(
            PurchaseRequestRejected.create(
                aggregate_id=pr_id,
                company_id=company_id,
                pr_number=pr.pr_number,
                rejection_reason=reason,
                rejected_by=str(actor_id),
                actor_id=actor_id,
            )
        )

        logger.info("PurchaseRequest %s rejected by %s", pr.pr_number, actor_id)
        return self._build_pr_read(pr)

    def cancel_pr(
        self,
        pr_id: UUID,
        company_id: UUID,
        actor_id: UUID,
        reason: str | None = None,
    ) -> PurchaseRequestRead:
        """Cancel a DRAFT or SUBMITTED PR."""
        pr = self._get_or_404(pr_id, company_id)
        _assert_transition(pr_id, pr.status, "CANCELLED")

        self.pr_repo.update_status(pr_id, company_id, "CANCELLED")
        pr.status = "CANCELLED"

        get_event_bus().publish(
            PurchaseRequestCancelled.create(
                aggregate_id=pr_id,
                company_id=company_id,
                pr_number=pr.pr_number,
                cancellation_reason=reason,
                actor_id=actor_id,
            )
        )

        logger.info("PurchaseRequest %s cancelled by %s", pr.pr_number, actor_id)
        return self._build_pr_read(pr)

    # ------------------------------------------------------------------
    # Convert to PO  (T104)
    # ------------------------------------------------------------------

    def convert_to_po(
        self,
        pr_id: UUID,
        company_id: UUID,
        actor_id: UUID,
    ) -> PurchaseOrder:
        """Convert an APPROVED PR to a draft PurchaseOrder.

        Business rules:
          - PR must be in APPROVED status
          - A PO is created in DRAFT status with purchase_request_id set
          - PR.converted_to_po_id is set to the new PO's id
          - PurchaseRequestConvertedToPO event is published

        Returns the newly created PurchaseOrder stub.
        Phase 5 will expand PO with full supplier/terms fields.
        """
        pr = self._get_or_404(pr_id, company_id)
        if pr.status != "APPROVED":
            raise PRNotConvertibleError(pr_id, pr.status)

        po_number = self.sequence_service.generate_next_number(company_id, "PO")

        po = PurchaseOrder(
            company_id=company_id,
            po_number=po_number,
            status="DRAFT",
            purchase_request_id=str(pr_id),
            created_by=actor_id,
        )
        self.db.add(po)
        self.db.flush()

        self.pr_repo.set_converted_to_po(pr_id, company_id, po.id)
        pr.converted_to_po_id = str(po.id)

        get_event_bus().publish(
            PurchaseRequestConvertedToPO.create(
                aggregate_id=pr_id,
                company_id=company_id,
                pr_number=pr.pr_number,
                po_id=str(po.id),
                po_number=po_number,
                actor_id=actor_id,
            )
        )

        logger.info(
            "PurchaseRequest %s converted to PO %s by %s",
            pr.pr_number,
            po_number,
            actor_id,
        )
        return po

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_pr(self, pr_id: UUID, company_id: UUID) -> PurchaseRequestRead:
        """Retrieve a single PR with all its lines."""
        pr = self._get_or_404(pr_id, company_id)
        return self._build_pr_read(pr)

    def list_prs(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        requestor_id: UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PurchaseRequestListRead], int]:
        """Return a paginated list of PRs with optional filters.

        Returns (items, total_count).
        """
        items = self.pr_repo.list_for_company(
            company_id,
            status=status,
            requestor_id=requestor_id,
            skip=skip,
            limit=limit,
        )
        total = self.pr_repo.count_for_company(company_id, status=status)
        reads = [PurchaseRequestListRead.model_validate(pr) for pr in items]
        return reads, total

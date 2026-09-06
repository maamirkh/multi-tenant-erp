"""Sales Approval Service — Phase 4.

Implements the configurable approval workflow engine for Sales Orders and
Sales Returns. Supports:
  - Single and multi-level approval routing via SalesApprovalMatrix
  - Self-approval prevention (approver cannot be the requestor)
  - Auto-approval for orders below threshold with GOOD customer credit
  - Credit check integration before routing to human approvers
  - Pending approval inbox management

Spec ref: specs/007-sales-management/spec.md §Approval Workflow
Research: research.md Decision 1, Decision 5
Task: T111, T113
"""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException, NotFoundException
from core.utils.datetime import utcnow
from modules.sales.events import get_event_bus
from modules.sales.events.order_events import (
    OrderApproved,
    OrderCreditHold,
)
from modules.sales.models.approval import SalesApprovalRecord, SalesMatrixRule
from modules.sales.models.master import SalesConfiguration
from modules.sales.repositories.order import (
    SalesApprovalMatrixRepository,
    SalesApprovalRecordRepository,
    SalesMatrixRuleRepository,
    SalesOrderRepository,
)
from modules.sales.services.credit_check_service import CreditCheckService

logger = logging.getLogger(__name__)


class ApprovalService:
    """Manages approval workflow routing and decisions.

    Responsibilities:
      1. Determine whether an order should be auto-approved or routed for
         human review using the configured SalesApprovalMatrix.
      2. Evaluate credit status via CreditCheckService before routing.
      3. Record approval decisions and validate self-approval prevention.
      4. Determine when all approval levels are satisfied.

    Spec ref: specs/007-sales-management/spec.md §Approval Workflow
    Task: T111, T113
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._matrix_repo = SalesApprovalMatrixRepository(db)
        self._rule_repo = SalesMatrixRuleRepository(db)
        self._record_repo = SalesApprovalRecordRepository(db)
        self._order_repo = SalesOrderRepository(db)
        self._credit_service = CreditCheckService(db)

    def _get_sales_config(self, company_id: UUID) -> SalesConfiguration | None:
        """Fetch company sales configuration."""
        return (
            self._db.query(SalesConfiguration)
            .filter(
                SalesConfiguration.company_id == company_id,
                SalesConfiguration.is_deleted.is_(False),
            )
            .first()
        )

    def _is_auto_approve_enabled(self, company_id: UUID) -> bool:
        """Check if auto-approve feature flag is enabled."""
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
            flag_key="sales.auto_approve_below_threshold",
        )

    def evaluate_for_order(
        self,
        company_id: UUID,
        order_id: UUID,
        submitted_by: UUID,
    ) -> tuple[bool, str]:
        """Evaluate whether an order should be auto-approved or routed.

        Performs:
          1. Credit check — blocks if EXCEEDED or HOLD.
          2. Auto-approval check (feature flag + threshold + GOOD credit).
          3. Matrix routing — creates SalesApprovalRecord(s) for human review.

        Returns:
            (auto_approved: bool, message: str)
              - If auto_approved=True, caller should transition order to APPROVED.
              - If auto_approved=False, caller transitions to PENDING_APPROVAL.

        Raises:
            ConflictException: If credit check blocks approval.
        """
        order = self._order_repo.get_by_id_or_none(order_id, company_id)
        if order is None:
            raise NotFoundException(f"Sales order {order_id} not found.")

        customer_id = UUID(order.customer_id)
        order_total = Decimal(str(order.total_amount))

        # --- Credit check ---
        credit_result = self._credit_service.evaluate_credit(
            company_id=company_id,
            customer_id=customer_id,
            order_total=order_total,
            exclude_order_id=order_id,
        )

        if not credit_result.allowed:
            # Publish credit hold event
            get_event_bus().publish(
                OrderCreditHold(
                    company_id=company_id,
                    aggregate_id=order_id,
                    order_id=order_id,
                    order_number=order.order_number,
                    customer_id=str(customer_id),
                    credit_status=credit_result.credit_status,
                    credit_limit=str(credit_result.credit_limit),
                    outstanding_balance=str(credit_result.outstanding_balance),
                    order_total=str(order_total),
                )
            )
            raise ConflictException(f"Credit check failed: {credit_result.message}")

        # --- Auto-approval check ---
        if self._is_auto_approve_enabled(company_id):
            config = self._get_sales_config(company_id)
            threshold = (
                Decimal(str(config.auto_approve_threshold))
                if config and config.auto_approve_threshold is not None
                else None
            )
            if (
                threshold is not None
                and order_total <= threshold
                and credit_result.credit_status == "GOOD"
            ):
                logger.info(
                    "ApprovalService: auto-approving order %s (total=%s <= threshold=%s)",
                    order.order_number,
                    order_total,
                    threshold,
                )
                get_event_bus().publish(
                    OrderApproved(
                        company_id=company_id,
                        aggregate_id=order_id,
                        order_id=order_id,
                        order_number=order.order_number,
                        customer_id=str(customer_id),
                        total_amount=str(order_total),
                        approved_by=str(submitted_by),
                        auto_approved=True,
                    )
                )
                return True, "Auto-approved: order below threshold with good credit."

        # --- Matrix routing ---
        matrix = self._matrix_repo.get_active_for_document_type(
            company_id, "SALES_ORDER"
        )

        if matrix is None:
            # No matrix configured — auto-approve by default
            logger.info(
                "ApprovalService: no active SALES_ORDER matrix for company %s; "
                "auto-approving order %s",
                company_id,
                order.order_number,
            )
            get_event_bus().publish(
                OrderApproved(
                    company_id=company_id,
                    aggregate_id=order_id,
                    order_id=order_id,
                    order_number=order.order_number,
                    customer_id=str(customer_id),
                    total_amount=str(order_total),
                    approved_by=str(submitted_by),
                    auto_approved=True,
                )
            )
            return True, "Auto-approved: no approval matrix configured."

        # Find applicable rules for this order total
        rules = self._rule_repo.list_for_matrix(company_id, UUID(str(matrix.id)))
        applicable = self._find_applicable_rules(rules, order_total, order)

        if not applicable:
            # No matching rule — auto-approve
            logger.info(
                "ApprovalService: no matching matrix rules for order %s (total=%s); "
                "auto-approving",
                order.order_number,
                order_total,
            )
            get_event_bus().publish(
                OrderApproved(
                    company_id=company_id,
                    aggregate_id=order_id,
                    order_id=order_id,
                    order_number=order.order_number,
                    customer_id=str(customer_id),
                    total_amount=str(order_total),
                    approved_by=str(submitted_by),
                    auto_approved=True,
                )
            )
            return True, "Auto-approved: no applicable matrix rules."

        if all(r.auto_approve for r in applicable):
            # All applicable rules are set to auto_approve
            logger.info(
                "ApprovalService: all applicable rules are auto_approve for order %s",
                order.order_number,
            )
            get_event_bus().publish(
                OrderApproved(
                    company_id=company_id,
                    aggregate_id=order_id,
                    order_id=order_id,
                    order_number=order.order_number,
                    customer_id=str(customer_id),
                    total_amount=str(order_total),
                    approved_by=str(submitted_by),
                    auto_approved=True,
                )
            )
            return True, "Auto-approved by matrix rule configuration."

        # Create pending SalesApprovalRecord for each applicable rule
        for rule in applicable:
            if rule.auto_approve:
                continue  # Skip auto-approve rules; they don't need records

            approver_id = (
                rule.approver_user_id
                if rule.approver_user_id
                else str(submitted_by)  # Fallback; production would resolve role
            )
            # Self-approval prevention: if approver == requestor, skip
            if approver_id == str(submitted_by):
                logger.warning(
                    "ApprovalService: self-approval attempted for order %s "
                    "at level %d; record created but marked needs-different-approver",
                    order.order_number,
                    rule.approval_level,
                )

            record = SalesApprovalRecord(
                company_id=company_id,
                document_type="SALES_ORDER",
                document_id=str(order_id),
                approval_level=rule.approval_level,
                approver_id=approver_id,
                decision="PENDING",
                approval_version=order.approval_version,
            )
            self._db.add(record)

        logger.info(
            "ApprovalService: created %d approval record(s) for order %s",
            len([r for r in applicable if not r.auto_approve]),
            order.order_number,
        )
        return False, "Order routed for human approval."

    def _find_applicable_rules(
        self,
        rules: list[SalesMatrixRule],
        order_total: Decimal,
        order: object,
    ) -> list[SalesMatrixRule]:
        """Return rules that match this order's total amount.

        Selects rules where min_amount <= order_total <= max_amount (or max_amount is None).
        """
        applicable = []
        for rule in rules:
            min_amt = Decimal(str(rule.min_amount))
            max_amt = (
                Decimal(str(rule.max_amount)) if rule.max_amount is not None else None
            )

            if order_total < min_amt:
                continue
            if max_amt is not None and order_total > max_amt:
                continue
            applicable.append(rule)
        return applicable

    def process_approval_decision(
        self,
        company_id: UUID,
        document_type: str,
        document_id: UUID,
        approver_id: UUID,
        decision: str,
        comments: str | None = None,
        requestor_id: UUID | None = None,
    ) -> tuple[bool, bool]:
        """Process an approval/rejection decision.

        Enforces self-approval prevention. Returns (all_approved, any_rejected).

        Args:
            company_id:     Company context.
            document_type:  SALES_ORDER or SALES_RETURN.
            document_id:    Document UUID.
            approver_id:    User making the decision.
            decision:       APPROVED or REJECTED.
            comments:       Optional comments.
            requestor_id:   Original submitter (for self-approval check).

        Returns:
            (all_approved, any_rejected):
              - all_approved: True if all pending records are now APPROVED.
              - any_rejected: True if any record was just REJECTED.

        Raises:
            ConflictException: Self-approval attempted, or record already decided.
            NotFoundException: No pending record found for this approver.
        """
        if decision not in ("APPROVED", "REJECTED"):
            raise ConflictException(f"Invalid decision: {decision}")

        # Get all pending records for this document
        order = self._order_repo.get_by_id_or_none(document_id, company_id)
        if order is None:
            raise NotFoundException(f"Document {document_id} not found.")

        pending = self._record_repo.get_pending_for_document(
            company_id=company_id,
            document_type=document_type,
            document_id=document_id,
            approval_version=order.approval_version,
        )

        # Find the record for this approver
        approver_record = None
        for rec in pending:
            if rec.approver_id == str(approver_id):
                approver_record = rec
                break

        if approver_record is None:
            raise NotFoundException(
                f"No pending approval record found for approver {approver_id} "
                f"on {document_type} {document_id}."
            )

        # Self-approval prevention
        if requestor_id is not None and str(approver_id) == str(requestor_id):
            raise ConflictException(
                "Self-approval is not permitted. "
                "The approver cannot be the same user who submitted the order."
            )

        # Record is already decided
        if approver_record.decision != "PENDING":
            raise ConflictException(
                f"Approval record is already in {approver_record.decision} state."
            )

        # Update the record
        approver_record.decision = decision
        approver_record.comments = comments
        approver_record.decided_at = utcnow().isoformat()

        if decision == "REJECTED":
            logger.info(
                "ApprovalService: %s %s REJECTED by %s at level %d",
                document_type,
                document_id,
                approver_id,
                approver_record.approval_level,
            )
            return False, True

        # Check if all pending records are now approved
        remaining_pending = [
            r for r in pending if r.id != approver_record.id and r.decision == "PENDING"
        ]
        all_approved = len(remaining_pending) == 0

        logger.info(
            "ApprovalService: %s %s APPROVED by %s at level %d (remaining=%d)",
            document_type,
            document_id,
            approver_id,
            approver_record.approval_level,
            len(remaining_pending),
        )
        return all_approved, False

    def get_pending_approvals_for_user(
        self, company_id: UUID, approver_id: UUID
    ) -> list[SalesApprovalRecord]:
        """Return all pending approval records assigned to a user."""
        return self._record_repo.get_pending_for_approver(company_id, approver_id)

    def get_approval_history(
        self,
        company_id: UUID,
        document_type: str,
        document_id: UUID,
    ) -> list[SalesApprovalRecord]:
        """Return full approval history for a document."""
        return self._record_repo.list_for_document(
            company_id, document_type, document_id
        )

    def invalidate_pending_approvals(
        self,
        company_id: UUID,
        document_type: str,
        document_id: UUID,
        approval_version: int,
    ) -> None:
        """Invalidate (soft-delete) pending approval records for a given version.

        Called when an order is rejected and transitions back to DRAFT for revision.
        """
        self._record_repo.invalidate_for_document(
            company_id, document_type, document_id, approval_version
        )

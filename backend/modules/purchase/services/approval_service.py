"""Approval Engine application service — Phase 3.

Provides the complete approval workflow engine:

  route_for_approval   — find the applicable rule, return required levels
                         (auto-approves when policy flags are OFF)
  approve              — record an APPROVED action for a level
  reject               — record a REJECTED action (comment mandatory)
  emergency_bypass     — Purchase Manager bypasses all pending levels
  resolve_approver     — return effective approver_id honouring delegation
  check_stale_approvals — return documents where a level is past escalation_days

Business rules (from spec §25):
  - Self-approval prevention: approver_id must differ from requestor_id
  - Rejection requires a non-empty comment
  - Emergency bypass requires justification (Purchase Manager only, enforced at API layer)
  - ApprovalRecord is immutable: once written it cannot be changed or deleted
  - Auto-approve when the relevant feature flag (pr_approval_required /
    po_approval_required) is False on the company PurchasePolicy
  - Delegation: if a delegator has an active ApprovalDelegate covering the
    document_type, the delegate acts on their behalf

Spec ref: specs/006-purchase-management/spec.md §22 Business Workflows
Tasks: T079-T085
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import NotFoundException
from core.utils.datetime import utcnow
from modules.purchase.models.approval import (
    ApprovalDelegate,
    ApprovalLevel,
    ApprovalMatrix,
    ApprovalRecord,
    MatrixRule,
)
from modules.purchase.repositories.approval import (
    ApprovalDelegateRepository,
    ApprovalLevelRepository,
    ApprovalMatrixRepository,
    ApprovalRecordRepository,
    MatrixRuleRepository,
)
from modules.purchase.repositories.master import PurchasePolicyRepository
from modules.purchase.schemas.approval import (
    ApprovalLevelRead,
    ApprovalStatusRead,
    RouteForApprovalResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


class SelfApprovalError(Exception):
    """Raised when an approver attempts to approve their own document."""

    def __init__(self, approver_id: UUID, requestor_id: UUID) -> None:
        super().__init__(
            f"Self-approval forbidden: approver {approver_id} == requestor {requestor_id}."
        )


class AlreadyActionedError(Exception):
    """Raised when an approval action is taken on an already actioned level."""

    def __init__(self, document_type: str, document_id: UUID, level: int) -> None:
        super().__init__(
            f"Level {level} of {document_type} {document_id} has already been actioned."
        )


class ApprovalEngineDisabledError(Exception):
    """Raised when attempting an approval action when the engine is disabled by policy."""

    def __init__(self, document_type: str) -> None:
        super().__init__(
            f"Approval engine is disabled for {document_type} by company policy."
        )


# ---------------------------------------------------------------------------
# ApprovalService
# ---------------------------------------------------------------------------


class ApprovalService:
    """Application service implementing the complete approval engine.

    Args:
        db:              SQLAlchemy session.
        matrix_repo:     ApprovalMatrixRepository (injected).
        rule_repo:       MatrixRuleRepository (injected).
        level_repo:      ApprovalLevelRepository (injected).
        record_repo:     ApprovalRecordRepository (injected).
        delegate_repo:   ApprovalDelegateRepository (injected).
        policy_repo:     PurchasePolicyRepository (injected).
    """

    def __init__(
        self,
        db: Session,
        matrix_repo: ApprovalMatrixRepository,
        rule_repo: MatrixRuleRepository,
        level_repo: ApprovalLevelRepository,
        record_repo: ApprovalRecordRepository,
        delegate_repo: ApprovalDelegateRepository,
        policy_repo: PurchasePolicyRepository,
    ) -> None:
        self.db = db
        self._matrix_repo = matrix_repo
        self._rule_repo = rule_repo
        self._level_repo = level_repo
        self._record_repo = record_repo
        self._delegate_repo = delegate_repo
        self._policy_repo = policy_repo

    # ------------------------------------------------------------------
    # T079 — route_for_approval
    # ------------------------------------------------------------------

    def route_for_approval(
        self,
        document_type: str,
        document_id: UUID,
        company_id: UUID,
        *,
        amount: Decimal | None = None,
        category_id: UUID | None = None,
        department: str | None = None,
        requestor_id: UUID | None = None,
    ) -> RouteForApprovalResult:
        """Determine the approval path for a document.

        Checks the company PurchasePolicy to see if approval is required.
        If disabled, returns auto_approved=True.

        Otherwise:
          1. Find the active ApprovalMatrix for the document_type.
          2. Iterate its rules to find the first matching one.
          3. Return the required ApprovalLevel list for that rule.

        If no matrix or no matching rule exists, the document is
        auto-approved (no matrix configured = no approval required).

        Returns:
            RouteForApprovalResult schema.
        """
        # Check feature flag: is approval required for this document type?
        if not self._is_approval_required(
            company_id=company_id, document_type=document_type
        ):
            logger.info(
                "route_for_approval: approval disabled by policy for %s company=%s",
                document_type,
                company_id,
            )
            return RouteForApprovalResult(
                document_type=document_type,
                document_id=str(document_id),
                auto_approved=True,
                matrix_found=False,
                applicable_rule_id=None,
                required_levels=[],
                message="Auto-approved: approval not required by company policy.",
            )

        # Find the active matrix
        matrix = self._matrix_repo.get_active_for_document_type(
            company_id=company_id, document_type=document_type
        )
        if matrix is None:
            logger.info(
                "route_for_approval: no active matrix for %s company=%s — auto-approving",
                document_type,
                company_id,
            )
            return RouteForApprovalResult(
                document_type=document_type,
                document_id=str(document_id),
                auto_approved=True,
                matrix_found=False,
                applicable_rule_id=None,
                required_levels=[],
                message="Auto-approved: no active approval matrix configured.",
            )

        # Find the first matching rule
        rules = self._rule_repo.list_for_matrix(
            company_id=company_id, matrix_id=matrix.id
        )
        matched_rule: MatrixRule | None = None
        for rule in rules:
            if self._rule_matches(
                rule, amount=amount, category_id=category_id, department=department
            ):
                matched_rule = rule
                break

        if matched_rule is None:
            logger.info(
                "route_for_approval: no matching rule for %s id=%s company=%s — auto-approving",
                document_type,
                document_id,
                company_id,
            )
            return RouteForApprovalResult(
                document_type=document_type,
                document_id=str(document_id),
                auto_approved=True,
                matrix_found=True,
                applicable_rule_id=None,
                required_levels=[],
                message="Auto-approved: no matching rule found in the approval matrix.",
            )

        # Retrieve the required levels for the matched rule
        levels = self._level_repo.list_for_rule(
            company_id=company_id, rule_id=matched_rule.id
        )

        if not levels:
            logger.info(
                "route_for_approval: matched rule %s has no levels for %s id=%s — auto-approving",
                matched_rule.id,
                document_type,
                document_id,
            )
            return RouteForApprovalResult(
                document_type=document_type,
                document_id=str(document_id),
                auto_approved=True,
                matrix_found=True,
                applicable_rule_id=str(matched_rule.id),
                required_levels=[],
                message="Auto-approved: matching rule has no approval levels configured.",
            )

        level_reads = [self._level_to_read(lv) for lv in levels]

        logger.info(
            "route_for_approval: %s id=%s requires %d approval level(s) via rule=%s",
            document_type,
            document_id,
            len(levels),
            matched_rule.id,
        )
        return RouteForApprovalResult(
            document_type=document_type,
            document_id=str(document_id),
            auto_approved=False,
            matrix_found=True,
            applicable_rule_id=str(matched_rule.id),
            required_levels=level_reads,
            message=f"Approval required: {len(levels)} level(s) via rule '{matched_rule.id}'.",
        )

    # ------------------------------------------------------------------
    # T080 — approve
    # ------------------------------------------------------------------

    def approve(
        self,
        document_type: str,
        document_id: UUID,
        approver_id: UUID,
        company_id: UUID,
        level_number: int,
        *,
        comment: str | None = None,
        requestor_id: UUID | None = None,
    ) -> ApprovalRecord:
        """Record an APPROVED action for a document level.

        Raises:
            SelfApprovalError:    If approver_id == requestor_id.
            AlreadyActionedError: If this level already has an APPROVED record.
        """
        # Self-approval check
        if requestor_id is not None and approver_id == requestor_id:
            raise SelfApprovalError(approver_id=approver_id, requestor_id=requestor_id)

        # Resolve effective approver (delegation)
        effective_approver_id = self.resolve_approver(
            approver_id=approver_id,
            company_id=company_id,
            document_type=document_type,
        )

        # Check if already approved at this level
        existing = self._record_repo.get_for_document_level(
            company_id=company_id,
            document_type=document_type,
            document_id=document_id,
            level_number=level_number,
        )
        already_approved = any(r.action == "APPROVED" for r in existing)
        if already_approved:
            raise AlreadyActionedError(
                document_type=document_type,
                document_id=document_id,
                level=level_number,
            )

        record = ApprovalRecord(
            company_id=company_id,
            created_by=effective_approver_id,
            document_type=document_type,
            document_id=str(document_id),
            level_number=level_number,
            approver_id=str(effective_approver_id),
            action="APPROVED",
            comment=comment,
            is_emergency_bypass=False,
            bypass_justification=None,
            actioned_at=utcnow(),
        )
        result = self._record_repo.create(record)
        logger.info(
            "approve: %s %s level=%d by approver=%s",
            document_type,
            document_id,
            level_number,
            effective_approver_id,
        )
        return result

    # ------------------------------------------------------------------
    # T081 — reject
    # ------------------------------------------------------------------

    def reject(
        self,
        document_type: str,
        document_id: UUID,
        approver_id: UUID,
        company_id: UUID,
        level_number: int,
        comment: str,
    ) -> ApprovalRecord:
        """Record a REJECTED action for a document level.

        Comment is mandatory for rejections (enforced here and at API layer).
        """
        if not comment or not comment.strip():
            raise ValueError("A rejection comment is mandatory.")

        effective_approver_id = self.resolve_approver(
            approver_id=approver_id,
            company_id=company_id,
            document_type=document_type,
        )

        record = ApprovalRecord(
            company_id=company_id,
            created_by=effective_approver_id,
            document_type=document_type,
            document_id=str(document_id),
            level_number=level_number,
            approver_id=str(effective_approver_id),
            action="REJECTED",
            comment=comment,
            is_emergency_bypass=False,
            bypass_justification=None,
            actioned_at=utcnow(),
        )
        result = self._record_repo.create(record)
        logger.info(
            "reject: %s %s level=%d by approver=%s",
            document_type,
            document_id,
            level_number,
            effective_approver_id,
        )
        return result

    # ------------------------------------------------------------------
    # T082 — emergency_bypass
    # ------------------------------------------------------------------

    def emergency_bypass(
        self,
        document_type: str,
        document_id: UUID,
        bypasser_id: UUID,
        company_id: UUID,
        justification: str,
    ) -> ApprovalRecord:
        """Record an emergency bypass — bypasses all pending approval levels.

        Authorization (Purchase Manager role) is enforced at the API layer.
        This method records a single bypass record covering the document.
        """
        if not justification or not justification.strip():
            raise ValueError("A bypass justification is mandatory.")

        record = ApprovalRecord(
            company_id=company_id,
            created_by=bypasser_id,
            document_type=document_type,
            document_id=str(document_id),
            level_number=1,  # bypass record uses level 1; is_emergency_bypass=True is the signal
            approver_id=str(bypasser_id),
            action="APPROVED",
            comment=None,
            is_emergency_bypass=True,
            bypass_justification=justification,
            actioned_at=utcnow(),
        )
        result = self._record_repo.create(record)
        logger.warning(
            "emergency_bypass: %s %s by bypasser=%s",
            document_type,
            document_id,
            bypasser_id,
        )
        return result

    # ------------------------------------------------------------------
    # T083 — get_approval_status
    # ------------------------------------------------------------------

    def get_approval_status(
        self,
        document_type: str,
        document_id: UUID,
        company_id: UUID,
    ) -> ApprovalStatusRead:
        """Return the current approval status for a document."""
        from modules.purchase.schemas.approval import ApprovalRecordRead

        records = self._record_repo.list_for_document(
            company_id=company_id,
            document_type=document_type,
            document_id=document_id,
        )

        # Emergency bypass = fully approved
        has_bypass = any(r.is_emergency_bypass for r in records)
        is_approved = has_bypass or any(
            r.action == "APPROVED" and r.level_number > 0 for r in records
        )
        is_rejected = any(r.action == "REJECTED" for r in records)

        # Derive current level from the highest APPROVED level_number
        approved_levels = [
            r.level_number
            for r in records
            if r.action == "APPROVED" and r.level_number > 0
        ]
        current_level = max(approved_levels) if approved_levels else 0

        record_reads = [
            ApprovalRecordRead(
                id=r.id,
                company_id=r.company_id,
                document_type=r.document_type,
                document_id=r.document_id,
                level_number=r.level_number,
                approver_id=r.approver_id,
                action=r.action,
                comment=r.comment,
                is_emergency_bypass=r.is_emergency_bypass,
                bypass_justification=r.bypass_justification,
                actioned_at=r.actioned_at,
                created_at=r.created_at,
            )
            for r in records
        ]

        return ApprovalStatusRead(
            document_type=document_type,
            document_id=str(document_id),
            is_approved=is_approved,
            is_rejected=is_rejected,
            current_level=current_level,
            records=record_reads,
        )

    # ------------------------------------------------------------------
    # T084 — resolve_approver (delegation check)
    # ------------------------------------------------------------------

    def resolve_approver(
        self,
        approver_id: UUID,
        company_id: UUID,
        document_type: str | None = None,
    ) -> UUID:
        """Return the effective approver_id, honouring any active delegation.

        If the approver has an active ApprovalDelegate for this document_type
        (or a universal delegation), the delegate_id is returned instead.
        """
        delegation = self._delegate_repo.get_active_delegation(
            company_id=company_id,
            delegator_id=approver_id,
            document_type=document_type,
            as_of=utcnow(),
        )
        if delegation is not None:
            logger.debug(
                "resolve_approver: %s delegated to %s for %s",
                approver_id,
                delegation.delegate_id,
                document_type,
            )
            return UUID(delegation.delegate_id)
        return approver_id

    # ------------------------------------------------------------------
    # T085 — check_stale_approvals
    # ------------------------------------------------------------------

    def check_stale_approvals(
        self,
        company_id: UUID,
        document_type: str,
        document_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return levels that are pending beyond their escalation_days threshold.

        Returns a list of dicts with keys: level_number, approver_type,
        approver_role, approver_user_id, days_overdue.

        This method is informational; escalation notifications are sent by a
        background job that calls this method.
        """

        route = self.route_for_approval(
            document_type=document_type,
            document_id=document_id,
            company_id=company_id,
        )

        if route.auto_approved or not route.required_levels:
            return []

        # Get actioned level numbers
        records = self._record_repo.list_for_document(
            company_id=company_id,
            document_type=document_type,
            document_id=document_id,
        )
        actioned_levels = {r.level_number for r in records}

        stale = []
        now = utcnow()
        for level_read in route.required_levels:
            if level_read.level_number in actioned_levels:
                continue
            # Check based on any existing records for earlier levels
            level_records = [
                r for r in records if r.level_number == level_read.level_number - 1
            ]
            if level_records:
                last_action = max(r.actioned_at for r in level_records)
            else:
                # No previous level actioned; use the earliest approval record or skip
                continue

            days_pending = (now - last_action).days
            if days_pending > level_read.escalation_days:
                stale.append(
                    {
                        "level_number": level_read.level_number,
                        "approver_type": level_read.approver_type,
                        "approver_role": level_read.approver_role,
                        "approver_user_id": level_read.approver_user_id,
                        "days_overdue": days_pending - level_read.escalation_days,
                    }
                )
        return stale

    # ------------------------------------------------------------------
    # Matrix management helpers
    # ------------------------------------------------------------------

    def create_matrix(
        self,
        company_id: UUID,
        actor_id: UUID | None,
        document_type: str,
        name: str,
        is_active: bool = True,
    ) -> ApprovalMatrix:
        """Create a new approval matrix."""
        matrix = ApprovalMatrix(
            company_id=company_id,
            created_by=actor_id,
            document_type=document_type,
            name=name,
            is_active=is_active,
        )
        return self._matrix_repo.create(matrix)

    def update_matrix(
        self,
        matrix_id: UUID,
        company_id: UUID,
        *,
        name: str | None = None,
        is_active: bool | None = None,
    ) -> ApprovalMatrix:
        """Update an approval matrix."""
        matrix = self._matrix_repo.get_by_id_or_none(
            id=matrix_id, company_id=company_id
        )
        if matrix is None or matrix.is_deleted:
            raise NotFoundException(f"ApprovalMatrix {matrix_id} not found.")
        if name is not None:
            matrix.name = name
        if is_active is not None:
            matrix.is_active = is_active
        return self._matrix_repo.update(matrix)

    def delete_matrix(self, matrix_id: UUID, company_id: UUID) -> None:
        """Soft-delete an approval matrix."""
        matrix = self._matrix_repo.get_by_id_or_none(
            id=matrix_id, company_id=company_id
        )
        if matrix is None:
            raise NotFoundException(f"ApprovalMatrix {matrix_id} not found.")
        self._matrix_repo.soft_delete(id=matrix_id, company_id=company_id)

    def list_matrices(self, company_id: UUID) -> list[ApprovalMatrix]:
        return self._matrix_repo.list_for_company(company_id=company_id)

    def get_matrix(self, matrix_id: UUID, company_id: UUID) -> ApprovalMatrix:
        matrix = self._matrix_repo.get_by_id_or_none(
            id=matrix_id, company_id=company_id
        )
        if matrix is None or matrix.is_deleted:
            raise NotFoundException(f"ApprovalMatrix {matrix_id} not found.")
        return matrix

    # ------------------------------------------------------------------
    # Rule management helpers
    # ------------------------------------------------------------------

    def create_rule(
        self,
        matrix_id: UUID,
        company_id: UUID,
        actor_id: UUID | None,
        condition_type: str,
        approval_level: int = 1,
        approval_mode: str = "SEQUENTIAL",
        *,
        min_amount: Decimal | None = None,
        max_amount: Decimal | None = None,
        category_id: UUID | None = None,
        department: str | None = None,
    ) -> MatrixRule:
        rule = MatrixRule(
            company_id=company_id,
            created_by=actor_id,
            matrix_id=str(matrix_id),
            condition_type=condition_type,
            min_amount=min_amount,
            max_amount=max_amount,
            category_id=str(category_id) if category_id else None,
            department=department,
            approval_level=approval_level,
            approval_mode=approval_mode,
        )
        return self._rule_repo.create(rule)

    def update_rule(
        self,
        rule_id: UUID,
        company_id: UUID,
        **kwargs: Any,
    ) -> MatrixRule:
        rule = self._rule_repo.get_by_id_or_none(id=rule_id, company_id=company_id)
        if rule is None or rule.is_deleted:
            raise NotFoundException(f"MatrixRule {rule_id} not found.")
        for k, v in kwargs.items():
            if v is not None and hasattr(rule, k):
                setattr(rule, k, v)
        return self._rule_repo.update(rule)

    def delete_rule(self, rule_id: UUID, company_id: UUID) -> None:
        rule = self._rule_repo.get_by_id_or_none(id=rule_id, company_id=company_id)
        if rule is None:
            raise NotFoundException(f"MatrixRule {rule_id} not found.")
        self._rule_repo.soft_delete(id=rule_id, company_id=company_id)

    def list_rules(self, matrix_id: UUID, company_id: UUID) -> list[MatrixRule]:
        return self._rule_repo.list_for_matrix(
            company_id=company_id, matrix_id=matrix_id
        )

    # ------------------------------------------------------------------
    # Level management helpers
    # ------------------------------------------------------------------

    def create_level(
        self,
        rule_id: UUID,
        company_id: UUID,
        actor_id: UUID | None,
        level_number: int,
        approver_type: str,
        escalation_days: int = 3,
        *,
        approver_role: str | None = None,
        approver_user_id: UUID | None = None,
    ) -> ApprovalLevel:
        level = ApprovalLevel(
            company_id=company_id,
            created_by=actor_id,
            rule_id=str(rule_id),
            level_number=level_number,
            approver_type=approver_type,
            approver_role=approver_role,
            approver_user_id=str(approver_user_id) if approver_user_id else None,
            escalation_days=escalation_days,
        )
        return self._level_repo.create(level)

    def update_level(
        self, level_id: UUID, company_id: UUID, **kwargs: Any
    ) -> ApprovalLevel:
        level = self._level_repo.get_by_id_or_none(id=level_id, company_id=company_id)
        if level is None or level.is_deleted:
            raise NotFoundException(f"ApprovalLevel {level_id} not found.")
        for k, v in kwargs.items():
            if v is not None and hasattr(level, k):
                setattr(level, k, v)
        return self._level_repo.update(level)

    def delete_level(self, level_id: UUID, company_id: UUID) -> None:
        level = self._level_repo.get_by_id_or_none(id=level_id, company_id=company_id)
        if level is None:
            raise NotFoundException(f"ApprovalLevel {level_id} not found.")
        self._level_repo.soft_delete(id=level_id, company_id=company_id)

    def list_levels(self, rule_id: UUID, company_id: UUID) -> list[ApprovalLevel]:
        return self._level_repo.list_for_rule(company_id=company_id, rule_id=rule_id)

    # ------------------------------------------------------------------
    # Delegate management helpers
    # ------------------------------------------------------------------

    def create_delegate(
        self,
        company_id: UUID,
        actor_id: UUID,
        delegate_id: UUID,
        valid_from: datetime,
        valid_until: datetime,
        document_type: str | None = None,
        is_active: bool = True,
    ) -> ApprovalDelegate:
        if actor_id == delegate_id:
            raise ValueError("Cannot delegate approval authority to yourself.")
        if valid_from >= valid_until:
            raise ValueError("valid_from must be before valid_until.")

        delegate = ApprovalDelegate(
            company_id=company_id,
            created_by=actor_id,
            delegator_id=str(actor_id),
            delegate_id=str(delegate_id),
            valid_from=valid_from,
            valid_until=valid_until,
            document_type=document_type,
            is_active=is_active,
        )
        return self._delegate_repo.create(delegate)

    def update_delegate(
        self, delegate_id: UUID, company_id: UUID, **kwargs: Any
    ) -> ApprovalDelegate:
        delegation = self._delegate_repo.get_by_id_or_none(
            id=delegate_id, company_id=company_id
        )
        if delegation is None or delegation.is_deleted:
            raise NotFoundException(f"ApprovalDelegate {delegate_id} not found.")
        for k, v in kwargs.items():
            if v is not None and hasattr(delegation, k):
                setattr(delegation, k, v)
        return self._delegate_repo.update(delegation)

    def delete_delegate(self, delegate_id: UUID, company_id: UUID) -> None:
        delegation = self._delegate_repo.get_by_id_or_none(
            id=delegate_id, company_id=company_id
        )
        if delegation is None:
            raise NotFoundException(f"ApprovalDelegate {delegate_id} not found.")
        self._delegate_repo.soft_delete(id=delegate_id, company_id=company_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_approval_required(self, company_id: UUID, document_type: str) -> bool:
        """Check if approval is required for this document type via policy flags."""
        policy = self._policy_repo.get_for_company(company_id=company_id)
        if policy is None:
            return True  # Default: approval required when no policy configured

        if document_type == "PURCHASE_REQUEST":
            return policy.pr_approval_required
        if document_type == "PURCHASE_ORDER":
            return policy.po_approval_required
        # VENDOR_RETURN: always requires approval (no flag; treat as required)
        return True

    @staticmethod
    def _rule_matches(
        rule: MatrixRule,
        *,
        amount: Decimal | None,
        category_id: UUID | None,
        department: str | None,
    ) -> bool:
        """Return True if the given context satisfies the rule's condition."""
        if rule.condition_type == "ALWAYS":
            return True

        if rule.condition_type == "AMOUNT_RANGE":
            if amount is None:
                return False
            if rule.min_amount is not None and amount < Decimal(str(rule.min_amount)):
                return False
            if rule.max_amount is not None and amount > Decimal(str(rule.max_amount)):
                return False
            return True

        if rule.condition_type == "CATEGORY":
            if category_id is None or rule.category_id is None:
                return False
            return str(category_id) == rule.category_id

        if rule.condition_type == "DEPARTMENT":
            if department is None or rule.department is None:
                return False
            return department.strip().upper() == rule.department.strip().upper()

        return False

    @staticmethod
    def _level_to_read(level: ApprovalLevel) -> ApprovalLevelRead:
        return ApprovalLevelRead(
            id=level.id,
            company_id=level.company_id,
            rule_id=str(level.rule_id),
            level_number=level.level_number,
            approver_type=level.approver_type,
            approver_role=level.approver_role,
            approver_user_id=level.approver_user_id,
            escalation_days=level.escalation_days,
            created_at=level.created_at,
        )

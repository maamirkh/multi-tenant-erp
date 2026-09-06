"""Unit tests for ApprovalService — Phase 4.

Tests:
  - Self-approval prevention raises ConflictException
  - process_approval_decision: no pending record raises NotFoundException
  - process_approval_decision: already-decided record raises ConflictException
  - process_approval_decision: single-level approval returns all_approved=True
  - process_approval_decision: multi-level approval — partial, then full
  - process_approval_decision: rejection returns (False, True)
  - _find_applicable_rules: range matching, min/max None handling
  - evaluate_for_order: credit block raises ConflictException

Task: T129
Spec ref: specs/007-sales-management/spec.md §Approval Workflow
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from core.exceptions.base import ConflictException, NotFoundException
from modules.sales.services.approval_service import ApprovalService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service() -> ApprovalService:
    """Create an ApprovalService with a mock DB session."""
    db = MagicMock()
    return ApprovalService(db)


def _make_rule(
    level: int,
    min_amount: str,
    max_amount: str | None = None,
    auto_approve: bool = False,
    approver_user_id: str | None = None,
) -> MagicMock:
    rule = MagicMock()
    rule.approval_level = level
    rule.min_amount = Decimal(min_amount)
    rule.max_amount = Decimal(max_amount) if max_amount is not None else None
    rule.auto_approve = auto_approve
    rule.approver_user_id = approver_user_id
    return rule


def _make_pending_record(approver_id: str, level: int = 1) -> MagicMock:
    rec = MagicMock()
    rec.approver_id = approver_id
    rec.approval_level = level
    rec.decision = "PENDING"
    rec.id = str(uuid4())
    return rec


# ---------------------------------------------------------------------------
# _find_applicable_rules
# ---------------------------------------------------------------------------


class TestFindApplicableRules:
    """Test rule range matching logic."""

    def setup_method(self) -> None:
        self.svc = _make_service()
        self.order = MagicMock()

    def test_exact_minimum_match(self) -> None:
        rule = _make_rule(1, "100.00", "500.00")
        result = self.svc._find_applicable_rules([rule], Decimal("100.00"), self.order)
        assert rule in result

    def test_exact_maximum_match(self) -> None:
        rule = _make_rule(1, "100.00", "500.00")
        result = self.svc._find_applicable_rules([rule], Decimal("500.00"), self.order)
        assert rule in result

    def test_within_range(self) -> None:
        rule = _make_rule(1, "100.00", "500.00")
        result = self.svc._find_applicable_rules([rule], Decimal("250.00"), self.order)
        assert rule in result

    def test_below_min_excluded(self) -> None:
        rule = _make_rule(1, "100.00", "500.00")
        result = self.svc._find_applicable_rules([rule], Decimal("99.99"), self.order)
        assert rule not in result

    def test_above_max_excluded(self) -> None:
        rule = _make_rule(1, "100.00", "500.00")
        result = self.svc._find_applicable_rules([rule], Decimal("500.01"), self.order)
        assert rule not in result

    def test_no_max_matches_any_amount_above_min(self) -> None:
        rule = _make_rule(1, "0.00", None)
        result = self.svc._find_applicable_rules(
            [rule], Decimal("999999.00"), self.order
        )
        assert rule in result

    def test_no_max_excluded_below_min(self) -> None:
        rule = _make_rule(1, "500.00", None)
        result = self.svc._find_applicable_rules([rule], Decimal("100.00"), self.order)
        assert rule not in result

    def test_multiple_rules_multi_match(self) -> None:
        rule_low = _make_rule(1, "0.00", "999.99")
        rule_high = _make_rule(2, "1000.00", "9999.99")
        result = self.svc._find_applicable_rules(
            [rule_low, rule_high], Decimal("500.00"), self.order
        )
        assert rule_low in result
        assert rule_high not in result

    def test_empty_rules_list(self) -> None:
        result = self.svc._find_applicable_rules([], Decimal("500.00"), self.order)
        assert result == []

    def test_auto_approve_rule_included(self) -> None:
        rule = _make_rule(1, "0.00", "9999.00", auto_approve=True)
        result = self.svc._find_applicable_rules([rule], Decimal("500.00"), self.order)
        assert rule in result


# ---------------------------------------------------------------------------
# process_approval_decision
# ---------------------------------------------------------------------------


class TestProcessApprovalDecision:
    """Test approval/rejection decision processing."""

    def setup_method(self) -> None:
        self.svc = _make_service()
        # Replace repos with full MagicMocks so we can set return_value
        self.svc._order_repo = MagicMock()
        self.svc._record_repo = MagicMock()
        self.company_id = uuid4()
        self.doc_id = uuid4()
        self.approver_id = uuid4()
        self.requestor_id = uuid4()

    def _mock_order(self, approval_version: int = 1) -> MagicMock:
        order = MagicMock()
        order.approval_version = approval_version
        self.svc._order_repo.get_by_id_or_none.return_value = order
        return order

    def _mock_pending_records(self, records: list) -> None:
        self.svc._record_repo.get_pending_for_document.return_value = records

    def test_raises_not_found_when_order_missing(self) -> None:
        self.svc._order_repo.get_by_id_or_none.return_value = None
        with pytest.raises(NotFoundException):
            self.svc.process_approval_decision(
                company_id=self.company_id,
                document_type="SALES_ORDER",
                document_id=self.doc_id,
                approver_id=self.approver_id,
                decision="APPROVED",
            )

    def test_raises_not_found_when_no_pending_record_for_approver(self) -> None:
        self._mock_order()
        other_approver = str(uuid4())
        rec = _make_pending_record(other_approver)
        self._mock_pending_records([rec])

        with pytest.raises(NotFoundException, match="No pending approval record"):
            self.svc.process_approval_decision(
                company_id=self.company_id,
                document_type="SALES_ORDER",
                document_id=self.doc_id,
                approver_id=self.approver_id,
                decision="APPROVED",
            )

    def test_self_approval_prevention(self) -> None:
        """Approver same as requestor raises ConflictException."""
        self._mock_order()
        user_id = uuid4()
        rec = _make_pending_record(str(user_id))
        self._mock_pending_records([rec])

        with pytest.raises(ConflictException, match="Self-approval"):
            self.svc.process_approval_decision(
                company_id=self.company_id,
                document_type="SALES_ORDER",
                document_id=self.doc_id,
                approver_id=user_id,
                decision="APPROVED",
                requestor_id=user_id,  # same user
            )

    def test_already_decided_record_raises_conflict(self) -> None:
        self._mock_order()
        rec = _make_pending_record(str(self.approver_id))
        rec.decision = "APPROVED"  # Already decided
        self._mock_pending_records([rec])

        with pytest.raises(ConflictException, match="already in"):
            self.svc.process_approval_decision(
                company_id=self.company_id,
                document_type="SALES_ORDER",
                document_id=self.doc_id,
                approver_id=self.approver_id,
                decision="APPROVED",
            )

    def test_single_level_approval_returns_all_approved_true(self) -> None:
        self._mock_order()
        rec = _make_pending_record(str(self.approver_id), level=1)
        self._mock_pending_records([rec])

        all_approved, any_rejected = self.svc.process_approval_decision(
            company_id=self.company_id,
            document_type="SALES_ORDER",
            document_id=self.doc_id,
            approver_id=self.approver_id,
            decision="APPROVED",
        )

        assert all_approved is True
        assert any_rejected is False
        assert rec.decision == "APPROVED"

    def test_multi_level_partial_approval_returns_false(self) -> None:
        self._mock_order()
        rec_l1 = _make_pending_record(str(self.approver_id), level=1)
        rec_l2_id = str(uuid4())
        rec_l2 = _make_pending_record(rec_l2_id, level=2)
        # Both start pending
        self._mock_pending_records([rec_l1, rec_l2])

        all_approved, any_rejected = self.svc.process_approval_decision(
            company_id=self.company_id,
            document_type="SALES_ORDER",
            document_id=self.doc_id,
            approver_id=self.approver_id,
            decision="APPROVED",
        )

        # L2 is still pending → not all approved
        assert all_approved is False
        assert any_rejected is False

    def test_rejection_returns_any_rejected_true(self) -> None:
        self._mock_order()
        rec = _make_pending_record(str(self.approver_id), level=1)
        self._mock_pending_records([rec])

        all_approved, any_rejected = self.svc.process_approval_decision(
            company_id=self.company_id,
            document_type="SALES_ORDER",
            document_id=self.doc_id,
            approver_id=self.approver_id,
            decision="REJECTED",
        )

        assert all_approved is False
        assert any_rejected is True
        assert rec.decision == "REJECTED"

    def test_invalid_decision_raises_conflict(self) -> None:
        with pytest.raises(ConflictException, match="Invalid decision"):
            self.svc.process_approval_decision(
                company_id=self.company_id,
                document_type="SALES_ORDER",
                document_id=self.doc_id,
                approver_id=self.approver_id,
                decision="MAYBE",
            )

    def test_approved_decision_sets_decided_at(self) -> None:
        self._mock_order()
        rec = _make_pending_record(str(self.approver_id))
        self._mock_pending_records([rec])

        self.svc.process_approval_decision(
            company_id=self.company_id,
            document_type="SALES_ORDER",
            document_id=self.doc_id,
            approver_id=self.approver_id,
            decision="APPROVED",
        )

        assert rec.decided_at is not None


# ---------------------------------------------------------------------------
# evaluate_for_order — credit check blocking
# ---------------------------------------------------------------------------


class TestEvaluateForOrderCreditCheck:
    """Test that credit block raises ConflictException."""

    def setup_method(self) -> None:
        self.svc = _make_service()
        self.svc._order_repo = MagicMock()
        self.svc._credit_service = MagicMock()
        self.company_id = uuid4()
        self.order_id = uuid4()
        self.submitted_by = uuid4()

    def _mock_order(self, customer_id: str, total: str) -> MagicMock:
        order = MagicMock()
        order.customer_id = customer_id
        order.total_amount = Decimal(total)
        order.order_number = "SO-2026-000001"
        order.approval_version = 1
        self.svc._order_repo.get_by_id_or_none.return_value = order
        return order

    def test_credit_block_raises_conflict(self) -> None:
        customer_id = str(uuid4())
        self._mock_order(customer_id, "5000.00")

        blocked_result = MagicMock()
        blocked_result.allowed = False
        blocked_result.message = "Customer is on credit hold."
        blocked_result.credit_status = "HOLD"
        blocked_result.credit_limit = Decimal("10000.00")
        blocked_result.outstanding_balance = Decimal("0")
        blocked_result.order_total = Decimal("5000.00")

        self.svc._credit_service = MagicMock()
        self.svc._credit_service.evaluate_credit.return_value = blocked_result

        with pytest.raises(ConflictException, match="Credit check failed"):
            self.svc.evaluate_for_order(
                company_id=self.company_id,
                order_id=self.order_id,
                submitted_by=self.submitted_by,
            )

    def test_order_not_found_raises(self) -> None:
        self.svc._order_repo.get_by_id_or_none.return_value = None

        with pytest.raises(NotFoundException):
            self.svc.evaluate_for_order(
                company_id=self.company_id,
                order_id=self.order_id,
                submitted_by=self.submitted_by,
            )

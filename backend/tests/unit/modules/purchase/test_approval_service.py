"""Unit tests for Phase 3 ApprovalService — T093.

Tests:
  - Auto-approval when policy disables approval
  - Auto-approval when no active matrix configured
  - Auto-approval when no rule matches
  - Route correctly identifies matching rule and levels
  - Self-approval prevention
  - AlreadyActionedError prevention
  - Rule condition matching (ALWAYS, AMOUNT_RANGE, CATEGORY, DEPARTMENT)
  - Emergency bypass requires justification
  - Reject requires comment
  - Delegation resolves correctly
  - _is_approval_required for PR and PO

No database required — uses MagicMock for repositories.

Task: T093
Spec ref: specs/006-purchase-management/spec.md §22 Business Workflows
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from modules.purchase.models.approval import (
    ApprovalLevel,
    ApprovalMatrix,
    ApprovalRecord,
    MatrixRule,
)
from modules.purchase.models.policy import PurchasePolicy
from modules.purchase.services.approval_service import (
    AlreadyActionedError,
    ApprovalService,
    SelfApprovalError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(
    *,
    policy_approval_required: bool = True,
    matrix: ApprovalMatrix | None = None,
    rules: list[MatrixRule] | None = None,
    levels: list[ApprovalLevel] | None = None,
    records: list[ApprovalRecord] | None = None,
    active_delegation=None,
):
    """Build an ApprovalService with mocked repositories."""
    db = MagicMock()

    matrix_repo = MagicMock()
    rule_repo = MagicMock()
    level_repo = MagicMock()
    record_repo = MagicMock()
    delegate_repo = MagicMock()
    policy_repo = MagicMock()

    company_id = uuid4()

    # Policy
    policy = MagicMock(spec=PurchasePolicy)
    policy.pr_approval_required = policy_approval_required
    policy.po_approval_required = policy_approval_required
    policy_repo.get_for_company.return_value = policy

    # Matrix
    matrix_repo.get_active_for_document_type.return_value = matrix

    # Rules
    rule_repo.list_for_matrix.return_value = rules or []

    # Levels
    level_repo.list_for_rule.return_value = levels or []

    # Records
    record_repo.list_for_document.return_value = records or []
    record_repo.get_for_document_level.return_value = records or []
    record_repo.create.side_effect = lambda r: r

    # Delegation
    delegate_repo.get_active_delegation.return_value = active_delegation

    svc = ApprovalService(
        db=db,
        matrix_repo=matrix_repo,
        rule_repo=rule_repo,
        level_repo=level_repo,
        record_repo=record_repo,
        delegate_repo=delegate_repo,
        policy_repo=policy_repo,
    )
    return svc, company_id


def _make_matrix(document_type: str = "PURCHASE_REQUEST") -> ApprovalMatrix:
    m = MagicMock(spec=ApprovalMatrix)
    m.id = uuid4()
    m.company_id = uuid4()
    m.document_type = document_type
    m.name = "Test Matrix"
    m.is_active = True
    m.is_deleted = False
    return m


def _make_rule(condition_type: str = "ALWAYS", **kwargs) -> MatrixRule:
    r = MagicMock(spec=MatrixRule)
    r.id = uuid4()
    r.company_id = uuid4()
    r.condition_type = condition_type
    r.min_amount = kwargs.get("min_amount")
    r.max_amount = kwargs.get("max_amount")
    r.category_id = str(kwargs["category_id"]) if kwargs.get("category_id") else None
    r.department = kwargs.get("department")
    r.approval_level = 1
    r.approval_mode = "SEQUENTIAL"
    r.is_deleted = False
    return r


def _make_level(level_number: int = 1, approver_type: str = "ROLE") -> ApprovalLevel:
    lv = MagicMock(spec=ApprovalLevel)
    lv.id = uuid4()
    lv.company_id = uuid4()
    lv.rule_id = str(uuid4())
    lv.level_number = level_number
    lv.approver_type = approver_type
    lv.approver_role = "PURCHASE_MANAGER" if approver_type == "ROLE" else None
    lv.approver_user_id = None
    lv.escalation_days = 3
    lv.created_at = datetime.now(UTC)
    return lv


def _make_record(action: str = "APPROVED", level_number: int = 1) -> ApprovalRecord:
    rec = MagicMock(spec=ApprovalRecord)
    rec.id = uuid4()
    rec.company_id = uuid4()
    rec.document_type = "PURCHASE_REQUEST"
    rec.document_id = str(uuid4())
    rec.level_number = level_number
    rec.approver_id = str(uuid4())
    rec.action = action
    rec.comment = None
    rec.is_emergency_bypass = False
    rec.bypass_justification = None
    rec.actioned_at = datetime.now(UTC)
    rec.created_at = datetime.now(UTC)
    return rec


# ===========================================================================
# Auto-approval scenarios
# ===========================================================================


class TestAutoApproval:
    """Tests covering the various auto-approval paths."""

    def test_auto_approve_when_policy_disables_pr(self):
        """PR auto-approved when pr_approval_required=False."""
        svc, cid = _make_service(policy_approval_required=False)
        result = svc.route_for_approval(
            document_type="PURCHASE_REQUEST",
            document_id=uuid4(),
            company_id=cid,
        )
        assert result.auto_approved is True
        assert result.matrix_found is False
        assert result.required_levels == []

    def test_auto_approve_when_no_matrix(self):
        """Auto-approved when no active matrix configured."""
        svc, cid = _make_service(matrix=None)
        result = svc.route_for_approval(
            document_type="PURCHASE_REQUEST",
            document_id=uuid4(),
            company_id=cid,
        )
        assert result.auto_approved is True
        assert result.matrix_found is False

    def test_auto_approve_when_no_matching_rule(self):
        """Auto-approved when matrix has no matching rule for the document."""
        matrix = _make_matrix()
        # Rule requires AMOUNT_RANGE 100–500 but we pass amount=50
        rule = _make_rule(condition_type="AMOUNT_RANGE", min_amount=100, max_amount=500)
        svc, cid = _make_service(matrix=matrix, rules=[rule], levels=[])
        result = svc.route_for_approval(
            document_type="PURCHASE_REQUEST",
            document_id=uuid4(),
            company_id=cid,
            amount=Decimal("50"),
        )
        assert result.auto_approved is True
        assert result.matrix_found is True
        assert result.applicable_rule_id is None

    def test_route_identifies_matching_rule_and_levels(self):
        """route_for_approval returns required levels when a rule matches."""
        matrix = _make_matrix()
        rule = _make_rule(condition_type="ALWAYS")
        level1 = _make_level(level_number=1)
        level2 = _make_level(level_number=2)
        svc, cid = _make_service(matrix=matrix, rules=[rule], levels=[level1, level2])
        result = svc.route_for_approval(
            document_type="PURCHASE_REQUEST",
            document_id=uuid4(),
            company_id=cid,
        )
        assert result.auto_approved is False
        assert result.matrix_found is True
        assert result.applicable_rule_id == str(rule.id)
        assert len(result.required_levels) == 2

    def test_first_matching_rule_wins(self):
        """Only the first matching rule is used (priority ordering)."""
        matrix = _make_matrix()
        rule1 = _make_rule(
            condition_type="AMOUNT_RANGE", min_amount=0, max_amount=10000
        )
        rule2 = _make_rule(condition_type="ALWAYS")
        level = _make_level(level_number=1)
        svc, cid = _make_service(matrix=matrix, rules=[rule1, rule2], levels=[level])
        result = svc.route_for_approval(
            document_type="PURCHASE_REQUEST",
            document_id=uuid4(),
            company_id=cid,
            amount=Decimal("500"),
        )
        assert result.applicable_rule_id == str(rule1.id)


# ===========================================================================
# Rule condition matching
# ===========================================================================


class TestRuleConditionMatching:
    """Tests for _rule_matches static method."""

    def test_always_matches(self):
        rule = _make_rule("ALWAYS")
        assert ApprovalService._rule_matches(
            rule, amount=None, category_id=None, department=None
        )

    def test_amount_range_matches_in_range(self):
        rule = _make_rule("AMOUNT_RANGE", min_amount=100, max_amount=5000)
        assert ApprovalService._rule_matches(
            rule, amount=Decimal("500"), category_id=None, department=None
        )

    def test_amount_range_misses_below_min(self):
        rule = _make_rule("AMOUNT_RANGE", min_amount=100, max_amount=5000)
        assert not ApprovalService._rule_matches(
            rule, amount=Decimal("50"), category_id=None, department=None
        )

    def test_amount_range_misses_above_max(self):
        rule = _make_rule("AMOUNT_RANGE", min_amount=100, max_amount=5000)
        assert not ApprovalService._rule_matches(
            rule, amount=Decimal("9999"), category_id=None, department=None
        )

    def test_amount_range_no_amount_no_match(self):
        rule = _make_rule("AMOUNT_RANGE", min_amount=0, max_amount=1000)
        assert not ApprovalService._rule_matches(
            rule, amount=None, category_id=None, department=None
        )

    def test_amount_range_no_max_matches_any_above_min(self):
        rule = _make_rule("AMOUNT_RANGE", min_amount=100, max_amount=None)
        assert ApprovalService._rule_matches(
            rule, amount=Decimal("999999"), category_id=None, department=None
        )

    def test_category_matches(self):
        cat_id = uuid4()
        rule = _make_rule("CATEGORY", category_id=cat_id)
        assert ApprovalService._rule_matches(
            rule, amount=None, category_id=cat_id, department=None
        )

    def test_category_no_match(self):
        rule = _make_rule("CATEGORY", category_id=uuid4())
        assert not ApprovalService._rule_matches(
            rule, amount=None, category_id=uuid4(), department=None
        )

    def test_category_no_category_id_no_match(self):
        rule = _make_rule("CATEGORY", category_id=uuid4())
        assert not ApprovalService._rule_matches(
            rule, amount=None, category_id=None, department=None
        )

    def test_department_matches_case_insensitive(self):
        rule = _make_rule("DEPARTMENT", department="IT")
        assert ApprovalService._rule_matches(
            rule, amount=None, category_id=None, department="it"
        )

    def test_department_no_match(self):
        rule = _make_rule("DEPARTMENT", department="IT")
        assert not ApprovalService._rule_matches(
            rule, amount=None, category_id=None, department="FINANCE"
        )

    def test_department_none_no_match(self):
        rule = _make_rule("DEPARTMENT", department="IT")
        assert not ApprovalService._rule_matches(
            rule, amount=None, category_id=None, department=None
        )


# ===========================================================================
# Approve action
# ===========================================================================


class TestApproveAction:
    """Tests for the approve() method."""

    def test_approve_success(self):
        """approve() returns an ApprovalRecord with action=APPROVED."""
        svc, cid = _make_service(records=[])
        record = svc.approve(
            document_type="PURCHASE_REQUEST",
            document_id=uuid4(),
            approver_id=uuid4(),
            company_id=cid,
            level_number=1,
        )
        assert record.action == "APPROVED"
        assert record.is_emergency_bypass is False

    def test_approve_self_approval_raises(self):
        """approve() raises SelfApprovalError when approver == requestor."""
        svc, cid = _make_service(records=[])
        user_id = uuid4()
        with pytest.raises(SelfApprovalError):
            svc.approve(
                document_type="PURCHASE_REQUEST",
                document_id=uuid4(),
                approver_id=user_id,
                company_id=cid,
                level_number=1,
                requestor_id=user_id,
            )

    def test_approve_already_approved_raises(self):
        """approve() raises AlreadyActionedError when level already approved."""
        existing = _make_record(action="APPROVED", level_number=1)
        svc, cid = _make_service(records=[existing])
        doc_id = uuid4()
        with pytest.raises(AlreadyActionedError):
            svc.approve(
                document_type="PURCHASE_REQUEST",
                document_id=doc_id,
                approver_id=uuid4(),
                company_id=cid,
                level_number=1,
            )

    def test_approve_with_comment(self):
        """approve() stores the comment on the record."""
        svc, cid = _make_service(records=[])
        record = svc.approve(
            document_type="PURCHASE_REQUEST",
            document_id=uuid4(),
            approver_id=uuid4(),
            company_id=cid,
            level_number=1,
            comment="Looks good.",
        )
        assert record.comment == "Looks good."


# ===========================================================================
# Reject action
# ===========================================================================


class TestRejectAction:
    def test_reject_requires_comment(self):
        """reject() raises ValueError when comment is empty."""
        svc, cid = _make_service()
        with pytest.raises(ValueError, match="rejection comment"):
            svc.reject(
                document_type="PURCHASE_REQUEST",
                document_id=uuid4(),
                approver_id=uuid4(),
                company_id=cid,
                level_number=1,
                comment="",
            )

    def test_reject_success(self):
        """reject() returns ApprovalRecord with action=REJECTED."""
        svc, cid = _make_service()
        record = svc.reject(
            document_type="PURCHASE_REQUEST",
            document_id=uuid4(),
            approver_id=uuid4(),
            company_id=cid,
            level_number=1,
            comment="Budget exceeded.",
        )
        assert record.action == "REJECTED"
        assert record.comment == "Budget exceeded."


# ===========================================================================
# Emergency bypass
# ===========================================================================


class TestEmergencyBypass:
    def test_bypass_requires_justification(self):
        """emergency_bypass() raises ValueError when justification is empty."""
        svc, cid = _make_service()
        with pytest.raises(ValueError, match="justification"):
            svc.emergency_bypass(
                document_type="PURCHASE_REQUEST",
                document_id=uuid4(),
                bypasser_id=uuid4(),
                company_id=cid,
                justification="",
            )

    def test_bypass_success(self):
        """emergency_bypass() returns an APPROVED record with is_emergency_bypass=True."""
        svc, cid = _make_service()
        record = svc.emergency_bypass(
            document_type="PURCHASE_REQUEST",
            document_id=uuid4(),
            bypasser_id=uuid4(),
            company_id=cid,
            justification="Urgent supply needed.",
        )
        assert record.action == "APPROVED"
        assert record.is_emergency_bypass is True
        assert record.bypass_justification == "Urgent supply needed."
        assert (
            record.level_number == 1
        )  # DB CHECK requires level_number >= 1; is_emergency_bypass is the signal


# ===========================================================================
# Delegation
# ===========================================================================


class TestDelegation:
    def test_resolve_approver_no_delegation(self):
        """resolve_approver returns original approver when no delegation active."""
        svc, cid = _make_service(active_delegation=None)
        approver_id = uuid4()
        result = svc.resolve_approver(approver_id=approver_id, company_id=cid)
        assert result == approver_id

    def test_resolve_approver_with_delegation(self):
        """resolve_approver returns delegate_id when active delegation exists."""
        delegate_id = uuid4()
        delegation = MagicMock()
        delegation.delegate_id = str(delegate_id)
        svc, cid = _make_service(active_delegation=delegation)
        approver_id = uuid4()
        result = svc.resolve_approver(
            approver_id=approver_id,
            company_id=cid,
            document_type="PURCHASE_REQUEST",
        )
        assert result == delegate_id


# ===========================================================================
# ApprovalRecord immutability
# ===========================================================================


class TestApprovalRecordImmutability:
    def test_update_raises(self):
        """ApprovalRecordRepository.update() raises NotImplementedError."""
        from modules.purchase.repositories.approval import ApprovalRecordRepository

        repo = ApprovalRecordRepository(db=MagicMock())
        with pytest.raises(NotImplementedError):
            repo.update(MagicMock())

    def test_soft_delete_raises(self):
        """ApprovalRecordRepository.soft_delete() raises NotImplementedError."""
        from uuid import uuid4

        from modules.purchase.repositories.approval import ApprovalRecordRepository

        repo = ApprovalRecordRepository(db=MagicMock())
        with pytest.raises(NotImplementedError):
            repo.soft_delete(id=uuid4(), company_id=uuid4())

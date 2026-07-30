"""Unit tests for Approval Engine feature flags — T097.

Tests:
  - pr_approval_required=False → auto-approves PURCHASE_REQUEST
  - pr_approval_required=True  → routes through matrix
  - po_approval_required=False → auto-approves PURCHASE_ORDER
  - po_approval_required=True  → routes through matrix
  - Missing policy → treated as approval required (safe default)

No database — all repos mocked.

Task: T097
Spec ref: specs/006-purchase-management/spec.md §29 Feature Matrix
"""

from __future__ import annotations

from datetime import UTC
from unittest.mock import MagicMock
from uuid import uuid4

from modules.purchase.models.approval import ApprovalLevel, ApprovalMatrix, MatrixRule
from modules.purchase.models.policy import PurchasePolicy
from modules.purchase.services.approval_service import ApprovalService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(
    *,
    pr_approval_required: bool,
    po_approval_required: bool,
    matrix: ApprovalMatrix | None = None,
    rules: list[MatrixRule] | None = None,
    levels: list[ApprovalLevel] | None = None,
):
    db = MagicMock()
    matrix_repo = MagicMock()
    rule_repo = MagicMock()
    level_repo = MagicMock()
    record_repo = MagicMock()
    delegate_repo = MagicMock()
    policy_repo = MagicMock()

    policy = MagicMock(spec=PurchasePolicy)
    policy.pr_approval_required = pr_approval_required
    policy.po_approval_required = po_approval_required
    policy_repo.get_for_company.return_value = policy

    matrix_repo.get_active_for_document_type.return_value = matrix
    rule_repo.list_for_matrix.return_value = rules or []
    level_repo.list_for_rule.return_value = levels or []
    record_repo.list_for_document.return_value = []
    record_repo.get_for_document_level.return_value = []
    record_repo.create.side_effect = lambda r: r
    delegate_repo.get_active_delegation.return_value = None

    svc = ApprovalService(
        db=db,
        matrix_repo=matrix_repo,
        rule_repo=rule_repo,
        level_repo=level_repo,
        record_repo=record_repo,
        delegate_repo=delegate_repo,
        policy_repo=policy_repo,
    )
    return svc, uuid4()


def _make_matrix():
    m = MagicMock(spec=ApprovalMatrix)
    m.id = uuid4()
    m.is_active = True
    m.is_deleted = False
    return m


def _make_rule():
    r = MagicMock(spec=MatrixRule)
    r.id = uuid4()
    r.condition_type = "ALWAYS"
    r.min_amount = None
    r.max_amount = None
    r.category_id = None
    r.department = None
    r.is_deleted = False
    return r


def _make_level(level_number: int = 1):
    lv = MagicMock(spec=ApprovalLevel)
    lv.id = uuid4()
    lv.company_id = uuid4()
    lv.rule_id = str(uuid4())
    lv.level_number = level_number
    lv.approver_type = "ROLE"
    lv.approver_role = "PURCHASE_MANAGER"
    lv.approver_user_id = None
    lv.escalation_days = 3
    from datetime import datetime

    lv.created_at = datetime.now(UTC)
    return lv


# ===========================================================================
# PR approval flag
# ===========================================================================


class TestPRApprovalFlag:
    def test_pr_flag_off_auto_approves(self):
        svc, cid = _make_service(pr_approval_required=False, po_approval_required=True)
        result = svc.route_for_approval(
            document_type="PURCHASE_REQUEST",
            document_id=uuid4(),
            company_id=cid,
        )
        assert result.auto_approved is True
        assert result.matrix_found is False
        assert result.required_levels == []

    def test_pr_flag_on_with_matrix_requires_approval(self):
        matrix = _make_matrix()
        rule = _make_rule()
        level = _make_level()
        svc, cid = _make_service(
            pr_approval_required=True,
            po_approval_required=True,
            matrix=matrix,
            rules=[rule],
            levels=[level],
        )
        result = svc.route_for_approval(
            document_type="PURCHASE_REQUEST",
            document_id=uuid4(),
            company_id=cid,
        )
        assert result.auto_approved is False
        assert result.matrix_found is True
        assert len(result.required_levels) == 1

    def test_pr_flag_on_no_matrix_still_auto_approves(self):
        """No matrix configured → auto-approve even when flag is ON."""
        svc, cid = _make_service(
            pr_approval_required=True, po_approval_required=True, matrix=None
        )
        result = svc.route_for_approval(
            document_type="PURCHASE_REQUEST",
            document_id=uuid4(),
            company_id=cid,
        )
        assert result.auto_approved is True
        assert result.matrix_found is False


# ===========================================================================
# PO approval flag
# ===========================================================================


class TestPOApprovalFlag:
    def test_po_flag_off_auto_approves(self):
        svc, cid = _make_service(pr_approval_required=True, po_approval_required=False)
        result = svc.route_for_approval(
            document_type="PURCHASE_ORDER",
            document_id=uuid4(),
            company_id=cid,
        )
        assert result.auto_approved is True
        assert result.matrix_found is False

    def test_po_flag_on_with_matrix_requires_approval(self):
        matrix = _make_matrix()
        rule = _make_rule()
        level = _make_level()
        svc, cid = _make_service(
            pr_approval_required=True,
            po_approval_required=True,
            matrix=matrix,
            rules=[rule],
            levels=[level],
        )
        result = svc.route_for_approval(
            document_type="PURCHASE_ORDER",
            document_id=uuid4(),
            company_id=cid,
        )
        assert result.auto_approved is False
        assert result.matrix_found is True

    def test_po_flag_off_does_not_affect_pr_flag(self):
        """Disabling PO approval does not disable PR approval."""
        matrix = _make_matrix()
        rule = _make_rule()
        level = _make_level()
        svc, cid = _make_service(
            pr_approval_required=True,
            po_approval_required=False,
            matrix=matrix,
            rules=[rule],
            levels=[level],
        )
        result = svc.route_for_approval(
            document_type="PURCHASE_REQUEST",
            document_id=uuid4(),
            company_id=cid,
        )
        assert result.auto_approved is False


# ===========================================================================
# Cross-document-type isolation
# ===========================================================================


class TestDocumentTypeIsolation:
    def test_pr_and_po_flags_independent(self):
        """PR flag OFF and PO flag ON are independent."""
        svc_pr_off, cid = _make_service(
            pr_approval_required=False, po_approval_required=True
        )
        pr_result = svc_pr_off.route_for_approval(
            document_type="PURCHASE_REQUEST", document_id=uuid4(), company_id=cid
        )
        po_result = svc_pr_off.route_for_approval(
            document_type="PURCHASE_ORDER", document_id=uuid4(), company_id=cid
        )
        assert pr_result.auto_approved is True  # PR flag off
        assert po_result.auto_approved is True  # No matrix configured → auto-approve

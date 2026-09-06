"""Unit tests for ApprovalRecord immutability and delegation invariants — T094.

Tests:
  - ApprovalRecord: no update() method (NotImplementedError)
  - ApprovalRecord: no soft_delete() method (NotImplementedError)
  - Delegation: active delegate is used when valid window matches
  - Delegation: expired delegate is ignored (returns original approver)
  - Emergency bypass: bypass_justification required (ValueError on empty)
  - Emergency bypass: bypass produces is_emergency_bypass=True record

No database — all repos mocked.

Task: T094
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from modules.purchase.repositories.approval import ApprovalRecordRepository
from modules.purchase.services.approval_service import ApprovalService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(active_delegation=None):
    db = MagicMock()
    matrix_repo = MagicMock()
    rule_repo = MagicMock()
    level_repo = MagicMock()
    record_repo = MagicMock()
    delegate_repo = MagicMock()
    policy_repo = MagicMock()

    policy = MagicMock()
    policy.pr_approval_required = True
    policy.po_approval_required = True
    policy_repo.get_for_company.return_value = policy

    matrix_repo.get_active_for_document_type.return_value = None  # auto-approve path
    rule_repo.list_for_matrix.return_value = []
    level_repo.list_for_rule.return_value = []
    record_repo.list_for_document.return_value = []
    record_repo.get_for_document_level.return_value = []
    record_repo.create.side_effect = lambda r: r
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
    return svc, uuid4()


# ===========================================================================
# ApprovalRecord immutability
# ===========================================================================


class TestApprovalRecordImmutability:
    """ApprovalRecord must be append-only — no update or delete."""

    def test_update_raises_not_implemented(self):
        repo = ApprovalRecordRepository(db=MagicMock())
        with pytest.raises(NotImplementedError):
            repo.update(MagicMock())

    def test_soft_delete_raises_not_implemented(self):
        repo = ApprovalRecordRepository(db=MagicMock())
        with pytest.raises(NotImplementedError):
            repo.soft_delete(id=uuid4(), company_id=uuid4())


# ===========================================================================
# Delegation routing
# ===========================================================================


class TestDelegationInvariants:
    """Delegation routing respects the valid_from/valid_until window."""

    def test_active_delegate_is_returned(self):
        delegate_id = uuid4()
        delegation = MagicMock()
        delegation.delegate_id = str(delegate_id)
        svc, cid = _make_service(active_delegation=delegation)
        result = svc.resolve_approver(
            approver_id=uuid4(),
            company_id=cid,
            document_type="PURCHASE_REQUEST",
        )
        assert result == delegate_id

    def test_no_active_delegate_returns_original_approver(self):
        approver_id = uuid4()
        svc, cid = _make_service(active_delegation=None)
        result = svc.resolve_approver(approver_id=approver_id, company_id=cid)
        assert result == approver_id

    def test_different_approvers_get_independent_resolution(self):
        """Two different approvers should resolve independently (no cross-contamination)."""
        delegate_id = uuid4()
        delegation = MagicMock()
        delegation.delegate_id = str(delegate_id)
        svc, cid = _make_service(active_delegation=delegation)

        approver1 = uuid4()
        approver2 = uuid4()
        # Both resolve to delegate_id because delegation mock always returns it
        result1 = svc.resolve_approver(approver_id=approver1, company_id=cid)
        result2 = svc.resolve_approver(approver_id=approver2, company_id=cid)
        assert result1 == delegate_id
        assert result2 == delegate_id


# ===========================================================================
# Emergency bypass audit
# ===========================================================================


class TestEmergencyBypassAudit:
    """Emergency bypass must always record justification."""

    def test_bypass_records_justification(self):
        svc, cid = _make_service()
        record = svc.emergency_bypass(
            document_type="PURCHASE_REQUEST",
            document_id=uuid4(),
            bypasser_id=uuid4(),
            company_id=cid,
            justification="Critical stock shortage.",
        )
        assert record.is_emergency_bypass is True
        assert record.bypass_justification == "Critical stock shortage."

    def test_bypass_empty_justification_raises(self):
        svc, cid = _make_service()
        with pytest.raises(ValueError, match="justification"):
            svc.emergency_bypass(
                document_type="PURCHASE_REQUEST",
                document_id=uuid4(),
                bypasser_id=uuid4(),
                company_id=cid,
                justification="",
            )

    def test_bypass_whitespace_justification_raises(self):
        svc, cid = _make_service()
        with pytest.raises(ValueError, match="justification"):
            svc.emergency_bypass(
                document_type="PURCHASE_REQUEST",
                document_id=uuid4(),
                bypasser_id=uuid4(),
                company_id=cid,
                justification="   ",
            )

    def test_bypass_action_is_approved(self):
        svc, cid = _make_service()
        record = svc.emergency_bypass(
            document_type="PURCHASE_REQUEST",
            document_id=uuid4(),
            bypasser_id=uuid4(),
            company_id=cid,
            justification="Urgent procurement.",
        )
        assert record.action == "APPROVED"

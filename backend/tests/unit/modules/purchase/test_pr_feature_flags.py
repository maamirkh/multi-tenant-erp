"""Unit tests for Purchase Request feature flags — T118.

Tests:
  - PR submission event is published regardless of approval flag
  - PR can be submitted when pr_approval_required=False (auto-approve at routing)
  - PR state machine does not depend on policy flags (service is flag-agnostic)
  - Verify ALLOWED_TRANSITIONS match spec requirements

The PRService itself does not check feature flags; it is the calling context
(API + approval engine) that checks flags. These tests verify the state machine
is correctly spec'd for both flag states.

Task: T118
Spec ref: specs/006-purchase-management/spec.md §29 Feature Matrix
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from modules.purchase.models.purchase_request import PRLine, PurchaseRequest
from modules.purchase.services.pr_service import (
    ALLOWED_TRANSITIONS,
    PRMissingLinesError,
    PRService,
)


def _make_service(
    *,
    pr: PurchaseRequest | None = None,
    lines: list[PRLine] | None = None,
):
    db = MagicMock()
    pr_repo = MagicMock()
    line_repo = MagicMock()
    seq_svc = MagicMock()

    seq_svc.generate_next_number.return_value = "PR-2026-000001"

    if pr is not None:
        pr_repo.get_by_id_or_none.return_value = pr
    else:
        pr_repo.get_by_id_or_none.return_value = None

    pr_repo.update_status.return_value = None
    pr_repo.update_total_cost.return_value = None

    line_repo.list_for_pr.return_value = lines or []

    return PRService(
        db=db, pr_repo=pr_repo, line_repo=line_repo, sequence_service=seq_svc
    )


def _make_pr(status: str = "DRAFT") -> PurchaseRequest:
    pr = MagicMock(spec=PurchaseRequest)
    pr.id = uuid4()
    pr.company_id = uuid4()
    pr.pr_number = "PR-2026-000001"
    pr.title = "Test PR"
    pr.status = status
    pr.requestor_id = str(uuid4())
    pr.department = None
    pr.required_by_date = None
    pr.notes = None
    pr.total_estimated_cost = Decimal("100.00")
    pr.currency_code = "USD"
    pr.converted_to_po_id = None
    pr.branch_id = None
    return pr


def _make_line() -> PRLine:
    line = MagicMock(spec=PRLine)
    line.id = uuid4()
    line.company_id = uuid4()
    line.pr_id = str(uuid4())
    line.line_number = 1
    line.product_description = "Item"
    line.quantity = Decimal("1.000")
    line.estimated_unit_cost = Decimal("100.0000")
    line.estimated_line_total = Decimal("100.00")
    line.notes = None
    return line


class TestStateTransitionsForFlagStates:
    """State transitions are independent of policy flags."""

    def test_draft_can_always_be_submitted(self):
        """DRAFT → SUBMITTED is valid regardless of approval flag."""
        assert "SUBMITTED" in ALLOWED_TRANSITIONS["DRAFT"]

    def test_submitted_can_be_auto_approved(self):
        """SUBMITTED → APPROVED supports auto-approval path."""
        assert "APPROVED" in ALLOWED_TRANSITIONS["SUBMITTED"]

    def test_submitted_goes_to_under_review_for_manual_approval(self):
        """SUBMITTED → UNDER_REVIEW for manual approval routing."""
        assert "UNDER_REVIEW" in ALLOWED_TRANSITIONS["SUBMITTED"]

    def test_cancelled_is_terminal(self):
        assert ALLOWED_TRANSITIONS["CANCELLED"] == []

    def test_approved_is_terminal(self):
        assert ALLOWED_TRANSITIONS["APPROVED"] == []

    def test_rejected_is_terminal(self):
        assert ALLOWED_TRANSITIONS["REJECTED"] == []


class TestSubmitPublishesEvent:
    """submit_pr always publishes PurchaseRequestSubmitted regardless of flags."""

    def test_submit_publishes_event(self):
        pr = _make_pr("DRAFT")
        line = _make_line()
        svc = _make_service(pr=pr, lines=[line])

        with patch("modules.purchase.services.pr_service.get_event_bus") as mock_bus:
            published = []
            mock_bus.return_value.publish = lambda e: published.append(e)
            with patch.object(svc, "_build_pr_read", return_value=MagicMock()):
                svc.submit_pr(pr.id, pr.company_id, uuid4())

        assert len(published) == 1
        assert published[0].event_type == "purchase_request.submitted"


class TestAutoApprovalPath:
    """When pr_approval_required=False the caller transitions PR directly to APPROVED."""

    def test_submitted_can_directly_approve(self):
        """Verify SUBMITTED → APPROVED is valid for auto-approval path."""
        pr = _make_pr("SUBMITTED")
        svc = _make_service(pr=pr)

        with patch("modules.purchase.services.pr_service.get_event_bus") as mock_bus:
            mock_bus.return_value.publish = MagicMock()
            with patch.object(svc, "_build_pr_read", return_value=MagicMock()):
                svc.approve_pr(pr.id, pr.company_id, uuid4(), auto_approved=True)

        svc.pr_repo.update_status.assert_called_with(pr.id, pr.company_id, "APPROVED")

    def test_auto_approved_event_carries_flag(self):
        pr = _make_pr("SUBMITTED")
        svc = _make_service(pr=pr)

        with patch("modules.purchase.services.pr_service.get_event_bus") as mock_bus:
            published = []
            mock_bus.return_value.publish = lambda e: published.append(e)
            with patch.object(svc, "_build_pr_read", return_value=MagicMock()):
                svc.approve_pr(pr.id, pr.company_id, uuid4(), auto_approved=True)

        assert published[0].auto_approved is True


class TestSubmitRequiresLines:
    """PR must have at least one line to submit (flag-independent)."""

    def test_submit_without_lines_raises(self):
        pr = _make_pr("DRAFT")
        svc = _make_service(pr=pr, lines=[])

        with pytest.raises(PRMissingLinesError):
            svc.submit_pr(pr.id, pr.company_id, uuid4())

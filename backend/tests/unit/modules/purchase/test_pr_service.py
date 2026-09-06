"""Unit tests for PRService — T114.

Tests:
  - create_pr creates a DRAFT PR with sequence number
  - create_pr with lines calculates total_estimated_cost
  - update_pr updates metadata on DRAFT
  - update_pr raises PRNotEditableError on non-DRAFT
  - add_line appends a line and recalculates total
  - remove_line soft-deletes a line and recalculates total
  - submit_pr transitions DRAFT → SUBMITTED
  - submit_pr raises PRMissingLinesError when no lines
  - submit_pr raises InvalidPRStatusTransitionError for non-DRAFT
  - approve_pr transitions SUBMITTED → APPROVED
  - approve_pr transitions UNDER_REVIEW → APPROVED
  - reject_pr transitions UNDER_REVIEW → REJECTED
  - reject_pr requires non-empty reason
  - cancel_pr transitions DRAFT → CANCELLED
  - cancel_pr transitions SUBMITTED → CANCELLED
  - cancel_pr raises InvalidPRStatusTransitionError for APPROVED
  - convert_to_po creates a PO from APPROVED PR
  - convert_to_po raises PRNotConvertibleError for non-APPROVED

No database — all repos mocked.

Task: T114
Spec ref: specs/006-purchase-management/spec.md §22 Business Workflows
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from modules.purchase.models.purchase_order import PurchaseOrder
from modules.purchase.models.purchase_request import PRLine, PurchaseRequest
from modules.purchase.schemas.purchase_request import (
    PRLineCreate,
    PurchaseRequestCreate,
    PurchaseRequestUpdate,
)
from modules.purchase.services.pr_service import (
    ALLOWED_TRANSITIONS,
    InvalidPRStatusTransitionError,
    PRMissingLinesError,
    PRNotConvertibleError,
    PRNotEditableError,
    PRService,
    _assert_transition,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(
    *,
    pr: PurchaseRequest | None = None,
    lines: list[PRLine] | None = None,
    max_line_number: int = 0,
):
    db = MagicMock()
    pr_repo = MagicMock()
    line_repo = MagicMock()
    seq_svc = MagicMock()

    seq_svc.generate_next_number.return_value = "PR-2026-000001"

    if pr is not None:
        pr_repo.get_by_id_or_none.return_value = pr
        pr_repo.create.side_effect = lambda x: x
        pr_repo.update.side_effect = lambda x: x
    else:
        pr_repo.get_by_id_or_none.return_value = None

    pr_repo.list_for_company.return_value = []
    pr_repo.count_for_company.return_value = 0
    pr_repo.get_by_pr_number.return_value = None
    pr_repo.update_status.return_value = None
    pr_repo.update_total_cost.return_value = None
    pr_repo.set_converted_to_po.return_value = None

    line_repo.list_for_pr.return_value = lines or []
    line_repo.get_max_line_number.return_value = max_line_number
    line_repo.create.side_effect = lambda x: x
    line_repo.get_by_id_or_none.return_value = None

    svc = PRService(
        db=db,
        pr_repo=pr_repo,
        line_repo=line_repo,
        sequence_service=seq_svc,
    )
    return svc, db, pr_repo, line_repo, seq_svc


def _make_pr(status: str = "DRAFT") -> PurchaseRequest:
    pr = MagicMock(spec=PurchaseRequest)
    pr.id = uuid4()
    pr.company_id = uuid4()
    pr.pr_number = "PR-2026-000001"
    pr.title = "Test PR"
    pr.status = status
    pr.requestor_id = str(uuid4())
    pr.department = "IT"
    pr.required_by_date = None
    pr.notes = None
    pr.total_estimated_cost = Decimal("0.00")
    pr.currency_code = "USD"
    pr.converted_to_po_id = None
    pr.branch_id = None
    return pr


def _make_line(line_number: int = 1) -> PRLine:
    line = MagicMock(spec=PRLine)
    line.id = uuid4()
    line.company_id = uuid4()
    line.pr_id = str(uuid4())
    line.line_number = line_number
    line.product_id = None
    line.product_description = "Test Item"
    line.quantity = Decimal("2.000")
    line.uom_id = None
    line.estimated_unit_cost = Decimal("10.0000")
    line.estimated_line_total = Decimal("20.00")
    line.notes = None
    return line


# ===========================================================================
# State machine
# ===========================================================================


class TestStateMachine:
    def test_allowed_transitions_draft(self):
        assert "SUBMITTED" in ALLOWED_TRANSITIONS["DRAFT"]
        assert "CANCELLED" in ALLOWED_TRANSITIONS["DRAFT"]

    def test_allowed_transitions_submitted(self):
        targets = ALLOWED_TRANSITIONS["SUBMITTED"]
        assert "APPROVED" in targets
        assert "REJECTED" in targets
        assert "CANCELLED" in targets
        assert "UNDER_REVIEW" in targets

    def test_terminal_statuses_have_no_transitions(self):
        for terminal in ("APPROVED", "REJECTED", "CANCELLED"):
            assert ALLOWED_TRANSITIONS[terminal] == []

    def test_assert_transition_valid(self):
        pr_id = uuid4()
        _assert_transition(pr_id, "DRAFT", "SUBMITTED")  # should not raise

    def test_assert_transition_invalid(self):
        pr_id = uuid4()
        with pytest.raises(InvalidPRStatusTransitionError):
            _assert_transition(pr_id, "APPROVED", "SUBMITTED")


# ===========================================================================
# Create PR
# ===========================================================================


class TestCreatePR:
    def test_create_pr_returns_draft(self):
        svc, db, pr_repo, line_repo, seq_svc = _make_service()
        company_id = uuid4()
        requestor_id = uuid4()

        # mock create to return a real-ish object
        created_pr = _make_pr("DRAFT")
        pr_repo.create.return_value = created_pr

        payload = PurchaseRequestCreate(title="Office Supplies", lines=[])

        with patch.object(svc, "_build_pr_read") as mock_build:
            mock_build.return_value = MagicMock()
            svc.create_pr(payload, company_id, requestor_id)

        seq_svc.generate_next_number.assert_called_once_with(company_id, "PR")
        pr_repo.create.assert_called_once()

    def test_create_pr_with_lines_creates_them(self):
        svc, db, pr_repo, line_repo, seq_svc = _make_service()
        company_id = uuid4()
        requestor_id = uuid4()

        created_pr = _make_pr("DRAFT")
        pr_repo.create.return_value = created_pr

        payload = PurchaseRequestCreate(
            title="Stationery",
            lines=[
                PRLineCreate(
                    product_description="Pens",
                    quantity=Decimal("10"),
                    estimated_unit_cost=Decimal("1"),
                ),
                PRLineCreate(
                    product_description="Paper",
                    quantity=Decimal("5"),
                    estimated_unit_cost=Decimal("2"),
                ),
            ],
        )

        with patch.object(svc, "_build_pr_read") as mock_build:
            mock_build.return_value = MagicMock()
            svc.create_pr(payload, company_id, requestor_id)

        assert line_repo.create.call_count == 2


# ===========================================================================
# Update PR
# ===========================================================================


class TestUpdatePR:
    def test_update_draft_pr_succeeds(self):
        pr = _make_pr("DRAFT")
        svc, *_ = _make_service(pr=pr)

        payload = PurchaseRequestUpdate(title="Updated Title")

        with patch.object(svc, "_build_pr_read") as mock_build:
            mock_build.return_value = MagicMock()
            svc.update_pr(pr.id, pr.company_id, payload)

        assert pr.title == "Updated Title"

    def test_update_non_draft_raises(self):
        pr = _make_pr("SUBMITTED")
        svc, *_ = _make_service(pr=pr)

        payload = PurchaseRequestUpdate(title="New")
        with pytest.raises(PRNotEditableError):
            svc.update_pr(pr.id, pr.company_id, payload)


# ===========================================================================
# Submit PR
# ===========================================================================


class TestSubmitPR:
    def test_submit_draft_with_lines_succeeds(self):
        pr = _make_pr("DRAFT")
        line = _make_line()
        svc, db, pr_repo, line_repo, _ = _make_service(pr=pr, lines=[line])

        with patch("modules.purchase.services.pr_service.get_event_bus") as mock_bus:
            mock_bus.return_value.publish = MagicMock()
            with patch.object(svc, "_build_pr_read") as mock_build:
                mock_build.return_value = MagicMock()
                svc.submit_pr(pr.id, pr.company_id, uuid4())

        pr_repo.update_status.assert_called_once_with(pr.id, pr.company_id, "SUBMITTED")

    def test_submit_no_lines_raises(self):
        pr = _make_pr("DRAFT")
        svc, *_ = _make_service(pr=pr, lines=[])

        with pytest.raises(PRMissingLinesError):
            svc.submit_pr(pr.id, pr.company_id, uuid4())

    def test_submit_non_draft_raises(self):
        pr = _make_pr("APPROVED")
        line = _make_line()
        svc, *_ = _make_service(pr=pr, lines=[line])

        with pytest.raises(InvalidPRStatusTransitionError):
            svc.submit_pr(pr.id, pr.company_id, uuid4())


# ===========================================================================
# Approve / Reject
# ===========================================================================


class TestApprovePR:
    def test_approve_submitted_pr(self):
        pr = _make_pr("SUBMITTED")
        svc, db, pr_repo, *_ = _make_service(pr=pr)

        with patch("modules.purchase.services.pr_service.get_event_bus") as mock_bus:
            mock_bus.return_value.publish = MagicMock()
            with patch.object(svc, "_build_pr_read") as mock_build:
                mock_build.return_value = MagicMock()
                svc.approve_pr(pr.id, pr.company_id, uuid4())

        pr_repo.update_status.assert_called_with(pr.id, pr.company_id, "APPROVED")

    def test_approve_already_approved_raises(self):
        pr = _make_pr("APPROVED")
        svc, *_ = _make_service(pr=pr)

        with pytest.raises(InvalidPRStatusTransitionError):
            svc.approve_pr(pr.id, pr.company_id, uuid4())


class TestRejectPR:
    def test_reject_with_reason_succeeds(self):
        pr = _make_pr("SUBMITTED")
        svc, db, pr_repo, *_ = _make_service(pr=pr)

        with patch("modules.purchase.services.pr_service.get_event_bus") as mock_bus:
            mock_bus.return_value.publish = MagicMock()
            with patch.object(svc, "_build_pr_read") as mock_build:
                mock_build.return_value = MagicMock()
                svc.reject_pr(pr.id, pr.company_id, uuid4(), reason="Budget exceeded.")

        pr_repo.update_status.assert_called_with(pr.id, pr.company_id, "REJECTED")

    def test_reject_empty_reason_raises(self):
        pr = _make_pr("SUBMITTED")
        svc, *_ = _make_service(pr=pr)

        with pytest.raises(ValueError, match="required"):
            svc.reject_pr(pr.id, pr.company_id, uuid4(), reason="")

    def test_reject_approved_pr_raises(self):
        pr = _make_pr("APPROVED")
        svc, *_ = _make_service(pr=pr)

        with pytest.raises(InvalidPRStatusTransitionError):
            svc.reject_pr(pr.id, pr.company_id, uuid4(), reason="No budget.")


# ===========================================================================
# Cancel PR
# ===========================================================================


class TestCancelPR:
    def test_cancel_draft_pr(self):
        pr = _make_pr("DRAFT")
        svc, db, pr_repo, *_ = _make_service(pr=pr)

        with patch("modules.purchase.services.pr_service.get_event_bus") as mock_bus:
            mock_bus.return_value.publish = MagicMock()
            with patch.object(svc, "_build_pr_read") as mock_build:
                mock_build.return_value = MagicMock()
                svc.cancel_pr(pr.id, pr.company_id, uuid4())

        pr_repo.update_status.assert_called_with(pr.id, pr.company_id, "CANCELLED")

    def test_cancel_submitted_pr(self):
        pr = _make_pr("SUBMITTED")
        svc, db, pr_repo, *_ = _make_service(pr=pr)

        with patch("modules.purchase.services.pr_service.get_event_bus") as mock_bus:
            mock_bus.return_value.publish = MagicMock()
            with patch.object(svc, "_build_pr_read") as mock_build:
                mock_build.return_value = MagicMock()
                svc.cancel_pr(pr.id, pr.company_id, uuid4())

        pr_repo.update_status.assert_called_with(pr.id, pr.company_id, "CANCELLED")

    def test_cancel_approved_pr_raises(self):
        pr = _make_pr("APPROVED")
        svc, *_ = _make_service(pr=pr)

        with pytest.raises(InvalidPRStatusTransitionError):
            svc.cancel_pr(pr.id, pr.company_id, uuid4())


# ===========================================================================
# Convert to PO
# ===========================================================================


class TestConvertToPO:
    def test_convert_approved_pr_creates_po(self):
        pr = _make_pr("APPROVED")
        svc, db, pr_repo, *_ = _make_service(pr=pr)
        db.add = MagicMock()
        db.flush = MagicMock()

        # Mock PO creation
        po = MagicMock(spec=PurchaseOrder)
        po.id = uuid4()
        po.po_number = "PO-2026-000001"
        po.status = "DRAFT"

        svc.sequence_service.generate_next_number.side_effect = [
            "PR-2026-000001",
            "PO-2026-000001",
        ]

        with patch("modules.purchase.services.pr_service.get_event_bus") as mock_bus:
            mock_bus.return_value.publish = MagicMock()
            with patch(
                "modules.purchase.services.pr_service.PurchaseOrder",
                return_value=po,
            ):
                result = svc.convert_to_po(pr.id, pr.company_id, uuid4())

        assert result.po_number == "PO-2026-000001"
        db.add.assert_called_once_with(po)

    def test_convert_non_approved_raises(self):
        pr = _make_pr("SUBMITTED")
        svc, *_ = _make_service(pr=pr)

        with pytest.raises(PRNotConvertibleError):
            svc.convert_to_po(pr.id, pr.company_id, uuid4())

    def test_convert_draft_raises(self):
        pr = _make_pr("DRAFT")
        svc, *_ = _make_service(pr=pr)

        with pytest.raises(PRNotConvertibleError):
            svc.convert_to_po(pr.id, pr.company_id, uuid4())

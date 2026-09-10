"""Integration tests for sales return generation and state machine — Phase 7.

Tests:
  - Create return in DRAFT status
  - Return lines created with correct extended_amount
  - Submit DRAFT → PENDING_APPROVAL
  - Approve PENDING_APPROVAL → APPROVED
  - Reject PENDING_APPROVAL → REJECTED (terminal)
  - Receive APPROVED → RECEIVED
  - Complete RECEIVED → COMPLETED with CREDIT_NOTE resolution
  - Complete RECEIVED → COMPLETED with REFUND_READINESS resolution
  - Cancel DRAFT → CANCELLED
  - Cancel PENDING_APPROVAL → CANCELLED
  - Terminal status prevents further transitions
  - List filtering by status / customer_id
  - Tenant isolation: different companies have independent sequences
  - Return number format starts with "SR-"

Task: T200, T201
Spec ref: specs/007-sales-management/spec.md §19 Sales Returns
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException, NotFoundException
from modules.sales.schemas.sales_return import (
    ReturnApproveRequest,
    ReturnCompleteRequest,
    ReturnLineCreate,
    ReturnLineReceiptItem,
    ReturnReceiveRequest,
    ReturnRejectRequest,
    SalesReturnCreate,
)
from modules.sales.services.return_service import ReturnService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _return_payload(
    customer_id=None,
    reason_code_id=None,
    resolution_type: str = "CREDIT_NOTE",
    lines=None,
) -> SalesReturnCreate:
    _lines = lines or [
        ReturnLineCreate(
            description="Widget A",
            quantity_returned=Decimal("2"),
            unit_price=Decimal("25.00"),
        )
    ]
    return SalesReturnCreate(
        customer_id=customer_id or uuid4(),
        return_date="2026-08-04",
        reason_code_id=reason_code_id or uuid4(),
        resolution_type=resolution_type,
        lines=_lines,
    )


def _svc(db: Session) -> ReturnService:
    return ReturnService(db=db)


# ---------------------------------------------------------------------------
# Create tests
# ---------------------------------------------------------------------------


class TestReturnCreation:
    def test_creates_in_draft(self, db_session: Session) -> None:
        company_id = uuid4()
        ret = _svc(db_session).create_return(
            company_id, _return_payload(), created_by=uuid4()
        )
        assert ret.status == "DRAFT"
        assert ret.company_id == company_id

    def test_return_number_starts_with_sr(self, db_session: Session) -> None:
        company_id = uuid4()
        ret = _svc(db_session).create_return(
            company_id, _return_payload(), created_by=uuid4()
        )
        assert ret.return_number.startswith("SR-")

    def test_sequential_numbers(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = _svc(db_session)
        r1 = svc.create_return(company_id, _return_payload(), created_by=uuid4())
        r2 = svc.create_return(company_id, _return_payload(), created_by=uuid4())
        assert r1.return_number != r2.return_number

    def test_lines_extended_amount(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = _svc(db_session)
        payload = _return_payload(
            lines=[
                ReturnLineCreate(
                    description="Item",
                    quantity_returned=Decimal("3"),
                    unit_price=Decimal("10.00"),
                )
            ]
        )
        ret = svc.create_return(company_id, payload, created_by=uuid4())
        lines = svc.get_return_lines(company_id, ret.id)
        assert len(lines) == 1
        assert lines[0].extended_amount == Decimal("30.00")

    def test_multi_line_return(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = _svc(db_session)
        payload = _return_payload(
            lines=[
                ReturnLineCreate(
                    description="A",
                    quantity_returned=Decimal("1"),
                    unit_price=Decimal("10"),
                ),
                ReturnLineCreate(
                    description="B",
                    quantity_returned=Decimal("2"),
                    unit_price=Decimal("5"),
                ),
            ]
        )
        ret = svc.create_return(company_id, payload, created_by=uuid4())
        lines = svc.get_return_lines(company_id, ret.id)
        assert len(lines) == 2

    def test_independent_sequences_per_company(self, db_session: Session) -> None:
        c1, c2 = uuid4(), uuid4()
        svc = _svc(db_session)
        r1 = svc.create_return(c1, _return_payload(), created_by=uuid4())
        r2 = svc.create_return(c2, _return_payload(), created_by=uuid4())
        # Both start at 000001
        assert r1.return_number.endswith("000001")
        assert r2.return_number.endswith("000001")


# ---------------------------------------------------------------------------
# State machine tests
# ---------------------------------------------------------------------------


class TestReturnStateMachineIntegration:
    def test_submit_transition(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = _svc(db_session)
        ret = svc.create_return(company_id, _return_payload(), created_by=uuid4())
        ret = svc.submit_return(company_id, ret.id, submitted_by=uuid4())
        assert ret.status == "PENDING_APPROVAL"

    def test_approve_transition(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = _svc(db_session)
        ret = svc.create_return(company_id, _return_payload(), created_by=uuid4())
        ret = svc.submit_return(company_id, ret.id, submitted_by=uuid4())
        ret = svc.approve_return(
            company_id, ret.id, ReturnApproveRequest(), approved_by=uuid4()
        )
        assert ret.status == "APPROVED"

    def test_reject_transition(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = _svc(db_session)
        ret = svc.create_return(company_id, _return_payload(), created_by=uuid4())
        ret = svc.submit_return(company_id, ret.id, submitted_by=uuid4())
        ret = svc.reject_return(
            company_id,
            ret.id,
            ReturnRejectRequest(rejection_reason="Duplicate"),
            rejected_by=uuid4(),
        )
        assert ret.status == "REJECTED"

    def test_rejected_is_terminal(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = _svc(db_session)
        ret = svc.create_return(company_id, _return_payload(), created_by=uuid4())
        ret = svc.submit_return(company_id, ret.id, submitted_by=uuid4())
        ret = svc.reject_return(
            company_id,
            ret.id,
            ReturnRejectRequest(rejection_reason="No"),
            rejected_by=uuid4(),
        )
        with pytest.raises(ConflictException):
            svc.approve_return(
                company_id, ret.id, ReturnApproveRequest(), approved_by=uuid4()
            )

    def test_cancel_from_draft(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = _svc(db_session)
        ret = svc.create_return(company_id, _return_payload(), created_by=uuid4())
        ret = svc.cancel_return(company_id, ret.id, cancelled_by=uuid4())
        assert ret.status == "CANCELLED"

    def test_cancel_from_pending_approval(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = _svc(db_session)
        ret = svc.create_return(company_id, _return_payload(), created_by=uuid4())
        ret = svc.submit_return(company_id, ret.id, submitted_by=uuid4())
        ret = svc.cancel_return(company_id, ret.id, cancelled_by=uuid4())
        assert ret.status == "CANCELLED"

    def test_receive_transition(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = _svc(db_session)
        ret = svc.create_return(company_id, _return_payload(), created_by=uuid4())
        ret = svc.submit_return(company_id, ret.id, submitted_by=uuid4())
        ret = svc.approve_return(
            company_id, ret.id, ReturnApproveRequest(), approved_by=uuid4()
        )
        # Get lines to build receipt
        lines = svc.get_return_lines(company_id, ret.id)
        receipt_items = [
            ReturnLineReceiptItem(
                line_id=lines[0].id,
                quantity_accepted=Decimal("2"),
                quantity_rejected=Decimal("0"),
            )
        ]
        ret = svc.receive_return(
            company_id,
            ret.id,
            ReturnReceiveRequest(accepted_lines=receipt_items),
            received_by=uuid4(),
        )
        assert ret.status == "RECEIVED"
        assert ret.received_by is not None

    def test_complete_with_credit_note(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = _svc(db_session)
        ret = svc.create_return(
            company_id,
            _return_payload(resolution_type="CREDIT_NOTE"),
            created_by=uuid4(),
        )
        ret = svc.submit_return(company_id, ret.id, submitted_by=uuid4())
        ret = svc.approve_return(
            company_id, ret.id, ReturnApproveRequest(), approved_by=uuid4()
        )
        lines = svc.get_return_lines(company_id, ret.id)
        receipt_items = [
            ReturnLineReceiptItem(
                line_id=lines[0].id,
                quantity_accepted=Decimal("2"),
                quantity_rejected=Decimal("0"),
            )
        ]
        ret = svc.receive_return(
            company_id,
            ret.id,
            ReturnReceiveRequest(accepted_lines=receipt_items),
            received_by=uuid4(),
        )
        ret = svc.complete_return(
            company_id,
            ret.id,
            ReturnCompleteRequest(credit_note_amount=Decimal("50.00")),
            completed_by=uuid4(),
        )
        assert ret.status == "COMPLETED"
        assert ret.credit_note_amount == Decimal("50.00")

    def test_complete_with_refund_readiness(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = _svc(db_session)
        ret = svc.create_return(
            company_id,
            _return_payload(resolution_type="REFUND_READINESS"),
            created_by=uuid4(),
        )
        ret = svc.submit_return(company_id, ret.id, submitted_by=uuid4())
        ret = svc.approve_return(
            company_id, ret.id, ReturnApproveRequest(), approved_by=uuid4()
        )
        lines = svc.get_return_lines(company_id, ret.id)
        receipt_items = [
            ReturnLineReceiptItem(
                line_id=lines[0].id,
                quantity_accepted=Decimal("1"),
                quantity_rejected=Decimal("1"),
            )
        ]
        ret = svc.receive_return(
            company_id,
            ret.id,
            ReturnReceiveRequest(accepted_lines=receipt_items),
            received_by=uuid4(),
        )
        ret = svc.complete_return(
            company_id,
            ret.id,
            ReturnCompleteRequest(),
            completed_by=uuid4(),
        )
        assert ret.status == "COMPLETED"

    def test_credit_note_requires_amount(self, db_session: Session) -> None:
        """CREDIT_NOTE resolution without amount must raise ConflictException."""
        company_id = uuid4()
        svc = _svc(db_session)
        ret = svc.create_return(
            company_id,
            _return_payload(resolution_type="CREDIT_NOTE"),
            created_by=uuid4(),
        )
        ret = svc.submit_return(company_id, ret.id, submitted_by=uuid4())
        ret = svc.approve_return(
            company_id, ret.id, ReturnApproveRequest(), approved_by=uuid4()
        )
        lines = svc.get_return_lines(company_id, ret.id)
        receipt_items = [
            ReturnLineReceiptItem(
                line_id=lines[0].id,
                quantity_accepted=Decimal("2"),
                quantity_rejected=Decimal("0"),
            )
        ]
        ret = svc.receive_return(
            company_id,
            ret.id,
            ReturnReceiveRequest(accepted_lines=receipt_items),
            received_by=uuid4(),
        )
        with pytest.raises(ConflictException, match="credit_note_amount"):
            svc.complete_return(
                company_id,
                ret.id,
                ReturnCompleteRequest(credit_note_amount=None),
                completed_by=uuid4(),
            )


# ---------------------------------------------------------------------------
# List tests
# ---------------------------------------------------------------------------


class TestReturnListFilters:
    def test_list_by_status(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = _svc(db_session)
        ret = svc.create_return(company_id, _return_payload(), created_by=uuid4())
        svc.submit_return(company_id, ret.id, submitted_by=uuid4())

        draft_items, draft_total = svc.list_returns(company_id, status="DRAFT")
        pending_items, pending_total = svc.list_returns(
            company_id, status="PENDING_APPROVAL"
        )
        assert draft_total == 0
        assert pending_total == 1

    def test_list_by_customer(self, db_session: Session) -> None:
        company_id = uuid4()
        customer_a = uuid4()
        customer_b = uuid4()
        svc = _svc(db_session)
        svc.create_return(
            company_id, _return_payload(customer_id=customer_a), created_by=uuid4()
        )
        svc.create_return(
            company_id, _return_payload(customer_id=customer_b), created_by=uuid4()
        )

        items_a, total_a = svc.list_returns(company_id, customer_id=str(customer_a))
        assert total_a == 1

    def test_tenant_isolation(self, db_session: Session) -> None:
        c1, c2 = uuid4(), uuid4()
        svc = _svc(db_session)
        svc.create_return(c1, _return_payload(), created_by=uuid4())

        items_c2, total_c2 = svc.list_returns(c2)
        assert total_c2 == 0

    def test_not_found_raises(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = _svc(db_session)
        with pytest.raises(NotFoundException):
            svc.get_return(company_id, uuid4())
